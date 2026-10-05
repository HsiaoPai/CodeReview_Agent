from __future__ import annotations
import json
import time
from pathlib import Path
from enum import Enum
from typing import List, Dict, Any
from pydantic import BaseModel
from cra.llm.qwen_client import QwenClient, LLMRequestError
from cra.llm.prompt_loader import render_prompt
from cra.agent.memory import SessionMemory, truncate_messages
from cra.tools.read_file import ToolResult


class AgentState(str, Enum):
    IDLE = "IDLE"
    COLLECTING_INPUT = "COLLECTING_INPUT"
    PLANNING = "PLANNING"
    TOOL_EXECUTE = "TOOL_EXECUTE"
    LLM_REASON = "LLM_REASON"
    RENDERING_REPORT = "RENDERING_REPORT"
    ERROR = "ERROR"
    RETRY = "RETRY"


class AgentContext(BaseModel):
    model_config = {
        "arbitrary_types_allowed": True
    }
    state: AgentState = AgentState.IDLE
    memory: SessionMemory
    llm_client: QwenClient
    target_file: str
    enabled_rules: List[str]
    messages: List[Dict[str, Any]] = []
    tool_list: List[Any]
    loop_count: int = 0
    max_loop: int = 8
    retry_count: int = 0
    max_retry: int = 3
    max_tokens: int = 3000
    raw_findings: List[Dict[str, Any]] = []


def _tools_to_fc_schema(tool_list: List[Any]) -> List[Dict[str, Any]]:
    """把本地 Tool 列表转换为 DashScope Function Calling 工具描述"""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.args_schema.model_json_schema()
            }
        }
        for t in tool_list
    ]


def _dispatch_tool(tool_list: List[Any], tool_name: str, args: Dict) -> ToolResult:
    tool_map = {t.name: t for t in tool_list}
    if tool_name not in tool_map:
        return ToolResult(success=False, content="", error=f"不存在工具 {tool_name}")
    inst = tool_map[tool_name]
    return inst.run(**args)


def _extract_tool_results(memory: SessionMemory, tool_name: str) -> str:
    """从记忆中提取指定工具成功执行的结果，拼接为文本（用于最终 Prompt 注入）"""
    records = [
        rec["result"].get("content") or ""
        for rec in memory.tool_call_history
        if rec["call"].get("name") == tool_name and rec["result"].get("success")
    ]
    return "\n".join(str(c) for c in records)


def run_react_loop(ctx: AgentContext) -> List[Dict[str, Any]]:
    ctx.state = AgentState.COLLECTING_INPUT
    while True:
        if ctx.loop_count >= ctx.max_loop:
            break
        if ctx.state == AgentState.COLLECTING_INPUT:
            ctx.state = AgentState.PLANNING

        elif ctx.state == AgentState.PLANNING:
            try:
                resp_msg = ctx.llm_client.chat(
                    messages=ctx.messages,
                    tools=_tools_to_fc_schema(ctx.tool_list)
                )
                ctx.messages.append(resp_msg)
                if resp_msg.get("tool_calls"):
                    ctx.state = AgentState.TOOL_EXECUTE
                else:
                    ctx.state = AgentState.LLM_REASON
            except LLMRequestError:
                ctx.state = AgentState.ERROR

        elif ctx.state == AgentState.TOOL_EXECUTE:
            for tc in ctx.messages[-1].get("tool_calls", []):
                fn = tc["function"]
                # 模型偶发返回非法 JSON arguments：降级为 error 回传，让模型自行纠正
                try:
                    arg_dict = json.loads(fn["arguments"])
                    if not isinstance(arg_dict, dict):
                        raise ValueError("arguments 必须是 JSON 对象")
                except (json.JSONDecodeError, ValueError, TypeError) as e:
                    arg_dict = {}
                    tool_res = ToolResult(
                        success=False,
                        content="",
                        error=f"工具参数非法 JSON: {e}，请重新输出合法的 arguments"
                    )
                else:
                    tool_res = _dispatch_tool(ctx.tool_list, fn["name"], arg_dict)

                ctx.memory.append_tool_record(
                    {"name": fn["name"], "args": arg_dict},
                    tool_res.model_dump()
                )
                ctx.messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_res.model_dump_json()
                })
            ctx.loop_count += 1
            ctx.messages = truncate_messages(
                ctx.messages, max_total_tokens=ctx.max_tokens
            )
            ctx.state = AgentState.LLM_REASON

        elif ctx.state == AgentState.LLM_REASON:
            try:
                resp_msg = ctx.llm_client.chat(
                    messages=ctx.messages,
                    tools=_tools_to_fc_schema(ctx.tool_list)
                )
            except LLMRequestError:
                ctx.state = AgentState.ERROR
                continue
            ctx.messages.append(resp_msg)
            if resp_msg.get("tool_calls"):
                ctx.state = AgentState.TOOL_EXECUTE
            else:
                ctx.state = AgentState.RENDERING_REPORT

        elif ctx.state == AgentState.RENDERING_REPORT:
            lint_result = _extract_tool_results(ctx.memory, "run_linter")
            ast_result = _extract_tool_results(ctx.memory, "ast_parse")
            # 注入源码：ast/lint 证据缺失时模型仍能基于源码本身审查，避免"零证据"返回空报告
            try:
                source_code = Path(ctx.target_file).read_text(encoding="utf-8")
            except Exception:
                source_code = "（源码读取失败）"

            sys_p = render_prompt("system.j2")
            user_p = render_prompt(
                "task_review.j2",
                file_path=ctx.target_file,
                enabled_categories=ctx.enabled_rules,
                ast_result=ast_result,
                lint_result=lint_result,
                source_code=source_code
            )
            try:
                out_json = ctx.llm_client.chat_json(system=sys_p, user=user_p)
                ctx.raw_findings = out_json
                break
            except LLMRequestError:
                # 失败进入 ERROR → RETRY 链路，而非直接抛出
                ctx.state = AgentState.ERROR

        elif ctx.state == AgentState.ERROR:
            if ctx.retry_count < ctx.max_retry:
                ctx.retry_count += 1
                ctx.state = AgentState.RETRY
            else:
                break

        elif ctx.state == AgentState.RETRY:
            # 指数退避：sleep(2^n)；测试中可 monkeypatch time.sleep 加速
            time.sleep(2 ** ctx.retry_count)
            ctx.state = AgentState.PLANNING
        else:
            break
    return ctx.raw_findings
