"""API 请求/响应模型定义"""

from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class StartConversationRequest(BaseModel):
    initial_input: Optional[str] = ""
    form_data: Optional[Dict[str, Any]] = None
    system_prompt_override: Optional[str] = None


class ContinueConversationRequest(BaseModel):
    conversation_id: str
    messages: List[Dict[str, Any]]
    user_input: str


class ConversationMessagesRequest(BaseModel):
    """用于所有只需传入对话历史的请求（generate-prd、generate-prd-stream）"""
    conversation_messages: List[Dict[str, Any]]


class GeneratePrdFromSummaryRequest(BaseModel):
    requirements_summary: Dict[str, Any]
    conversation_messages: Optional[List[Dict[str, Any]]] = None


class SyncSummaryFromConversationRequest(BaseModel):
    requirements_summary: Dict[str, Any]
    conversation_messages: List[Dict[str, Any]]


class GenerateApiDocsRequest(BaseModel):
    prd_content: str
    conversation_messages: List[Dict[str, Any]]


class GeneratePromptsRequest(BaseModel):
    prd_content: str
    api_docs_content: str


class OptimizeDocumentRequest(BaseModel):
    doc_type: str
    current_content: str
    instruction: str
    context: Optional[str] = ""


class CreateJobRequest(BaseModel):
    session_id: str
    artifact: str
    payload: Dict[str, Any]


class CreateJobResponse(BaseModel):
    job_id: str


class JobDetailResponse(BaseModel):
    id: str
    session_id: str
    artifact: str
    status: str
    phase: str
    draft_content: str
    review: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
