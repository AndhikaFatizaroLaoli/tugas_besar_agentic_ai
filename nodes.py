"""Node-node StateGraph: Supervisor, 3 Worker (+ Apply Patch)."""
import json
import re
import shutil
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from analysis import run_python_file, syntax_check, validate_fix
from llm_utils import LLMError, extract_code_block, extract_json, safe_invoke
from tools import build_tools

# =====================================================================================
# Prompt
# =====================================================================================
SYNTAX_CHECKER_PROMPT = """Kamu adalah Syntax Checker Worker pada sistem Automated Code Debugger.
Tugas: mendiagnosis jenis dan lokasi kesalahan pada file kode Python target.

Gunakan pola ReAct: tulis "Thought:" singkat (1 kalimat) tentang langkah berikutnya, lalu panggil SATU tool,
baca Observation, dan ulangi sampai bukti cukup.
Tools: check_syntax, run_code, read_code_lines.
Urutan yang disarankan:
1. check_syntax.
2. Jika sintaks OK, panggil run_code untuk menemukan runtime error.
3. (Opsional) read_code_lines di sekitar baris error untuk melihat konteks.

Setelah bukti cukup, jawab HANYA dengan JSON (tanpa tool call):
{"status": "SYNTAX_ERROR | RUNTIME_ERROR | OK", "error_type": "...", "message": "...", "line": 0, "explanation": "penjelasan singkat penyebab"}"""

QUERY_REWRITER_PROMPT = """Kamu adalah Query Rewriter pada sistem Agentic RAG.
Pencarian ke Knowledge Base dengan query sebelumnya menghasilkan NOT_FOUND.
Tulis ulang menjadi SATU query baru yang pendek (maksimal 6 kata kunci), fokus pada nama jenis error
dan konsep penyebabnya, bukan salinan pesan error mentah. Jangan mengulang query yang sudah dicoba.
Jawab HANYA dengan query barunya, satu baris, tanpa penjelasan."""

CODE_FIXER_PROMPT = """Kamu adalah Code Fixer Worker pada sistem Automated Code Debugger.
Tulis ulang SELURUH kode Python agar bebas bug, berdasarkan diagnosis dan referensi Knowledge Base.
Aturan:
- Pertahankan logika, nama fungsi, dan struktur asli; ubah seminimal mungkin.
- Jangan menambahkan penjelasan di luar blok kode.
- Jawab dengan tepat SATU blok kode ```python ... ``` berisi kode lengkap yang sudah diperbaiki."""


# =====================================================================================
# Util
# =====================================================================================
def _t(node: str, kind: str, text: str) -> str:
    text = " ".join(str(text).split())
    if len(text) > 300:
        text = text[:297] + "..."
    return f"[{node}] {kind}: {text}"


def _loads(text: str):
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


def _call_tool(by_name: dict, name: str, args: dict) -> str:
    if name not in by_name:
        return f"ERROR: tool '{name}' tidak dikenal. Pilihan: {', '.join(by_name)}"
    try:
        return str(by_name[name].invoke(args or {}))
    except Exception as exc:  # noqa: BLE001 - argumen salah dari LLM tidak boleh menjatuhkan graf
        return f"ERROR: pemanggilan tool gagal ({type(exc).__name__}: {exc})"


# =====================================================================================
# Supervisor
# =====================================================================================
def decide_next(state: dict, s) -> tuple:
    """Keputusan routing dinamis berdasarkan isi state. Return (tujuan, alasan)."""
    if state.get("steps", 0) >= s.max_supervisor_steps:
        return "finish", "batas langkah Supervisor tercapai (guard anti infinite loop)"
    diag = state.get("diagnosis")
    if not diag:
        return "syntax_checker", "belum ada diagnosis"
    if diag.get("status") == "OK":
        return "finish", "tidak ditemukan bug"
    if not state.get("kb_done"):
        return "rag_specialist", f"diagnosis {diag.get('error_type')} sudah ada, cari referensi di Knowledge Base"
    fixed, valid = state.get("fixed_code"), state.get("fix_valid")
    attempts = state.get("fix_attempts", 0)
    if not fixed or valid is False:
        if attempts < s.max_fix_attempts:
            why = "belum ada kode perbaikan" if not fixed else f"perbaikan belum valid ({state.get('fix_report')})"
            return "code_fixer", f"{why}; percobaan ke-{attempts + 1}/{s.max_fix_attempts}"
        return "finish", f"perbaikan tidak lolos validasi setelah {attempts} percobaan; patch tidak diterapkan"
    return "apply_patch", "kode perbaikan valid -> menuju Safety Gate (menunggu persetujuan manusia)"


