from __future__ import annotations
import hashlib
from typing import List, Dict, Any
from pydantic import BaseModel
import tiktoken

class FileReadRecord(BaseModel):
    path: str
    content: str
    md5: str

def calc_text_token(text: str) -> int:
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))

class SessionMemory(BaseModel):
    """短期会话内存记忆，单次review任务使用"""
    read_file_hashes: Dict[str, str] = {}
    conclusions: List[Dict[str, Any]] = []
    tool_call_history: List[Dict[str, Any]] = []
    read_file_history: List[FileReadRecord] = []
    max_tool_history: int = 5

    def add_read_file(self, path: str, content: str):
        h = hashlib.md5(content.encode("utf-8")).hexdigest()
        self.read_file_hashes[path] = h
        self.read_file_history.append(FileReadRecord(
            path=path, content=content, md5=h
        ))

    def add_conclusion(self, finding: Dict):
        self.conclusions.append(finding)

    def append_tool_record(self, call_info: Dict, result: Dict):
        rec = {"call": call_info, "result": result}
        self.tool_call_history.append(rec)
        if len(self.tool_call_history) > self.max_tool_history:
            self.tool_call_history.pop(0)

def truncate_messages(messages: List[Dict], max_total_tokens: int = 3000) -> List[Dict]:
    """上下文裁剪，保留system，删除较早的tool返回"""
    def _tokens(msgs: List[Dict]) -> int:
        return sum(calc_text_token(m.get("content") or "") for m in msgs)

    total = _tokens(messages)
    if total <= max_total_tokens:
        return messages.copy()
    system_msg = [m for m in messages if m["role"] == "system"]
    others = [m for m in messages if m["role"] != "system"]
    while others and _tokens(system_msg + others) > max_total_tokens:
        others.pop(0)
    return system_msg + others
