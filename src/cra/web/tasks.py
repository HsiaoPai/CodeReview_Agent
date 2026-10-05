"""审查任务存储与后台执行：每个任务在独立线程中运行 Agent 循环，事件实时累积供前端轮询。"""
from __future__ import annotations

import re
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

from cra.agent.orchestrator import Orchestrator, OrchestratorConfig
from cra.config import load_config
from cra.report.renderer import MarkdownReportRenderer, ReviewFinding
from cra.web.instrument import RecordingQwenClient, RecordingTool

# 上传代码统一落盘到临时目录，避免污染项目目录
UPLOAD_DIR = Path(tempfile.gettempdir()) / "cra_web_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_FILENAME_RE = re.compile(r"^[A-Za-z0-9_\-\.]+\.py$")

DEFAULT_RULES = ["bug", "style", "security", "performance", "readability"]

_LOCK = threading.Lock()
_TASKS: Dict[str, Dict[str, Any]] = {}


def sanitize_filename(name: str) -> str:
    """只允许安全的 .py 文件名，防止路径穿越。"""
    name = (name or "").strip()
    if not _FILENAME_RE.match(name):
        return "upload.py"
    return name


def create_task(code: str, filename: str, rules: List[str]) -> Dict[str, Any]:
    task_id = uuid.uuid4().hex[:12]
    filename = sanitize_filename(filename)
    task_dir = UPLOAD_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    file_path = task_dir / filename
    file_path.write_text(code, encoding="utf-8")

    task: Dict[str, Any] = {
        "id": task_id,
        "status": "running",
        "filename": filename,
        "rules": rules,
        "file_path": str(file_path),
        "events": [],
        "findings": [],
        "markdown": "",
        "error": None,
        "created_at": time.time(),
        "finished_at": None,
    }
    with _LOCK:
        _TASKS[task_id] = task

    worker = threading.Thread(target=_run_review, args=(task_id,), daemon=True)
    worker.start()
    return task


def get_task(task_id: str) -> Dict[str, Any] | None:
    with _LOCK:
        task = _TASKS.get(task_id)
        if task is None:
            return None
        # 返回快照，避免并发修改
        return {
            "id": task["id"],
            "status": task["status"],
            "filename": task["filename"],
            "events": list(task["events"]),
            "findings": list(task["findings"]),
            "error": task["error"],
            "finished_at": task["finished_at"],
        }


def _make_emitter(task: Dict[str, Any]):
    def emit(event_type: str, text: str) -> None:
        with _LOCK:
            task["events"].append({
                "ts": round(time.time() - task["created_at"], 1),
                "type": event_type,
                "text": text,
            })
    return emit


def _run_review(task_id: str) -> None:
    with _LOCK:
        task = _TASKS[task_id]
    emit = _make_emitter(task)

    emit("state", "▶️ 启动 ReAct 循环（COLLECTING_INPUT → PLANNING → TOOL_EXECUTE / LLM_REASON）")
    try:
        cfg = load_config()
        if not cfg.api_key:
            raise RuntimeError("未配置 DASHSCOPE_API_KEY，请在项目根目录 .env 中填写")

        llm = RecordingQwenClient(cfg.api_key, cfg.llm_model, cfg.temperature, emit)
        orch = Orchestrator(cfg=OrchestratorConfig(
            llm_client=llm,
            max_loop=cfg.max_loop,
            max_retry=cfg.max_retries,
            max_tokens=cfg.max_tokens,
        ))
        # 用探针包装真实工具：Agent 决策逻辑不变，只是多了一层事件上报
        orch.tools = [RecordingTool(t, emit) for t in orch.tools]

        raw_findings = orch.review(task["file_path"], task["rules"])

        # Schema 强校验：未通过 Pydantic 校验的意见过滤掉
        valid: List[Dict[str, Any]] = []
        skipped = 0
        for f in raw_findings or []:
            try:
                valid.append(ReviewFinding(**f).model_dump(mode="json"))
            except Exception:
                skipped += 1
        if skipped:
            emit("state", f"⚠️ {skipped} 条模型意见未通过 Schema 校验，已过滤")

        task["findings"] = valid
        task["markdown"] = MarkdownReportRenderer.render_markdown(valid)
        emit("state", f"🏁 审查完成：共 {len(valid)} 条意见（RENDERING_REPORT → 结束）")
        task["status"] = "done"
    except Exception as e:  # noqa: BLE001 —— 顶层兜底，任何异常都转为任务失败状态
        task["error"] = f"{type(e).__name__}: {e}"
        emit("error", f"❌ 审查失败：{task['error']}（已触发 ERROR → RETRY 链路后仍失败）")
        task["status"] = "error"
    finally:
        task["finished_at"] = time.time()
