"""无侵入式事件探针：包装 QwenClient 与工具，把 Agent 行为发往前端，不修改任何现有代码。"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, List

from cra.llm.qwen_client import QwenClient
from cra.tools.read_file import ToolResult

# 事件回调签名：(事件类型, 事件文本) -> None
EventSink = Callable[[str, str], None]


class RecordingQwenClient(QwenClient):
    """QwenClient 子类：在每次 LLM 调用前后发出事件，供前端实时展示推理过程。"""

    def __init__(self, api_key: str, model: str, temperature: float, emit: EventSink):
        super().__init__(api_key, model, temperature)
        self._emit = emit

    def chat(self, messages: List[Dict[str, Any]], tools: Any = None) -> Dict[str, Any]:
        self._emit("llm", "🧠 LLM 推理中，等待通义千问响应…")
        resp = super().chat(messages, tools=tools)
        tool_calls = resp.get("tool_calls") or []
        if tool_calls:
            names = ", ".join(tc["function"]["name"] for tc in tool_calls)
            self._emit("llm", f"🤖 模型自主决策：调用工具 [{names}]")
        else:
            content = (resp.get("content") or "").strip().replace("\n", " ")
            self._emit("llm", f"💬 模型回复：{content[:60]}{'…' if len(content) > 60 else ''}")
        return resp

    def chat_json(self, system: str, user: str) -> List[Dict[str, Any]]:
        self._emit("llm", "📝 渲染阶段：生成结构化审查报告（JSON Mode）…")
        return super().chat_json(system, user)


class RecordingTool:
    """符合 Tool Protocol 的包装器：执行真实工具前后发出事件与耗时。"""

    def __init__(self, tool: Any, emit: EventSink):
        self._tool = tool
        self._emit = emit
        self.name: str = tool.name
        self.description: str = tool.description
        self.args_schema = tool.args_schema

    def run(self, **kwargs: Any) -> ToolResult:
        args_brief = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
        self._emit("tool", f"🔧 执行工具 {self.name}({args_brief})")
        t0 = time.monotonic()
        result: ToolResult = self._tool.run(**kwargs)
        cost = time.monotonic() - t0
        if result.success:
            size = len(result.content or "")
            self._emit("tool", f"✅ {self.name} 完成（耗时 {cost:.2f}s，返回 {size} 字符）")
        else:
            self._emit("tool", f"⚠️ {self.name} 失败：{result.error}（错误已回传给模型自行纠正）")
        return result
