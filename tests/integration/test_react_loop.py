# tests/integration/test_react_loop.py
# 使用 FakeQwenClient（脚本化响应序列）驱动 ReAct 主循环，验证状态机、
# 循环上限、LLM 异常重试、以及 RENDERING_REPORT 阶段失败的重试链路。
from typing import Any, Dict, List, Optional
import pytest
from cra.agent.react_loop import AgentContext, AgentState, run_react_loop
from cra.agent.memory import SessionMemory
from cra.llm.qwen_client import LLMRequestError, QwenClient
from cra.tools.read_file import ReadFileTool

EXAMPLE_FILE = "examples/test_case.py"


class FakeQwenClient(QwenClient):
    """Mock LLM 客户端：继承 QwenClient 以通过 AgentContext 的类型校验，
    脚本化返回预设响应；raise_error_at 指定第 N 次调用抛 LLMRequestError。"""

    def __init__(
        self,
        response_sequence: List[Any],
        raise_error_at: Optional[int] = None,
    ):
        super().__init__(api_key="fake-api-key-for-test", model="qwen-turbo", temperature=0.2)
        self.response_sequence = response_sequence
        self.call_count = 0
        self.raise_error_at = raise_error_at

    def _next(self) -> Any:
        if self.raise_error_at is not None and self.call_count == self.raise_error_at:
            self.call_count += 1
            raise LLMRequestError("Fake LLM network error")
        if self.call_count >= len(self.response_sequence):
            raise RuntimeError("FakeQwenClient: response sequence exhausted")
        resp = self.response_sequence[self.call_count]
        self.call_count += 1
        return resp

    def chat(self, messages: List[Dict[str, Any]], tools=None) -> Dict[str, Any]:
        return self._next()

    def chat_json(self, system: str, user: str) -> List[Dict[str, Any]]:
        return self._next()


def _make_ctx(client, tool_list=None, max_loop: int = 8) -> AgentContext:
    return AgentContext(
        memory=SessionMemory(),
        llm_client=client,
        target_file=EXAMPLE_FILE,
        enabled_rules=["bug", "style"],
        tool_list=tool_list or [],
        messages=[{"role": "user", "content": f"审查 {EXAMPLE_FILE}"}],
        max_loop=max_loop,
    )


TOOL_CALL_RESP = {
    "content": "需要读取文件",
    "tool_calls": [
        {
            "id": "call_001",
            "function": {"name": "read_file", "arguments": f'{{"path": "{EXAMPLE_FILE}"}}'},
        }
    ],
}

PLAIN_RESP = {"content": "分析完成，生成报告", "tool_calls": []}

FINDINGS = [
    {
        "file": EXAMPLE_FILE,
        "line_start": 8,
        "line_end": 12,
        "category": "bug",
        "severity": "Major",
        "title": "测试意见",
        "evidence": "dict=[...]",
        "suggestion": "建议",
        "confidence": 0.9,
    }
]


def test_react_full_state_flow():
    """完整状态流转：PLANNING → TOOL_EXECUTE → LLM_REASON → RENDERING_REPORT"""
    fake_client = FakeQwenClient([TOOL_CALL_RESP, PLAIN_RESP, FINDINGS])
    ctx = _make_ctx(fake_client, tool_list=[ReadFileTool()])

    result = run_react_loop(ctx)

    assert ctx.state == AgentState.RENDERING_REPORT
    assert ctx.loop_count == 1
    assert result == FINDINGS
    # read_file 工具真实执行并写入记忆
    assert ctx.memory.tool_call_history[0]["call"]["name"] == "read_file"
    assert ctx.memory.tool_call_history[0]["result"]["success"] is True


def test_react_max_loop_limit():
    """模型连续返回 tool_calls 时，loop_count 累加，max_loop=8 强制退出不死循环"""
    fake_client = FakeQwenClient([TOOL_CALL_RESP] * 20)
    ctx = _make_ctx(fake_client, tool_list=[ReadFileTool()], max_loop=8)

    result = run_react_loop(ctx)

    assert ctx.loop_count == 8
    assert ctx.raw_findings == []


def test_react_llm_error_retry(monkeypatch):
    """PLANNING 阶段 LLM 异常 → ERROR → RETRY → PLANNING，retry_count 累加"""
    # 加速测试：跳过指数退避的真实 sleep
    monkeypatch.setattr("cra.agent.react_loop.time.sleep", lambda s: None)
    fake_client = FakeQwenClient(
        [None, PLAIN_RESP, PLAIN_RESP, FINDINGS],
        raise_error_at=0,
    )
    ctx = _make_ctx(fake_client)

    result = run_react_loop(ctx)

    assert ctx.retry_count == 1
    assert ctx.state == AgentState.RENDERING_REPORT
    assert result == FINDINGS


def test_react_render_report_retry(monkeypatch):
    """RENDERING_REPORT 阶段 chat_json 失败 → ERROR → RETRY → 重新走完流程"""
    monkeypatch.setattr("cra.agent.react_loop.time.sleep", lambda s: None)
    # 消费序列：PLANNING(chat) → LLM_REASON(chat) → chat_json 抛异常
    #            → RETRY → PLANNING(chat) → LLM_REASON(chat) → chat_json 成功
    fake_client = FakeQwenClient(
        [PLAIN_RESP, PLAIN_RESP, None, PLAIN_RESP, PLAIN_RESP, FINDINGS],
        raise_error_at=2,
    )
    ctx = _make_ctx(fake_client)

    result = run_react_loop(ctx)

    assert ctx.retry_count == 1
    assert result == FINDINGS


def test_react_tool_args_invalid_json():
    """模型返回非法 JSON arguments 时降级为 error 回传，流程不崩溃"""
    bad_args_resp = {
        "content": "调用工具",
        "tool_calls": [
            {
                "id": "call_bad",
                "function": {"name": "read_file", "arguments": "{path: 不合法的json"},
            }
        ],
    }
    fake_client = FakeQwenClient([bad_args_resp, PLAIN_RESP, []])
    ctx = _make_ctx(fake_client, tool_list=[ReadFileTool()])

    result = run_react_loop(ctx)

    assert ctx.loop_count == 1
    assert result == []
    rec = ctx.memory.tool_call_history[0]
    assert rec["result"]["success"] is False
    assert "非法" in rec["result"]["error"]
