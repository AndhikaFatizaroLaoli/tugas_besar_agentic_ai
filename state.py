"""State bersama untuk seluruh node pada StateGraph."""
import operator
from typing import Annotated, Optional, TypedDict


class AgentState(TypedDict, total=False):
    # input
    target_path: str
    original_code: str

    # hasil Syntax Checker Worker
    diagnosis: dict  # {status, error_type, message, line, explanation}

    # hasil RAG Specialist Worker
    kb_done: bool
    kb_status: str  # "FOUND" | "NOT_FOUND"
    kb_docs: list  # [{doc_id, title, score, content}]
    kb_queries: list  # riwayat query (termasuk hasil Query Rewriting)

    # hasil Code Fixer Worker
    fixed_code: str
    fix_valid: Optional[bool]
    fix_report: str
    fix_attempts: int

    # Human-in-the-Loop
    human_approved: Optional[bool]

    # kontrol alur
    next: str  # keputusan terakhir Supervisor
    steps: int  # jumlah giliran Supervisor (guard infinite loop)
    patch_status: str
    final_status: str

    # Trace Log: setiap node menambahkan baris; reducer menggabungkan antar node
    trace: Annotated[list, operator.add]
