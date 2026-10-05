from pathlib import Path
import subprocess
import json
from typing import Protocol, Optional
from pydantic import BaseModel
from .read_file import ToolResult, Tool

class RunLinterArgs(BaseModel):
    path: str

class RunLinterTool:
    name = "run_linter"
    description = "使用ruff对python代码进行静态检查，返回lint问题列表"
    args_schema = RunLinterArgs

    def run(self, **kwargs) -> ToolResult:
        args = RunLinterArgs(** kwargs)
        file_path = Path(args.path)

        # 提前判断文件是否存在
        if not file_path.exists():
            return ToolResult(success=False, content=None, error="文件不存在")

        try:
            proc = subprocess.run(
                ["ruff", "check", str(file_path), "--output-format", "json"],
                capture_output=True,
                text=True,
                encoding="utf-8"
            )
            # ruff 退出码：0=无问题 1=发现问题 2=执行出错；出错信息在 stderr，必须显式报错而非当作"无告警"
            if proc.returncode not in (0, 1):
                return ToolResult(
                    success=False,
                    content="",
                    error=f"ruff执行失败(exit={proc.returncode}): {proc.stderr.strip()[:200]}"
                )
            output = proc.stdout.strip()
            # 处理ruff无报错时stdout为空的特殊情况
            if not output:
                issues = []
            else:
                issues = json.loads(output)

            return ToolResult(
                success=True,
                content=json.dumps(issues, ensure_ascii=False),
                error=None
            )
        except json.JSONDecodeError as e:
            return ToolResult(success=False, content=None, error=f"JSON解析失败: {str(e)}")
        except Exception as e:
            return ToolResult(success=False, content=None, error=str(e))