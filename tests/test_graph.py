"""Tes alur graf end-to-end (offline, LLM palsu). Jalankan: python -m pytest -q"""
import dataclasses
import shutil
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from analysis import run_python_file, syntax_check  # noqa: E402
from config import SETTINGS  # noqa: E402
from fake_llm import FakeLLM  # noqa: E402
from graph import build_graph  # noqa: E402
from knowledge_base import KnowledgeBase  # noqa: E402

FIXES = {
    "bug_syntax.py": lambda c: c.replace("(angka)\n", "(angka):\n", 1),
    "bug_runtime.py": lambda c: c.replace(
        "    total = 0\n", "    if len(angka) == 0:\n        return 0\n    total = 0\n", 1
    ),
    "bug_rewrite.py": lambda c: c.replace("+ umur +", "+ str(umur) +"),
}


@pytest.fixture
def work(tmp_path):
    def _copy(name):
        dst = tmp_path / name
        shutil.copy(ROOT / "samples" / name, dst)
        return dst

    return _copy


def run(graph, path, thread=None):
    config = {"configurable": {"thread_id": thread or str(uuid.uuid4())}, "recursion_limit": SETTINGS.recursion_limit}
    graph.invoke(
        {
            "target_path": str(path),
            "original_code": path.read_text(encoding="utf-8"),
            "steps": 0,
            "fix_attempts": 0,
            "trace": [],
        },
        config,
    )
    return config


def test_tools_pure_functions(work):
    assert syntax_check(work("bug_syntax.py").read_text())["status"] == "SYNTAX_ERROR"
    r = run_python_file(work("bug_runtime.py"))
    assert r["status"] == "RUNTIME_ERROR" and r["error_type"] == "ZeroDivisionError" and r["line"] == 5


def test_kb_found_and_not_found():
    kb = KnowledgeBase(threshold=SETTINGS.kb_threshold)
    assert kb.search("ZeroDivisionError: division by zero")["status"] == "FOUND"
    assert kb.search("xyzzy foobar quux")["status"] == "NOT_FOUND"


@pytest.mark.parametrize("sample", ["bug_syntax.py", "bug_runtime.py"])
def test_interrupt_before_apply_patch_and_resume(work, sample):
    path = work(sample)
    original = path.read_text()
    graph = build_graph(FakeLLM(FIXES[sample]))
    config = run(graph, path)

    # 1) Graf berhenti SEBELUM apply_patch, file belum berubah, state tersimpan
    snap = graph.get_state(config)
    assert snap.next == ("apply_patch",)
    assert path.read_text() == original
    assert snap.values["fix_valid"] is True and snap.values["fixed_code"]

    # 2) Manusia menyetujui -> lanjut dari checkpoint yang sama
    graph.update_state(config, {"human_approved": True}, as_node="supervisor")
    graph.invoke(None, config)
    final = graph.get_state(config).values
    assert final["patch_status"] == "APPLIED"
    assert path.read_text() == final["fixed_code"] != original
    assert path.with_name(path.name + ".bak").read_text() == original
    assert run_python_file(path)["status"] == "OK"


def test_human_rejects_patch(work):
    path = work("bug_runtime.py")
    original = path.read_text()
    graph = build_graph(FakeLLM(FIXES["bug_runtime.py"]))
    config = run(graph, path)
    graph.update_state(config, {"human_approved": False}, as_node="supervisor")
    graph.invoke(None, config)
    assert graph.get_state(config).values["patch_status"] == "REJECTED"
    assert path.read_text() == original


def test_query_rewriting_triggered_on_not_found(work):
    path = work("bug_rewrite.py")
    graph = build_graph(FakeLLM(FIXES["bug_rewrite.py"]))
    config = run(graph, path)
    values = graph.get_state(config).values
    queries = values["kb_queries"]
    assert len(queries) >= 2 and queries[0] != queries[1]
    assert values["kb_status"] == "FOUND" and values["kb_docs"][0]["doc_id"] == "KB-005"
    trace = "\n".join(values["trace"])
    assert "NOT_FOUND" in trace and "Query Rewriting" in trace


def test_rewriting_falls_back_when_llm_repeats_query(work):
    path = work("bug_rewrite.py")
    same = 'TypeError: can only concatenate str (not "int") to str'
    graph = build_graph(FakeLLM(FIXES["bug_rewrite.py"], rewrite_answer=same))
    values = graph.get_state(run(graph, path)).values
    assert len(set(values["kb_queries"])) == len(values["kb_queries"])  # tidak ada query berulang
    assert values["kb_status"] == "FOUND"


def test_no_infinite_loop_when_fix_never_valid(work):
    path = work("bug_runtime.py")
    original = path.read_text()
    graph = build_graph(FakeLLM(lambda c: c))  # fixer selalu mengembalikan kode yang sama
    config = run(graph, path)
    snap = graph.get_state(config)
    assert snap.next == ()  # selesai, TIDAK menuju apply_patch
    assert snap.values["final_status"] == "FIX_FAILED"
    assert snap.values["fix_attempts"] == SETTINGS.max_fix_attempts
    assert path.read_text() == original


def test_supervisor_step_guard(work):
    tiny = dataclasses.replace(SETTINGS, max_supervisor_steps=2)
    path = work("bug_runtime.py")
    graph = build_graph(FakeLLM(FIXES["bug_runtime.py"]), tiny)
    values = graph.get_state(run(graph, path)).values
    assert values["final_status"] == "STEP_LIMIT"


def test_clean_code_ends_without_interrupt(work):
    path = work("bug_clean.py")
    graph = build_graph(FakeLLM(lambda c: c))
    snap = graph.get_state(run(graph, path))
    assert snap.next == () and snap.values["final_status"] == "NO_BUG"


def test_patch_aborted_if_file_changed_during_review(work):
    path = work("bug_runtime.py")
    graph = build_graph(FakeLLM(FIXES["bug_runtime.py"]))
    config = run(graph, path)
    path.write_text(path.read_text() + "# diubah orang lain\n")
    graph.update_state(config, {"human_approved": True}, as_node="supervisor")
    graph.invoke(None, config)
    assert graph.get_state(config).values["patch_status"] == "ABORTED"
