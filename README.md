# Automated Code Debugger & Bug Finder (Topik 1) — IF-504 Kecerdasan Buatan

Sistem Agentic AI: Python + LangChain + LangGraph + Ollama lokal (`qwen2.5`).

## Cara menjalankan

```bash
pip install -r requirements.txt
ollama pull qwen2.5:3b          # atau: ollama pull qwen2.5:7b
ollama serve                 # jika belum berjalan

python main.py --demo syntax     # SyntaxError (titik dua hilang)
python main.py --demo runtime    # ZeroDivisionError
python main.py --demo rewrite    # query KB pertama NOT_FOUND -> Query Rewriting
python main.py --demo clean      # tanpa bug (graf berhenti tanpa Safety Gate)
python main.py kodeku.py         # file sendiri
python main.py --model qwen2.5:3b --demo runtime
python main.py --show-graph      # diagram Mermaid untuk PPT (tanpa Ollama)

python -m pytest -q              # tes alur offline (tanpa Ollama)
```

`--demo` menyalin sampel ke `workspace/` setiap kali dijalankan, jadi bisa diulang. Trace log tersimpan di `logs/`.

## Arsitektur

```
START -> supervisor --(conditional routing)--> syntax_checker  (ReAct)
            ^                              --> rag_specialist  (Agentic RAG)
            |                              --> code_fixer      (tulis ulang + validasi)
            +------ semua worker lapor ke supervisor
                                           --> apply_patch  [interrupt_before] -> END
                                           --> finish -> END
```

| File                              | Peran                                                                              |
| --------------------------------- | ---------------------------------------------------------------------------------- |
| `graph.py`                        | `StateGraph`, conditional edges, `MemorySaver`, `interrupt_before=["apply_patch"]` |
| `nodes.py`                        | Supervisor, 3 Worker, Apply Patch, prompt                                          |
| `tools.py`                        | `check_syntax`, `run_code`, `read_code_lines`, `search_knowledge_base`             |
| `knowledge_base.py`, `kb_data.py` | KB internal (15 dokumen) + retriever berbobot IDF                                  |
| `analysis.py`                     | cek sintaks (`ast`), eksekusi subprocess + timeout, validasi perbaikan             |
| `llm_utils.py`                    | retry Ollama, parser JSON / blok kode yang toleran, health check                   |
| `main.py`                         | CLI, Trace Log live, gerbang persetujuan manusia                                   |
| `tests/`                          | 11 tes offline dengan LLM palsu                                                    |

## Pemetaan ke ketentuan & rubrik

**1. ReAct Diagnostic Loop** — `make_syntax_checker`: LLM memanggil tool bertahap; Trace Log mencatat `Thought → Action → Observation`. Fakta (jenis error, baris) selalu diambil dari output tool; LLM hanya menyumbang penjelasan. Jika model lupa memanggil tool, node memanggilnya sendiri (`Action[paksa]`).

**2. Agentic RAG & Self-Correction** — `make_rag_specialist`: query pertama dari pesan error mentah. Status `FOUND` jika cakupan kata kunci ≥ 0.8 (`kb_threshold`), selain itu `NOT_FOUND` → LLM menulis ulang query (maks. 2×, `max_rewrites`). Query tidak pernah diulang: jika LLM mengulang, dipakai aturan cadangan (`fallback_rewrite`). Jika tetap tidak ketemu, alur lanjut dengan keterbatasan yang tercatat di trace.

**3. Supervisor-Worker** — `decide_next` memilih tujuan berdasarkan isi state (bukan urutan tetap): clean code → selesai; perbaikan tidak valid → Code Fixer lagi (maks. 3×) lalu selesai tanpa patch. Anti infinite loop berlapis: `max_supervisor_steps` (12) + `recursion_limit` (40) + batas percobaan per worker. Worker terisolasi: tiap worker hanya menerima state dan tool miliknya.

**4. Human-in-the-Loop** — `interrupt_before=["apply_patch"]` + `MemorySaver`. Graf berhenti, CLI menampilkan diff, lalu `update_state(human_approved=...)` dan `invoke(None, config)` melanjutkan dari checkpoint yang sama. Tambahan pengaman: backup `.bak`, dan patch dibatalkan bila file berubah selama menunggu persetujuan.

**5. Stabilitas Ollama** — suhu 0, tool tanpa argumen path (mengurangi salah skema), `safe_invoke` dengan retry, kode perbaikan diambil dari blok `python` (bukan JSON, karena kode di dalam string JSON sering rusak pada model kecil), semua hasil perbaikan divalidasi (`ast` + dijalankan) sebelum diajukan ke manusia.

## Bahan untuk demo / presentasi

- Alur terbaik untuk ditunjukkan: `--demo rewrite` (menampilkan ReAct + NOT_FOUND + Query Rewriting + Safety Gate sekaligus).
- Tunjukkan juga jawaban `n` pada Safety Gate: file tetap utuh (`patch_status=REJECTED`).
- Jelaskan Trace Log baris per baris; setiap anggota sebaiknya menguasai satu bagian (Supervisor/graph, RAG, Fixer+HITL).
- Rumus keputusan dapat dijelaskan lewat `decide_next` (nodes.py) — fungsinya murni dan mudah ditelusuri.

## Batasan yang perlu diketahui

- `run_code` dan validasi **mengeksekusi** kode target (subprocess, timeout 5 detik, tanpa stdin). Pakai hanya untuk kode tugas milik sendiri.
- Program yang memerlukan `input()` akan mengalami `EOFError` saat dijalankan agen.
- `MemorySaver` hanya di memori: persetujuan harus diberikan di proses yang sama (cukup untuk demo; produksi memakai SQLite/Postgres checkpointer).
- Supervisor berbasis aturan (bukan LLM) demi stabilitas model lokal.
- Kode ini diuji offline dengan LLM palsu; kualitas perbaikan nyata bergantung pada model Ollama Anda.
