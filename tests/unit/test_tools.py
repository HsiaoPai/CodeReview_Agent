# tests/unit/test_tools.py
import json
from pathlib import Path
from cra.tools.read_file import ReadFileTool
from cra.tools.ast_parse import AstParseTool
from cra.tools.run_linter import RunLinterTool

# 测试文件路径
TEST_CASE_PATH = Path("examples/test_case.py")
BAD_CASE_PATH = Path("examples/bad_case.py")
NOT_EXIST_PATH = Path("examples/never_exist.py")

def test_readfile_normal():
    """ReadFileTool 正常读取文件"""
    tool = ReadFileTool()
    res = tool.run(path=str(TEST_CASE_PATH))
    assert res.success is True
    assert res.content != ""

def test_readfile_not_found():
    """ReadFileTool 文件不存在"""
    tool = ReadFileTool()
    res = tool.run(path=str(NOT_EXIST_PATH)) # 修复：使用不存在路径
    assert res.success is False
    assert res.error != ""

def test_astparse_normal():
    """AstParseTool 解析合法Python文件"""
    tool = AstParseTool()
    res = tool.run(path=str(TEST_CASE_PATH))
    assert res.success is True
    # content是json字符串，查找key
    assert "functions" in res.content

def test_astparse_syntax_error():
    """AstParseTool 解析语法错误文件"""
    tool = AstParseTool()
    res = tool.run(path=str(BAD_CASE_PATH))
    assert res.success is False
    assert "语法错误" in res.error

def test_runlinter_normal():
    """RunLinterTool 正常文件执行ruff"""
    tool = RunLinterTool()
    res = tool.run(path=str(TEST_CASE_PATH))
    assert res.success is True
    # json字符串转回list校验
    data = json.loads(res.content)
    assert isinstance(data, list)

def test_runlinter_not_found():
    """RunLinterTool 文件不存在"""
    tool = RunLinterTool()
    res = tool.run(path=str(NOT_EXIST_PATH))
    assert res.success is False
    assert res.error == "文件不存在"