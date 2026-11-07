"""Perakitan StateGraph: Supervisor -> Worker, Safety Gate (interrupt_before) + MemorySaver."""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from config import SETTINGS
from knowledge_base import KnowledgeBase
from nodes import (
    apply_patch_node,
    make_code_fixer,
    make_rag_specialist,
    make_supervisor,
    make_syntax_checker,
    route_from_supervisor,
)
from state import AgentState


def build_graph(llm, settings=SETTINGS, kb=None, checkpointer=None):
    kb = kb or KnowledgeBase(threshold=settings.kb_threshold, top_k=settings.kb_top_k)

    builder = StateGraph(AgentState)
    builder.add_node("supervisor", make_supervisor(settings))
    builder.add_node("syntax_checker", make_syntax_checker(llm, kb, settings))
    builder.add_node("rag_specialist", make_rag_specialist(llm, kb, settings))
    builder.add_node("code_fixer", make_code_fixer(llm, settings))
    builder.add_node("apply_patch", apply_patch_node)

    builder.add_edge(START, "supervisor")
    # Conditional routing dinamis: tujuan ditentukan Supervisor dari isi state
    builder.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "syntax_checker": "syntax_checker",
            "rag_specialist": "rag_specialist",
            "code_fixer": "code_fixer",
            "apply_patch": "apply_patch",
            "finish": END,
        },
    )
    # Setiap worker melapor kembali ke Supervisor
    for worker in ("syntax_checker", "rag_specialist", "code_fixer"):
        builder.add_edge(worker, "supervisor")
    builder.add_edge("apply_patch", END)

    return builder.compile(
        checkpointer=checkpointer or MemorySaver(),  # menyimpan state saat graf berhenti
        interrupt_before=["apply_patch"],  # Safety Gate: berhenti SEBELUM aksi berisiko
    )
