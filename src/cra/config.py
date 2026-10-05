from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel

ENV_PATH = Path(".env")
load_dotenv(ENV_PATH)

class AppConfig(BaseModel):
    api_key: str
    llm_model: str = "qwen-turbo"
    temperature: float = 0.2
    max_retries: int = 3
    max_loop: int = 8
    max_tokens: int = 3000
    log_level: str = "INFO"

def load_config() -> AppConfig:
    return AppConfig(
        api_key=os.getenv("DASHSCOPE_API_KEY", ""),
        llm_model=os.getenv("CRA_LLM_MODEL", "qwen-turbo"),
        temperature=float(os.getenv("CRA_TEMPERATURE", "0.2")),
        max_retries=int(os.getenv("CRA_MAX_RETRIES", "3")),
        max_loop=int(os.getenv("CRA_MAX_LOOP", "8")),
        max_tokens=int(os.getenv("CRA_MAX_TOKENS", "3000")),
        log_level=os.getenv("CRA_LOG_LEVEL", "INFO")
    )
