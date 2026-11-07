"""LLM palsu (skrip) agar alur graf bisa diuji tanpa Ollama."""
import json
import re

from langchain_core.messages import AIMessage, ToolMessage


class FakeLLM:
    """Meniru perilaku ChatOllama: bind_tools + invoke. Peran dikenali dari system prompt."""

    def __init__(self, fix_fn, rewrite_answer="TypeError str int"):
        self.fix_fn = fix_fn  # fungsi: kode_asli -> kode_perbaikan
        self.rewrite_answer = rewrite_answer
        self.calls = []

    def bind_tools(self, tools, **_kw):
        return self

    def invoke(self, messages):
        system = messages[0].content
        self.calls.append(system.split("\n")[0])
        if "Syntax Checker" in system:
            return self._react(messages)
        if "Query Rewriter" in system:
            return AIMessage(content=self.rewrite_answer)
        if "Code Fixer" in system:
            user = messages[1].content
            original = re.search(r"```python\n(.*?)```", user, re.DOTALL).group(1)
            return AIMessage(content=f"```python\n{self.fix_fn(original)}```")
        raise AssertionError(f"prompt tidak dikenal: {system[:40]}")

    @staticmethod
    def _react(messages):
        tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
        if not tool_msgs:
            return AIMessage(
                content="Saya periksa sintaks dulu.",
                tool_calls=[{"name": "check_syntax", "args": {}, "id": "c1", "type": "tool_call"}],
            )
        last = tool_msgs[-1]
        status = json.loads(last.content).get("status")
        if last.name == "check_syntax" and status == "OK":
            return AIMessage(
                content="Sintaks OK, saya jalankan kodenya.",
                tool_calls=[{"name": "run_code", "args": {}, "id": "c2", "type": "tool_call"}],
            )
        return AIMessage(content=json.dumps({"explanation": "ringkasan dari LLM palsu"}))
