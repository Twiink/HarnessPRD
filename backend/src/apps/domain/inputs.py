"""需求与会话的已知输入契约，保留客户端扩展字段。"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt, StrictStr

from apps.domain.reviews import ReviewInput


class ExtensibleInput(BaseModel):
    model_config = ConfigDict(extra="allow")


class ConversationMessage(ExtensibleInput):
    role: Literal["system", "user", "human", "assistant", "ai"]
    content: StrictStr


class FeatureInput(ExtensibleInput):
    name: StrictStr | None = None
    description: StrictStr | None = None
    user_value: StrictStr | None = None


class PageInput(ExtensibleInput):
    name: StrictStr | None = None
    modules: list[StrictStr] | None = None
    notes: StrictStr | None = None


class FormPageInput(ExtensibleInput):
    name: StrictStr | None = None
    modules: list[StrictStr] | StrictStr | None = None
    notes: StrictStr | None = None


class TechnicalConstraintsInput(ExtensibleInput):
    auth: StrictBool | StrictStr | None = None
    database: StrictBool | StrictStr | None = None
    frontend: StrictStr | None = None
    backend: StrictStr | None = None
    deployment: StrictStr | None = None
    llm_usage: StrictStr | None = None
    security: list[StrictStr] | None = None


class NonFunctionalInput(ExtensibleInput):
    performance: list[StrictStr] | None = None
    security: list[StrictStr] | None = None
    usability: list[StrictStr] | None = None
    compatibility: list[StrictStr] | None = None


class DesignInput(ExtensibleInput):
    theme: StrictStr | None = None
    responsive: StrictBool | None = None
    style_notes: list[StrictStr] | None = None


class RequirementFields(ExtensibleInput):
    product_name: StrictStr | None = None
    product_goal: StrictStr | None = None
    problem_solved: StrictStr | None = None
    target_users: StrictStr | list[StrictStr] | None = None
    platform: StrictStr | None = None
    features: list[FeatureInput | StrictStr] | StrictStr | None = None
    mvp_features: list[FeatureInput | StrictStr] | StrictStr | None = None
    v2_features: list[FeatureInput | StrictStr] | StrictStr | None = None
    interaction_notes: list[StrictStr] | StrictStr | None = None
    in_scope: list[StrictStr] | StrictStr | None = None
    out_of_scope: list[StrictStr] | StrictStr | None = None
    technical_constraints: TechnicalConstraintsInput | None = None
    non_functional_requirements: NonFunctionalInput | None = None
    design_requirements: DesignInput | None = None


class RequirementsInput(RequirementFields):
    ui_pages: list[PageInput | StrictStr] | None = None


class FormInput(RequirementFields):
    # 编辑表单与旧草稿的 modules 为文本；结构化摘要的 modules 为列表。
    ui_pages: list[FormPageInput | StrictStr] | StrictStr | None = None


class SessionInput(ExtensibleInput):
    formData: FormInput | None = None
    requirementsSummary: RequirementsInput | None = None
    pendingSummary: RequirementsInput | None = None
    messages: list[ConversationMessage] | None = None
    prdContent: StrictStr | None = None
    apiDocsContent: StrictStr | None = None
    promptsContent: StrictStr | None = None
    manualPrdInput: StrictStr | None = None
    manualApiDocsInput: StrictStr | None = None
    manualPromptsInput: StrictStr | None = None
    prdReviewResult: ReviewInput | None = None
    viewState: StrictStr | None = None
    entryMode: StrictStr | None = None
    activeJobId: StrictStr | None = None
    activeOptimizeJobId: StrictStr | None = None
    prdBaselineConfirmed: StrictBool | None = None
    prdBaselineConfirmedAt: StrictStr | None = None
    prdBaselineVersionId: StrictStr | None = None
    prdBaselineVersionNo: StrictInt | None = None
    prdBaselineContentHash: StrictStr | None = None


def input_dict(value: ExtensibleInput) -> dict[str, Any]:
    """省略缺省字段，避免局部更新无意覆盖旧值。"""
    return value.model_dump(exclude_unset=True)


def message_dicts(messages: list[ConversationMessage]) -> list[dict[str, Any]]:
    return [input_dict(message) for message in messages]
