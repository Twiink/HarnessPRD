"""API 请求/响应模型定义"""

from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class StartConversationRequest(BaseModel):
    initial_input: Optional[str] = ""
    form_data: Optional[Dict[str, Any]] = None
    system_prompt_override: Optional[str] = None


class ContinueConversationRequest(BaseModel):
    conversation_id: str
    messages: List[Dict[str, str]]
    user_input: str


class ConversationMessagesRequest(BaseModel):
    """用于所有只需传入对话历史的请求（generate-prd、generate-prd-stream）"""
    conversation_messages: List[Dict[str, str]]


class GeneratePrdFromSummaryRequest(BaseModel):
    requirements_summary: Dict[str, Any]
    conversation_messages: Optional[List[Dict[str, str]]] = None


class SyncSummaryFromConversationRequest(BaseModel):
    requirements_summary: Dict[str, Any]
    conversation_messages: List[Dict[str, str]]


class GenerateApiDocsRequest(BaseModel):
    prd_content: str
    conversation_messages: List[Dict[str, str]]


class GeneratePromptsRequest(BaseModel):
    prd_content: str
    api_docs_content: str


class OptimizeDocumentRequest(BaseModel):
    doc_type: str
    current_content: str
    instruction: str
    context: Optional[str] = ""
