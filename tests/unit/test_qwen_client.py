# tests/unit/test_qwen_client.py
from cra.llm.qwen_client import clean_json_str

def test_clean_json_markdown_fence():
    """测试带 ```json ``` markdown围栏"""
    input_text = """
下面是审查结果：
```json
[{"title":"bug1"}]
```

以上是报告。
"""
    res = clean_json_str (input_text)
    assert res == '[{"title":"bug1"}]'

def test_clean_json_extra_natural_text ():
    """测试前后混杂自然语言"""
    raw = "好的，这是输出：[{\"title\":\"demo\"}]，完毕。"
    output = clean_json_str (raw)
    assert output == '[{"title":"demo"}]'

def test_clean_json_escape_single_quote ():
    """测试处理 ' 转义字符"""
    raw = ' 结果：[{"evidence":"It\\\'s a bug"}]'
    out = clean_json_str (raw)
    assert r"It's a bug" in out

def test_clean_json_empty_array ():
    """测试空数组 []"""
    raw_text = "本次没有发现问题，返回 []。"
    ret = clean_json_str (raw_text)
    assert ret == "[]"

def test_clean_json_no_fence_plain_json ():
    """直接返回纯 JSON，没有 markdown 围栏"""
    s = '[{"file":"test.py","confidence":0.8}]'
    r = clean_json_str (s)
    assert r == s