def make_supervisor(settings):
    def supervisor(state: dict) -> dict:
        nxt, reason = decide_next(state, settings)
        update = {
            "next": nxt,
            "steps": state.get("steps", 0) + 1,
            "trace": [_t("supervisor", "Routing", f"-> {nxt} ({reason})")],
        }
        if nxt == "finish":
            diag = state.get("diagnosis") or {}
            if state.get("steps", 0) >= settings.max_supervisor_steps:
                update["final_status"] = "STEP_LIMIT"
            elif diag.get("status") == "OK":
                update["final_status"] = "NO_BUG"
            else:
                update["final_status"] = "FIX_FAILED"
        return update

    return supervisor


def route_from_supervisor(state: dict) -> str:
    return state["next"]


# =====================================================================================
# Worker 1: Syntax Checker (ReAct)
# =====================================================================================
def make_syntax_checker(llm, kb, settings):
    name = "syntax_checker"

    def node(state: dict) -> dict:
        path = state["target_path"]
        tools = build_tools(path, kb, settings)
        diag_tools = [tools["check_syntax"], tools["run_code"], tools["read_code_lines"]]
        by_name = {t.name: t for t in diag_tools}
        trace, facts, explanation, llm_status = [], {}, "", None

        try:
            llm_tools = llm.bind_tools(diag_tools)
        except Exception as exc:  # noqa: BLE001 - model tanpa dukungan tool calling
            llm_tools = None
            trace.append(_t(name, "Peringatan", f"bind_tools gagal ({exc}); memakai mode paksa"))

        messages = [
            SystemMessage(content=SYNTAX_CHECKER_PROMPT),
            HumanMessage(content=f"Diagnosis file '{Path(path).name}'. Mulai dari check_syntax."),
        ]
        # ---- Siklus ReAct: Thought -> Action -> Observation ----
        if llm_tools is not None:
            for step in range(1, settings.max_react_steps + 1):
                try:
                    ai = safe_invoke(llm_tools, messages, settings.llm_retries)
                except LLMError as exc:
                    trace.append(_t(name, "Peringatan", str(exc)))
                    break
                messages.append(ai)
                thought = (ai.content or "").strip()
                calls = getattr(ai, "tool_calls", None) or []
                if not calls:  # jawaban akhir
                    parsed = extract_json(thought)
                    explanation = (parsed or {}).get("explanation", "") or ""
                    llm_status = (parsed or {}).get("status")
                    trace.append(_t(name, f"Final[{step}]", thought or "(kosong)"))
                    break
                trace.append(_t(name, f"Thought[{step}]", thought or "(model langsung memanggil tool)"))
                for call in calls:
                    tname, args = call.get("name", ""), call.get("args") or {}
                    trace.append(_t(name, f"Action[{step}]", f"{tname}({json.dumps(args, ensure_ascii=False)})"))
                    obs = _call_tool(by_name, tname, args)
                    trace.append(_t(name, f"Observation[{step}]", obs))
                    if tname in ("check_syntax", "run_code") and _loads(obs):
                        facts[tname] = _loads(obs)
                    messages.append(
                        ToolMessage(content=obs, tool_call_id=call.get("id") or f"{tname}-{step}", name=tname)
                    )

        # ---- Pengaman: fakta HARUS berasal dari tool, bukan tebakan LLM ----
        if "check_syntax" not in facts:
            facts["check_syntax"] = syntax_check(Path(path).read_text(encoding="utf-8"))
            trace.append(_t(name, "Action[paksa]", "check_syntax() -> " + json.dumps(facts["check_syntax"], ensure_ascii=False)))
        if facts["check_syntax"]["status"] == "OK" and "run_code" not in facts:
            facts["run_code"] = run_python_file(path, settings.run_timeout)
            trace.append(_t(name, "Action[paksa]", "run_code() -> " + json.dumps(facts["run_code"], ensure_ascii=False)))

        cs, rc = facts["check_syntax"], facts.get("run_code", {})
        if cs["status"] == "SYNTAX_ERROR":
            diag = {"status": "SYNTAX_ERROR", **{k: cs.get(k) for k in ("error_type", "message", "line")}}
        elif rc.get("status") == "RUNTIME_ERROR":
            diag = {"status": "RUNTIME_ERROR", **{k: rc.get(k) for k in ("error_type", "message", "line")}}
        else:
            diag = {"status": "OK", "error_type": None, "message": "Tidak ada error terdeteksi", "line": None}
        # penjelasan LLM hanya dipakai bila statusnya konsisten dengan fakta dari tool
        diag["explanation"] = explanation if llm_status == diag["status"] else ""
        trace.append(_t(name, "Diagnosis", json.dumps(diag, ensure_ascii=False)))
        return {"diagnosis": diag, "trace": trace}

    return node


