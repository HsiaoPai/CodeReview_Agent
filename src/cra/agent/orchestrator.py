from __future__ import annotations
import traceback
from pathlib import Path
from typing import List
from pydantic import BaseModel
from cra.agent.memory import SessionMemory
from cra.agent.react_loop import AgentContext, run_react_loop
from cra.llm.qwen_client import QwenClient
from cra.tools.read_file import ReadFileTool
from cra.tools.ast_parse import AstParseTool
from cra.tools.run_linter import RunLinterTool


class OrchestratorConfig(BaseModel):
    model_config = {
        "arbitrary_types_allowed": True
    }
    llm_client: QwenClient
    max_loop: int = 8
    max_retry: int = 3
    max_tokens: int = 3000


class Orchestrator:
    def __init__(self, cfg: OrchestratorConfig):
        self.cfg = cfg
        self.tools = [
            ReadFileTool(),
            AstParseTool(),
            RunLinterTool()
        ]

    def review(self, file_path: str, rules: List[str]) -> List[dict]:
        fp = Path(file_path)
        if not fp.exists():
            raise FileNotFoundError(f"{file_path}不存在")
        mem = SessionMemory()

        # 初始化对话消息，告诉Agent任务目标
        init_messages = [
            {
                "role": "system",
                "content": "你是代码审查Agent。你需要调用工具读取目标Python文件，解析AST，执行linter，收集代码问题，最后输出审查结果。"
            },
            {
                "role": "user",
                "content": f"请审查文件：{str(fp)}，启用规则：{','.join(rules)}。先调用read_file读取文件源码。"
            }
        ]

        ctx = AgentContext(
            memory=mem,
            llm_client=self.cfg.llm_client,
            target_file=str(fp),
            enabled_rules=rules,
            tool_list=self.tools,
            messages=init_messages,
            max_loop=self.cfg.max_loop,
            max_retry=self.cfg.max_retry,
            max_tokens=self.cfg.max_tokens,
        )
        try:
            findings = run_react_loop(ctx)
        except Exception:
            print("==== run_react_loop 发生异常 ====")
            print(traceback.format_exc())
            raise
        return findings
