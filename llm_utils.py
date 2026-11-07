"""Utilitas LLM lokal (Ollama): pembuatan model, retry, dan parsing output yang toleran."""
import json
import re
import urllib.error
import urllib.request


class LLMError(RuntimeError):
    """LLM gagal setelah semua retry."""


def get_llm(settings):
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=settings.model,
        base_url=settings.base_url,
        temperature=settings.temperature,
    )


def check_ollama(settings):
    """Pastikan server Ollama hidup dan model tersedia. Return (ok, pesan)."""
    try:
        with urllib.request.urlopen(f"{settings.base_url}/api/tags", timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return False, (
            f"Tidak bisa terhubung ke Ollama di {settings.base_url}. "
            "Jalankan 'ollama serve' terlebih dahulu."
        )
    names = [m.get("name", "") for m in data.get("models", [])]
    if not any(n == settings.model or n.startswith(settings.model + ":") for n in names):
        return False, (
            f"Model '{settings.model}' belum tersedia. Jalankan: ollama pull {settings.model}"
        )
    return True, "Ollama siap."


def safe_invoke(llm, messages, retries: int = 2):
    """Panggil LLM dengan retry. Error koneksi / parsing tool-call dari Ollama ditangani di sini."""
    last = None
    for _ in range(retries + 1):
        try:
            return llm.invoke(messages)
        except Exception as exc:  # noqa: BLE001 - Ollama melempar beragam tipe error
            last = exc
    raise LLMError(f"LLM gagal setelah {retries + 1} percobaan: {last}") from last


def extract_json(text: str):
    """Ambil objek JSON pertama dari teks (toleran terhadap code fence & teks tambahan)."""
    if not text:
        return None
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start : i + 1])
                        return obj if isinstance(obj, dict) else None
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None


def extract_code_block(text: str):
    """Ambil blok kode ```python ...``` pertama; None jika tidak ada."""
    if not text:
        return None
    m = re.search(r"```(?:python|py)?[ \t]*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).rstrip() + "\n"
    return None
