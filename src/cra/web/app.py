"""FastAPI Web 界面：提交代码 → 实时查看 Agent 状态流转 → 展示结构化审查报告。

启动方式：
    pip install -e ".[web]"
    python -m cra.web
然后浏览器访问 http://127.0.0.1:8000
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field

from cra.config import load_config
from cra.web import tasks as task_store

app = FastAPI(title="Code Review Agent", version="0.1.0",
              description="基于通义千问 + 自研 ReAct 循环的代码审查 Agent Web 界面")

_STATIC_DIR = Path(__file__).resolve().parent / "static"
# 项目根目录：src/cra/web/app.py → 上溯 3 级
_PROJECT_ROOT = Path(__file__).resolve().parents[3]

_EXAMPLES = {
    "test_case.py": "正常样例（内置若干真实代码问题）",
    "bad_case.py": "语法错误样例（边界测试）",
    "empty.py": "空文件样例（边界测试）",
}


class ReviewRequest(BaseModel):
    code: str = Field(min_length=0)
    filename: str = "upload.py"
    rules: List[str] = Field(default_factory=lambda: list(task_store.DEFAULT_RULES))


@app.get("/", response_class=HTMLResponse, tags=["page"])
def index() -> str:
    return (_STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/api/health", tags=["api"])
def health() -> dict:
    cfg = load_config()
    return {"ok": True, "api_key_configured": bool(cfg.api_key), "model": cfg.llm_model}


@app.get("/api/examples/{name}", tags=["api"])
def get_example(name: str) -> dict:
    if name not in _EXAMPLES:
        raise HTTPException(status_code=404, detail="样例不存在")
    path = _PROJECT_ROOT / "examples" / name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"样例文件缺失：{name}")
    return {"filename": name, "code": path.read_text(encoding="utf-8")}


@app.post("/api/review", tags=["api"])
def start_review(req: ReviewRequest) -> dict:
    if not req.code.strip():
        raise HTTPException(status_code=400, detail="代码内容为空，请输入或粘贴 Python 代码")
    rules = [r for r in req.rules if r] or list(task_store.DEFAULT_RULES)
    task = task_store.create_task(req.code, req.filename, rules)
    return {"task_id": task["id"], "filename": task["filename"], "rules": rules}


@app.get("/api/tasks/{task_id}", tags=["api"])
def get_task(task_id: str) -> dict:
    task = task_store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@app.get("/api/tasks/{task_id}/report.md", response_class=PlainTextResponse, tags=["api"])
def download_report(task_id: str) -> PlainTextResponse:
    snapshot = task_store.get_task(task_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if snapshot["status"] != "done":
        raise HTTPException(status_code=409, detail="任务尚未完成")
    with task_store._LOCK:
        markdown = task_store._TASKS[task_id]["markdown"]
    return PlainTextResponse(markdown, media_type="text/markdown; charset=utf-8")
