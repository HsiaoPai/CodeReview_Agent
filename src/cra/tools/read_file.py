from pathlib import Path
from typing import Protocol, Optional
from pydantic import BaseModel

class ToolResult(BaseModel):
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None

class Tool(Protocol):
    name: str
    description: str
    args_schema: type[BaseModel]
    def run(self,** kwargs) -> ToolResult: ...

class ReadFileArgs(BaseModel):
    path: str

class ReadFileTool:
    name = "read_file"
    description = "读取本地python源代码文件，获取文件全部内容，当需要审查磁盘上代码文件时调用。参数path为文件相对路径"
    args_schema = ReadFileArgs

    def run(self, **kwargs) -> ToolResult:
        args = ReadFileArgs(** kwargs)
        file_path = Path(args.path)

        # 新增：提前判断文件不存在，统一返回固定错误信息
        if not file_path.exists():
            return ToolResult(success=False, content=None, error="文件不存在")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
            return ToolResult(success=True, content=text)
        except Exception as e:
            return ToolResult(success=False, content=None, error=str(e))