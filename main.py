"""CLI Automated Code Debugger (Topik 1) - LangGraph + Ollama lokal + Human-in-the-Loop.

Contoh:
    python main.py --demo syntax            # salin sampel ke workspace/ lalu jalankan
    python main.py path/ke/kode_bermasalah.py
    python main.py --show-graph             # cetak diagram Mermaid (untuk PPT)
"""
import argparse
import dataclasses
import difflib
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path

from config import SETTINGS
from graph import build_graph
from llm_utils import check_ollama, get_llm

ROOT = Path(__file__).parent
DEMOS = {
    "syntax": "bug_syntax.py",  # SyntaxError (titik dua hilang)
    "runtime": "bug_runtime.py",  # ZeroDivisionError
    "rewrite": "bug_rewrite.py",  # TypeError; query pertama NOT_FOUND -> Query Rewriting
    "clean": "bug_clean.py",  # tanpa bug
}


def stream_run(graph, payload, config):
    """Jalankan graf dan cetak Trace Log per node secara berurutan."""
    for chunk in graph.stream(payload, config, stream_mode="updates"):
        for node, update in chunk.items():
            if node.startswith("__") or not isinstance(update, dict):
                continue
            for line in update.get("trace", []):
                print(line)


def show_diff(original: str, fixed: str, name: str):
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        fixed.splitlines(keepends=True),
        fromfile=f"{name} (asli)",
        tofile=f"{name} (perbaikan)",
    )
    print("".join(diff) or "(tidak ada perbedaan)")


def ask_approval() -> bool:
    while True:
        ans = input("\nTerapkan patch ke file? [y = setuju / n = tolak]: ").strip().lower()
        if ans in ("y", "yes", "ya"):
            return True
        if ans in ("n", "no", "tidak"):
            return False
        print("Jawab 'y' atau 'n'.")


def save_trace(values: dict, target: Path) -> Path:
    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    path = log_dir / f"trace_{target.stem}_{datetime.now():%Y%m%d_%H%M%S}.log"
    lines = list(values.get("trace", []))
    lines.append(f"[hasil] final_status={values.get('final_status')} patch_status={values.get('patch_status')}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Automated Code Debugger & Bug Finder (Agentic AI)")
    ap.add_argument("target", nargs="?", help="path file .py yang bermasalah")
    ap.add_argument("--demo", choices=sorted(DEMOS), help="salin sampel bug ke workspace/ dan jalankan")
    ap.add_argument("--model", default=SETTINGS.model, help="model Ollama (qwen2.5:3b)")
    ap.add_argument("--show-graph", action="store_true", help="cetak diagram Mermaid lalu keluar")
    args = ap.parse_args(argv)

    settings = dataclasses.replace(SETTINGS, model=args.model)

    if args.show_graph:
        class _NoLLM:  # hanya untuk menggambar topologi graf
            def bind_tools(self, *_a, **_k):
                return self

        print(build_graph(_NoLLM(), settings).get_graph().draw_mermaid())
        return 0

    if args.demo:
        work = ROOT / "workspace"
        work.mkdir(exist_ok=True)
        target = work / DEMOS[args.demo]
        shutil.copy(ROOT / "samples" / DEMOS[args.demo], target)
    elif args.target:
        target = Path(args.target)
    else:
        ap.error("berikan path file atau gunakan --demo")
    target = target.resolve()
    if not target.is_file() or target.suffix != ".py":
        print(f"File tidak ditemukan / bukan .py: {target}")
        return 1

    ok, msg = check_ollama(settings)
    if not ok:
        print(f"[Ollama] {msg}")
        return 1

    graph = build_graph(get_llm(settings), settings)
    config = {"configurable": {"thread_id": str(uuid.uuid4())}, "recursion_limit": settings.recursion_limit}
    initial = {
        "target_path": str(target),
        "original_code": target.read_text(encoding="utf-8"),
        "steps": 0,
        "fix_attempts": 0,
        "trace": [],
    }

    print(f"=== Debugging {target.name} dengan model {settings.model} ===\n")
    stream_run(graph, initial, config)

    # ---- Safety Gate: graf berhenti SEBELUM apply_patch ----
    snapshot = graph.get_state(config)
    if snapshot.next == ("apply_patch",):
        values = snapshot.values
        print("\n" + "=" * 60)
        print("SAFETY GATE: graf berhenti sebelum node apply_patch (state tersimpan di MemorySaver).")
        print("Usulan perbaikan:\n")
        show_diff(values["original_code"], values["fixed_code"], target.name)
        approved = ask_approval()
        graph.update_state(config, {"human_approved": approved}, as_node="supervisor")
        print()
        stream_run(graph, None, config)  # lanjutkan dari checkpoint

    final = graph.get_state(config).values
    log_path = save_trace(final, target)
    print(f"\nStatus akhir: {final.get('final_status')}")
    print(f"Trace log disimpan di: {log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
