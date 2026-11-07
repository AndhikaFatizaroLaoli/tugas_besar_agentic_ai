"""Konfigurasi terpusat. Semua nilai bisa di-override lewat environment variable."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # --- Ollama lokal ---
    model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
    base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    temperature: float = 0.0  # deterministik -> tool calling & JSON lebih stabil
    llm_retries: int = 2  # retry otomatis jika Ollama error / format salah

    # --- ReAct (Syntax Checker Worker) ---
    max_react_steps: int = 6

    # --- Agentic RAG ---
    kb_threshold: float = 0.8  # skor cakupan minimum agar dianggap FOUND
    kb_top_k: int = 2
    max_rewrites: int = 2  # jumlah maksimum Query Rewriting setelah NOT_FOUND

    # --- Code Fixer ---
    max_fix_attempts: int = 3

    # --- Supervisor / anti infinite-loop ---
    max_supervisor_steps: int = 12
    recursion_limit: int = 40  # batas keras LangGraph (lapisan pengaman kedua)

    # --- Eksekusi kode target ---
    run_timeout: int = 5  # detik


SETTINGS = Settings()
