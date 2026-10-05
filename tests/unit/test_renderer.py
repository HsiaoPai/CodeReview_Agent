# tests/unit/test_renderer.py
import pytest
from pydantic import ValidationError
from cra.report.renderer import ReviewFinding, MarkdownReportRenderer


def test_render_markdown_valid_finding():
    """合法的ReviewFinding字典，渲染Markdown包含Blocker、行号、文件信息"""
    input_data = [
        {
            "file": "demo.py",
            "line_start": 8,
            "line_end": 12,
            "category": "bug",
            "severity": "Blocker",
            "title": "字典赋值未校验，存在类型不一致风险",
            "evidence": "student[key] = list_obj",
            "suggestion": "增加类型判断，保证字典结构统一",
            "confidence": 0.92
        }
    ]
    md_text = MarkdownReportRenderer.render_markdown(input_data)
    assert "[Blocker]" in md_text
    assert "8-12" in md_text
    assert "demo.py" in md_text
    assert "字典赋值未校验" in md_text
    assert "置信度:0.92" in md_text


def test_render_terminal_output_color_text():
    """测试终端彩色渲染输出"""
    input_data = [
        {
            "file": "test.py",
            "line_start": 10,
            "line_end": 10,
            "category": "security",
            "severity": "Major",
            "title": "存在安全风险",
            "evidence": "eval(input())",
            "suggestion": "禁止直接使用eval",
            "confidence": 0.85
        }
    ]
    term_out = MarkdownReportRenderer.render_terminal(input_data)
    assert "[Major]" in term_out
    assert "test.py L10-10" in term_out
    assert "禁止直接使用eval" in term_out


def test_review_finding_invalid_severity_raise_validation_error():
    """非法severity high，触发Pydantic校验失败（反向测试schema一致性）"""
    bad_data = {
        "file": "demo.py",
        "line_start": 10,
        "line_end": 10,
        "category": "bug",
        "severity": "high",   # ❌非法，只能 Blocker/Major/Minor/Info
        "title": "测试非法等级",
        "evidence": "xxx",
        "suggestion": "xxx",
        "confidence": 0.8
    }
    with pytest.raises(ValidationError):
        ReviewFinding(**bad_data)


def test_review_finding_confidence_out_of_range():
    """置信度超出0‑1范围触发校验异常"""
    bad_data = {
        "file": "demo.py",
        "line_start": 1,
        "line_end": 2,
        "category": "bug",
        "severity": "Minor",
        "title": "置信度越界",
        "evidence": "test",
        "suggestion": "test",
        "confidence": 2.0  # ❌大于1
    }
    with pytest.raises(ValidationError):
        ReviewFinding(**bad_data)
