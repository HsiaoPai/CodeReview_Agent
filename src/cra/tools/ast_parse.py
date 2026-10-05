from __future__ import annotations
import ast
import json
from pathlib import Path
from typing import Protocol, List, Dict, Any
from pydantic import BaseModel

from .read_file import Tool, ToolResult

class AstParseArgs(BaseModel):
    path: str

class _AstVisitor(ast.NodeVisitor):
    def __init__(self):
        self.classes: List[Dict[str, Any]] = []
        self.functions: List[Dict[str, Any]] = []

    def visit_ClassDef(self, node: ast.ClassDef):
        bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
        self.classes.append({
            "name": node.name,
            "lineno": node.lineno,
            "end_lineno": node.end_lineno,
            "bases": bases
        })
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        calls: List[str] = []
        for sub_node in ast.walk(node):
            if isinstance(sub_node, ast.Call) and isinstance(sub_node.func, ast.Name):
                calls.append(sub_node.func.id)
        self.functions.append({
            "name": node.name,
            "lineno": node.lineno,
            "end_lineno": node.end_lineno,
            "calls": list(set(calls)),
            "args": [arg.arg for arg in node.args.args]
        })
        self.generic_visit(node)

class AstParseTool:
    name = "ast_parse"
    description = "读取Python文件，解析AST，返回类、函数、调用关系与行号，用于快速理解代码结构，不需要读取完整源码"
    args_schema = AstParseArgs

    def run(self,** kwargs) -> ToolResult:
        args = AstParseArgs(**kwargs)
        file_path = Path(args.path)
        try:
            src = file_path.read_text(encoding="utf-8")
            tree = ast.parse(src)
            visitor = _AstVisitor()
            visitor.visit(tree)
            payload = {
                "file": str(file_path),
                "classes": visitor.classes,
                "functions": visitor.functions
            }
            return ToolResult(
                success=True,
                content=json.dumps(payload, ensure_ascii=False), 
                error=""
            )
        except SyntaxError as e:
            return ToolResult(success=False, content="", error=f"Python语法错误 line:{e.lineno}: {e.msg}")
        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))

