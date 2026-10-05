from __future__ import annotations
import click
from cra.config import load_config
from cra.llm.qwen_client import QwenClient
from cra.agent.orchestrator import Orchestrator, OrchestratorConfig
from cra.report.renderer import MarkdownReportRenderer


@click.group()
def cli():
    pass


@cli.command("review")
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--rules", "-r", default="bug,style,security,performance,readability", help="启用审查维度，逗号分隔")
@click.option("--output", "-o", type=click.Path(), help="输出markdown文件路径")
def review(file_path, rules, output):
    cfg = load_config()
    if not cfg.api_key:
        click.echo("错误：请配置DASHSCOPE_API_KEY环境变量(.env)")
        return
    llm = QwenClient(
        api_key=cfg.api_key,
        model=cfg.llm_model,
        temperature=cfg.temperature
    )
    orch = Orchestrator(cfg=OrchestratorConfig(
        llm_client=llm,
        max_loop=cfg.max_loop,
        max_retry=cfg.max_retries,
        max_tokens=cfg.max_tokens,
    ))
    rule_list = [r.strip() for r in rules.split(",") if r.strip()]
    try:
        findings = orch.review(file_path, rule_list)
    except Exception as e:
        click.echo(f"审查失败：{e}")
        return
    renderer = MarkdownReportRenderer
    if output:
        md_text = renderer.render_markdown(findings)
        with open(output, "w", encoding="utf-8") as f:
            f.write(md_text)
        click.echo(f"报告写入 {output}")
    else:
        term_text = renderer.render_terminal(findings)
        click.echo(term_text)


if __name__ == "__main__":
    cli()
