# Code Review Agent（代码审查 Agent）

> 课程：软件工程与项目实践 · Homework 1
> 选题方向：代码审查 Agent —— 分析代码质量、发现潜在 Bug、给出改进建议
> 技术路线：Python 3.11+ · 通义千问 Qwen（DashScope 原生 API，`dashscope` SDK）· 自研 ReAct Agent 循环
> 设计文档：[`Design.md`](Design.md)



## 1. 项目简介

​	实现标准Agent闭环：**输入 → 推理 → 工具调用 → 输出**。 

​	对本地Python文件做多维度代码审查，Agent通过Function‑Calling自主调用工具读取源码、AST解析、ruff静态检查，输出带行号、严重等级的结构化审查报告。支持**CLI命令行**与**FastAPI Web页面**两种交互方式。



## 2. 功能特性

- **多维度审查**：Bug 风险、编码风格、安全、性能、可读性，可通过 `--rules` 自定义启用
- **Agent 工具调用**：内置 3 个工具，由 LLM 通过 DashScope Function Calling 自主决策调度
  - `read_file` —— 读取本地 Python 源码全文
  - `ast_parse` —— 基于内置 `ast` 模块解析类 / 函数 / 调用关系与行号
  - `run_linter` —— 调用 `ruff` 获取静态分析告警（"硬证据"，缓解 LLM 行号幻觉）
- **结构化输出**：终端彩色展示 / 导出Markdown报告；Pydantic校验审查结果
- **健壮性**：ReAct状态机主循环，最大8轮循环防死循环  ； LLM调用异常指数退避重试  ；会话短期记忆、Token自动上下文裁剪
- **会话记忆**：已读文件 MD5 哈希、审查结论、最近工具调用记录
- **边界情况处理**：提供语法错误（`examples/bad_case.py`）、空文件（`examples/empty.py`）等边界样例验证
- **单元+集成测试**：Mock环境验证Agent流转，不需要真实大模型API



## 3. 快速开始

### 3.1 下载项目

```bash
​```bash
git clone https://github.com/HsiaoPai/CodeReview_Agent.git
cd CodeReview_Agent
```

### 3.2 环境准备

- Python 3.11+
- DashScope（阿里云百炼）API Key：https://bailian.console.aliyun.com/ ，以 `sk-` 开头

### 3.3 安装项目（Visual Studio Code）

```powershell
# 1、新建干净虚拟环境
python -m venv .venv

# 2、激活虚拟环境
# 成功标志：命令行前面出现 (.venv)
. .venv\Scripts\Activate.ps1

# 3、可编辑安装项目（安装 cra 包 + 全部依赖）
pip install -e .

# 4、验证包是否安装成功
python -c "import cra; print('cra模块导入成功！')"
```

### 3.4 配置 API Key

在项目根目录新建 `.env` 文件，写入：

```ini
DASHSCOPE_API_KEY=你的通义千问API密钥

CRA_LLM_MODEL=qwen-turbo        # qwen-turbo（默认）/ qwen-plus / qwen-max
CRA_MAX_RETRIES=3
CRA_TEMPERATURE=0.2
```

### 3.5 测试 CLI 入口

```powershell
# 短入口（推荐，已提供 cra/__main__.py）
python -m cra review --help

# 等价长入口
python -m cra.cli.main review --help
```

能正常打印 `review` 子命令的帮助信息即说明 CLI 入口可用。

### 3.6 审查代码

```powershell
# 基本用法（默认维度：bug,style,security,performance,readability）
python -m cra review path/to/your_file.py

# 使用仓库自带样例快速体验
python -m cra review examples/test_case.py

# 自定义审查维度
python -m cra review path/to/your_file.py --rules bug,security

# 将 Markdown 报告写入指定文件
python -m cra review examples/test_case.py -o report_test.md
```

### 3.7 Web 界面

```powershell
# 安装 web 依赖（fastapi + uvicorn 已声明于 pyproject.toml 的 web 可选依赖）
pip install -e ".[web]"

# 启动本地服务
python -m cra.web

# 浏览器访问
# http://127.0.0.1:8000
```

### 3.8 运行测试

```powershell
# 安装测试依赖（pytest 已声明于 pyproject.toml 的 test 可选依赖）
pip install -e ".[test]"

# 运行全部测试（单元 + 集成，无需真实 API Key）
pytest -v

# 仅运行单元测试 / 集成测试
pytest tests/unit -v
pytest tests/integration -v
```



## 4. 项目结构

```
CodeReview_Agent/
├─ Design.md          # 完整设计文档
├─ README.md
├─ .env.example       # 环境变量模板
├─ pyproject.toml     # 依赖声明
├─ examples/          # 测试样例
├─ src/cra/           # 源代码
│  ├─ agent/          # ReAct循环、编排、记忆模块
│  ├─ llm/            # LLM客户端、Prompt模板
│  ├─ tools/          # read_file / ast_parse / run_linter工具
│  ├─ cli/main.py     # 命令行入口
│  ├─ report/         # 报告渲染
│  └─ web/            # FastAPI Web服务
└─ tests/             # 单元、集成测试
```

遇到报错问题，请查阅 [`Design.md`](Design.md) 的【15、常见问题】。

