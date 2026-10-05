from __future__ import annotations
from typing import List, Dict
from pydantic import BaseModel, Field
from enum import Enum


class Severity(str, Enum):
    Blocker = "Blocker"
    Major = "Major"
    Minor = "Minor"
    Info = "Info"


class Category(str, Enum):
    bug = "bug"
    style = "style"
    security = "security"
    performance = "performance"
    readability = "readability"
    design = "design"


class ReviewFinding(BaseModel):
    file: str
    line_start: int
    line_end: int
    category: Category
    severity: Severity
    title: str
    evidence: str
    suggestion: str
    confidence: float = Field(ge=0.0, le=1.0, description="置信度必须0~1之间")


TERM_COLOR = {
    "Blocker": "\033[91m",
    "Major": "\033[38;5;208m",
    "Minor": "\033[93m",
    "Info": "\033[94m",
    "reset": "\033[0m"
}

# 修改 MarkdownReportRenderer
class MarkdownReportRenderer:
    @staticmethod
    def render_markdown(findings: List[Dict]) -> str:
        items = [ReviewFinding(**x) for x in findings]
        md = "# Code Review Agent 审查报告\n\n"
        for f in items:
            # ✅ 用 .value 获取枚举原始字符串
            md += f"## [{f.severity.value}] {f.title}\n"
            md += f"- 文件：`{f.file}` 行号 {f.line_start}-{f.line_end}\n"
            md += f"- 类别：{f.category.value} 置信度:{f.confidence:.2f}\n"
            md += f"**证据**\n```\n{f.evidence}\n```\n"
            md += f"**修复建议**\n{f.suggestion}\n\n"
        return md

    @staticmethod
    def render_terminal(findings: List[Dict]) -> str:
        out = ""
        items = [ReviewFinding(**x) for x in findings]
        for f in items:
            # ✅ 这里同样用 .value
            sev_str = f.severity.value
            c = TERM_COLOR.get(sev_str, "")
            reset = TERM_COLOR["reset"]
            out += f"{c}[{sev_str}] {f.title}{reset}\n"
            out += f"  文件 {f.file} L{f.line_start}-{f.line_end} | {f.category.value}\n"
            out += f"  建议：{f.suggestion}\n\n"
        return out

