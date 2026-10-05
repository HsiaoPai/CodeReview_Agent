# src/cra/llm/qwen_client.py
import re
import json
import dashscope
from dashscope import Generation
from typing import List, Dict, Any


class LLMRequestError(Exception):
    """LLM调用异常"""
    pass


def clean_json_str(text: str) -> str:
    """
    JSON文本清洗
    1.剥离 ```json 围栏
    2.截取从 [/{ 到 }/] 的主体
    3.修复 \' 转义问题
    """
    # 1、提取json代码块
    fence_match = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)

    # 2、寻找json起始结束符号
    start_idx = -1
    for idx, char in enumerate(text):
        if char in ("[", "{"):
            start_idx = idx
            break
    end_idx = -1
    for idx, char in reversed(list(enumerate(text))):
        if char in ("]", "}"):
            end_idx = idx
            break

    if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
        text = text[start_idx: end_idx + 1]

    # 3、处理 \' 转义
    text = text.replace(r"\'", "'")
    return text.strip()


class QwenClient:
    def __init__(self, api_key: str, model: str, temperature: float):
        dashscope.api_key = api_key
        self.model = model
        self.temperature = temperature

    def chat(self, messages: List[Dict[str, Any]], tools=None) -> Dict[str, Any]:
        """普通chat，支持function calling"""
        call_kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature
        }
        if tools:
            call_kwargs["tools"] = tools
        try:
            resp = Generation.call(**call_kwargs, result_format="message")
        except Exception as e:
            # 保留原始异常链，统一封装为 LLMRequestError 供上层重试决策
            raise LLMRequestError(f"LLM调用异常: {e}") from e
        if resp.status_code != 200:
            raise LLMRequestError(f"LLM调用失败:{resp.code} {resp.message}")
        return resp.output.choices[0].message

    def chat_json(self, system: str, user: str) -> List[Dict[str, Any]]:
        """获取结构化JSON，使用clean_json_str清洗输出"""
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]
        raw_msg = self.chat(messages)
        raw_text = raw_msg.get("content", "")
        cleaned = clean_json_str(raw_text)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise LLMRequestError(f"JSON解析失败，原始清洗后文本：{cleaned}, err:{e}") from e
        if not isinstance(data, list):
            raise LLMRequestError("期待返回JSON数组")
        return data
