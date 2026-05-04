# core/state.py
from typing import TypedDict, Annotated, Literal, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
import operator

class ChatState(TypedDict):
    """The shared memory passed between all agents."""
    messages: Annotated[list[BaseMessage], add_messages]
    thread_id: str
    next_node: str         # Used by Supervisor to route to the correct agent
    active_agent: str      # Used by Tools to return to the calling agent
    image_assets: list[str]
    research_images: list[str]
    pending_email: dict | None
    forced_agent: str

class RouteAgent(BaseModel):
    """Schema for the Supervisor's JSON output decision."""
    next_node: Literal[
        "multimodal_rag", 
        "code_agent", 
        "research_agent", 
        "chatmodal", 
        "ppt_agent", 
        "docx_agent"
    ] = Field(..., description="Name of the specialized agent to route to next.")