# =====================================================================================
# Worker 2: RAG Specialist (Agentic RAG + Self-Correction / Query Rewriting)
# =====================================================================================
_TYPE_RE = re.compile(r"\b(str|int|float|list|dict|tuple|set|bool|NoneType)\b")


def fallback_rewrite(diag: dict, tried: list) -> str:
    """Query Rewriting berbasis aturan (cadangan bila LLM gagal / mengulang query)."""
    etype = diag.get("error_type") or "error"
    types = " ".join(dict.fromkeys(_TYPE_RE.findall(diag.get("message") or "")))
    candidates = [
        f"{etype} {types}".strip(),
        etype,
        f"{etype} penyebab dan cara memperbaiki",
        f"{diag.get('status', '')} {etype} python".strip(),
    ]
    tried_l = {q.lower() for q in tried}
    for c in candidates:
        if c.lower() not in tried_l:
            return c
    return candidates[-1] + " solusi"


def make_rag_specialist(llm, kb, settings):
    name = "rag_specialist"

    def rewrite(diag: dict, tried: list, trace: list, force_rule: bool = False) -> str:
        new_q = ""
        if force_rule:  # LLM sudah sekali gagal -> pakai aturan deterministik
            trace.append(_t(name, "Rewrite", "rewrite LLM sebelumnya gagal -> memakai aturan deterministik"))
            return fallback_rewrite(diag, tried)
        try:
            resp = safe_invoke(
                llm,
                [
                    SystemMessage(content=QUERY_REWRITER_PROMPT),
                    HumanMessage(
                        content=(
                            f"Diagnosis: {diag.get('error_type')}: {diag.get('message')}\n"
                            f"Query yang sudah dicoba (semua NOT_FOUND): {tried}"
                        )
                    ),
                ],
                settings.llm_retries,
            )
            lines = [ln.strip() for ln in (resp.content or "").strip().splitlines() if ln.strip()]
            new_q = re.sub(r"^(query|kueri)\s*:\s*", "", lines[0], flags=re.I) if lines else ""
            new_q = new_q.replace('"', " ").replace("'", " ").replace("`", " ")
            new_q = " ".join(new_q.split())[:80]
        except LLMError as exc:
            trace.append(_t(name, "Peringatan", str(exc)))
        if not new_q or new_q.lower() in {q.lower() for q in tried}:
            new_q = fallback_rewrite(diag, tried)
            trace.append(_t(name, "Rewrite", "LLM tidak memberi query baru -> pakai aturan cadangan"))
        return new_q

    def node(state: dict) -> dict:
        diag = state["diagnosis"]
        tools = build_tools(state["target_path"], kb, settings)
        search = tools["search_knowledge_base"]
        trace, queries = [], []
        query = f"{diag.get('error_type')}: {diag.get('message')}"
        result = {"status": "NOT_FOUND", "results": []}

        for attempt in range(settings.max_rewrites + 1):
            queries.append(query)
            trace.append(_t(name, f"Action[{attempt}]", f'search_knowledge_base(query="{query}")'))
            result = json.loads(search.invoke({"query": query}))
            trace.append(
                _t(name, f"Observation[{attempt}]", f"{result['status']} (skor terbaik {result['best_score']})")
            )
            if result["status"] == "FOUND":
                break
            if attempt == settings.max_rewrites:
                trace.append(_t(name, "Batas", "Query Rewriting habis; lanjut dengan keterbatasan (tanpa referensi KB)"))
                break
            query = rewrite(diag, queries, trace, force_rule=attempt >= 1)
            trace.append(_t(name, "Self-Correction", f'NOT_FOUND -> Query Rewriting: "{query}"'))

        docs = result.get("results", [])
        if docs:
            trace.append(_t(name, "Sumber", ", ".join(f"{d['doc_id']} ({d['score']})" for d in docs)))
        return {
            "kb_done": True,
            "kb_status": result["status"],
            "kb_docs": docs,
            "kb_queries": queries,
            "trace": trace,
        }

    return node


