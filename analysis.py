"""Fungsi murni untuk menganalisis & mengeksekusi kode (dipakai tools dan validasi)."""
import ast
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def syntax_check(code: str) -> dict:
    """Cek sintaks dengan parser Python (tanpa mengeksekusi kode)."""
    try:
        ast.parse(code)
        return {"status": "OK"}
    except SyntaxError as e:  # termasuk IndentationError & TabError
        return {
            "status": "SYNTAX_ERROR",
            "error_type": type(e).__name__,
            "message": e.msg,
            "line": e.lineno,
            "offset": e.offset,
            "text": (e.text or "").rstrip(),
        }


_FRAME_RE = re.compile(r'File "(?P<file>[^"]+)", line (?P<line>\d+)')
_ERR_RE = re.compile(r"^(?P<type>[A-Za-z_][\w.]*(?:Error|Exception|Exit|Interrupt)):?\s*(?P<msg>.*)$")


def parse_traceback(stderr: str, script_path: str) -> dict:
    """Ambil tipe error, pesan, dan baris (frame terakhir milik script) dari traceback."""
    lines = [ln for ln in stderr.strip().splitlines() if ln.strip()]
    err_type, message = "RuntimeError", (lines[-1].strip() if lines else "unknown error")
    for ln in reversed(lines):
        m = _ERR_RE.match(ln.strip())
        if m:
            err_type, message = m.group("type"), m.group("msg").strip()
            break
    script_name = Path(script_path).name
    line_no = None
    for ln in lines:
        m = _FRAME_RE.search(ln)
        if m and Path(m.group("file")).name == script_name:
            line_no = int(m.group("line"))
    return {"error_type": err_type, "message": message, "line": line_no}


def run_python_file(path, timeout: int = 5, cwd=None, extra_pythonpath=None) -> dict:
    """Jalankan file Python di subprocess (timeout, tanpa stdin).

    PERHATIAN: ini mengeksekusi kode target. Cocok untuk kode tugas/latihan milik
    sendiri, bukan kode tak tepercaya.
    """
    env = dict(os.environ)
    if extra_pythonpath:
        env["PYTHONPATH"] = str(extra_pythonpath) + os.pathsep + env.get("PYTHONPATH", "")
    try:
        proc = subprocess.run(
            [sys.executable, "-B", str(path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            cwd=str(cwd or Path(path).parent),
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "RUNTIME_ERROR",
            "error_type": "TimeoutError",
            "message": f"Eksekusi melebihi {timeout} detik (kemungkinan infinite loop)",
            "line": None,
        }
    if proc.returncode == 0:
        return {"status": "OK", "stdout": proc.stdout[-500:]}
    return {"status": "RUNTIME_ERROR", **parse_traceback(proc.stderr, str(path))}


def validate_fix(candidate: str, original: str, target_path: str, timeout: int = 5):
    """Validasi kode perbaikan: berubah, sintaks valid, dan berjalan tanpa error.

    Return (valid: bool, report: str).
    """
    if candidate.strip() == original.strip():
        return False, "Kode hasil perbaikan identik dengan kode asli (tidak ada perubahan)."
    sc = syntax_check(candidate)
    if sc["status"] != "OK":
        return False, f"Masih SyntaxError baris {sc['line']}: {sc['message']}"
    target_dir = Path(target_path).resolve().parent
    with tempfile.TemporaryDirectory() as tmp:
        cand_path = Path(tmp) / "candidate.py"
        cand_path.write_text(candidate, encoding="utf-8")
        rr = run_python_file(cand_path, timeout, cwd=target_dir, extra_pythonpath=target_dir)
    if rr["status"] != "OK":
        return False, (
            f"Masih {rr['error_type']} (baris {rr['line']}): {rr['message']}"
        )
    return True, "Sintaks valid dan kode berjalan tanpa error."
