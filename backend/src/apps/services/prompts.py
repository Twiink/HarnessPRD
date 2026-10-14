"""根据当前应用配置加载 Prompt 文本资源。"""

from apps.core.config import get_settings

PROMPT_NAMES = frozenset(
    [
        "API_DOCS_GENERATION_PROMPT",
        "API_DOCS_REVIEW_PROMPT_TEMPLATE",
        "API_DOCS_REVIEW_SYSTEM_PROMPT",
        "CLARIFICATION_SYSTEM_PROMPT",
        "JSON_REPAIR_SYSTEM_PROMPT",
        "OPTIMIZE_DOCUMENT_PROMPT_TEMPLATE",
        "PRD_GENERATION_PROMPT",
        "PRD_REVIEWER_SYSTEM_PROMPT",
        "PRD_REVIEW_PROMPT_TEMPLATE",
        "PRD_REVIEW_REGENERATION_PROMPT_TEMPLATE",
        "PRD_REWRITE_PROMPT_TEMPLATE",
        "PRD_WRITER_SYSTEM_PROMPT",
        "PROMPTS_GENERATION_PROMPT",
        "PROMPTS_REVIEW_PROMPT_TEMPLATE",
        "PROMPTS_REVIEW_SYSTEM_PROMPT",
        "REVIEW_REPAIR_PROMPT_TEMPLATE",
        "SYSTEM_PROMPT",
    ]
)


def get_prompt(name: str) -> str:
    if name not in PROMPT_NAMES:
        raise ValueError(f"Unknown prompt: {name}")
    root = get_settings().resources_dir.resolve()
    path = (root / "prompts" / f"{name}.md").resolve()
    if not path.is_relative_to(root):
        raise ValueError("Prompt path escapes resources_dir")
    return path.read_text(encoding="utf-8")


def get_api_docs_review_prompt(prd_content: str, api_docs_content: str) -> str:
    return get_prompt("API_DOCS_REVIEW_PROMPT_TEMPLATE").format(
        prd_content=prd_content, api_docs_content=api_docs_content
    )


def get_prompts_review_prompt(prd_content: str, prompts_content: str) -> str:
    return get_prompt("PROMPTS_REVIEW_PROMPT_TEMPLATE").format(
        prd_content=prd_content, prompts_content=prompts_content
    )


def __getattr__(name: str) -> str:
    # 兼容旧常量导入；业务服务在调用时按当前配置读取资源。
    if name in PROMPT_NAMES:
        return get_prompt(name)
    raise AttributeError(name)