# =====================================================================================
# Worker 3: Code Fixer
# =====================================================================================
def make_code_fixer(llm, settings):
    name = "code_fixer"

    def node(state: dict) -> dict:
        attempt = state.get("fix_attempts", 0) + 1
        diag, original = state["diagnosis"], state["original_code"]
        docs = state.get("kb_docs") or []
        ref = (
            "\n\n".join(f"[{d['doc_id']}] {d['title']}\n{d['content']}" for d in docs)
            if docs
            else "(Tidak ada referensi di Knowledge Base; gunakan pengetahuan umum Python secara hati-hati.)"
        )
        feedback = ""
        if state.get("fix_valid") is False:
            feedback = f"\n\nPERCOBAAN SEBELUMNYA GAGAL: {state.get('fix_report')}. Perbaiki kesalahan tersebut."
        user = (
            f"Kode asli:\n```python\n{original}```\n\n"
            f"Diagnosis: {diag.get('status')} {diag.get('error_type')} di baris {diag.get('line')}: {diag.get('message')}\n\n"
            f"Referensi Knowledge Base:\n{ref}{feedback}"
        )
        trace = [_t(name, "Action", f"menulis ulang kode (percobaan {attempt}/{settings.max_fix_attempts})")]
        candidate = None
        try:
            resp = safe_invoke(
                llm, [SystemMessage(content=CODE_FIXER_PROMPT), HumanMessage(content=user)], settings.llm_retries
            )
            candidate = extract_code_block(resp.content)
        except LLMError as exc:
            trace.append(_t(name, "Peringatan", str(exc)))

        if candidate is None:
            valid, report = False, "Respons LLM tidak berisi blok kode ```python```."
            candidate = state.get("fixed_code", "")
        else:
            valid, report = validate_fix(candidate, original, state["target_path"], settings.run_timeout)
        trace.append(_t(name, "Validasi", f"{'LOLOS' if valid else 'GAGAL'} - {report}"))
        return {
            "fixed_code": candidate,
            "fix_valid": valid,
            "fix_report": report,
            "fix_attempts": attempt,
            "trace": trace,
        }

    return node


# =====================================================================================
# Apply Patch (dihentikan oleh interrupt_before -> Human-in-the-Loop)
# =====================================================================================
def apply_patch_node(state: dict) -> dict:
    name = "apply_patch"
    path = Path(state["target_path"])
    if state.get("human_approved") is not True:
        return {
            "patch_status": "REJECTED",
            "final_status": "PATCH_REJECTED",
            "trace": [_t(name, "Hasil", "Patch DITOLAK manusia; file tidak diubah")],
        }
    if path.read_text(encoding="utf-8") != state["original_code"]:
        return {
            "patch_status": "ABORTED",
            "final_status": "PATCH_ABORTED",
            "trace": [_t(name, "Hasil", "DIBATALKAN: file berubah sejak diagnosis; patch tidak diterapkan")],
        }
    backup = path.with_name(path.name + ".bak")
    shutil.copy2(path, backup)
    path.write_text(state["fixed_code"], encoding="utf-8")
    return {
        "patch_status": "APPLIED",
        "final_status": "PATCH_APPLIED",
        "trace": [_t(name, "Hasil", f"Patch DITERAPKAN ke {path.name} (backup: {backup.name})")],
    }