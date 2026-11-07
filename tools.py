"""Tools LangChain yang dipakai agen (Action pada siklus ReAct)."""
import json
from pathlib import Path

from langchain_core.tools import tool

from analysis import run_python_file, syntax_check


def build_tools(target_path: str, kb, settings) -> dict:
    """Bangun tools yang terikat pada satu file target.

    Path TIDAK dijadikan argumen tool: model lokal sering salah mengisi path, dan
    agen tidak boleh membaca file di luar target. Argumen yang tersisa sederhana
    (angka/teks pendek) sehingga skema tool calling Ollama lebih stabil.
    """
    path = Path(target_path)

    @tool
    def check_syntax() -> str:
        """Periksa sintaks file kode target dengan parser Python. Hasil JSON: status OK atau SYNTAX_ERROR beserta error_type, message, line."""
        return json.dumps(syntax_check(path.read_text(encoding="utf-8")), ensure_ascii=False)

    @tool
    def run_code() -> str:
        """Jalankan file kode target (timeout singkat) untuk menemukan runtime error. Hasil JSON: status OK atau RUNTIME_ERROR beserta error_type, message, line."""
        return json.dumps(run_python_file(path, settings.run_timeout), ensure_ascii=False)

    @tool
    def read_code_lines(start_line: int, end_line: int) -> str:
        """Baca potongan kode target dari start_line sampai end_line (nomor baris mulai dari 1) untuk melihat konteks di sekitar error."""
        lines = path.read_text(encoding="utf-8").splitlines()
        start = max(1, int(start_line))
        end = min(len(lines), max(start, int(end_line)))
        return "\n".join(f"{i}: {lines[i - 1]}" for i in range(start, end + 1))

    @tool
    def search_knowledge_base(query: str) -> str:
        """Cari rekomendasi perbaikan di Knowledge Base internal. Hasil JSON: status FOUND (beserta dokumen) atau NOT_FOUND."""
        return json.dumps(kb.search(query), ensure_ascii=False)

    return {
        "check_syntax": check_syntax,
        "run_code": run_code,
        "read_code_lines": read_code_lines,
        "search_knowledge_base": search_knowledge_base,
    }
