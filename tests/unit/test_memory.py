# tests/unit/test_memory.py
from cra.agent.memory import SessionMemory, truncate_messages
import hashlib

def test_session_memory_fifo_limit():
    """
    SessionMemory.append_tool_record FIFO 测试
    连续append6条记录，tool_call_history最大长度保持5
    """
    mem = SessionMemory(max_tool_history=5)
    for i in range(6):
        call_info = {"name": f"tool_{i}", "args": {}}
        result = {"success": True, "content": f"res_{i}"}
        mem.append_tool_record(call_info, result)

    # 断言总长度上限为5
    assert len(mem.tool_call_history) == 5
    # FIFO：最先插入的第0条被丢弃，保留 1,2,3,4,5
    names = [rec["call"]["name"] for rec in mem.tool_call_history]
    assert names == ["tool_1", "tool_2", "tool_3", "tool_4", "tool_5"]


def test_truncate_messages_keep_system():
    """
    truncate_messages 超长消息裁剪
    要求：system消息保留，总token降到阈值以下，消息顺序不变
    这里假设你的truncate_messages阈值3000
    """
    messages = [
        {"role": "system", "content": "你是代码审查专家，永远保留这条system提示"},
    ]
    # 构造大量用户消息，制造超长上下文
    for i in range(20):
        messages.append({"role": "user", "content": "文本填充" * 200})

    new_messages = truncate_messages(messages, max_total_tokens=3000)

    # system消息必须保留，并且是第一条
    assert new_messages[0]["role"] == "system"
    # 消息顺序不变
    orig_system = messages[0]["content"]
    assert new_messages[0]["content"] == orig_system
    # 裁剪后消息总数变少
    assert len(new_messages) < len(messages)


def test_memory_add_read_file_md5():
    """add_read_file 写入MD5哈希校验"""
    mem = SessionMemory()
    content = "print('hello md5')"
    expected_md5 = hashlib.md5(content.encode("utf-8")).hexdigest()
    mem.add_read_file(path="test.py", content=content)

    # 直接从 read_file_hashes 取md5校验
    assert mem.read_file_hashes["test.py"] == expected_md5