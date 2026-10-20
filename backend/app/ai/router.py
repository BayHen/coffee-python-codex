"""Management-only AI chat endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.schemas import ChatRequest, ChatResponse
from app.ai.service import AIManagementService
from app.auth.dependencies import Principal, require_roles
from app.db.session import get_session

router = APIRouter(prefix="/ai", tags=["ai"])
Manager = Annotated[Principal, Depends(require_roles("Admin", "Manager"))]
Db = Annotated[Session, Depends(get_session)]


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, principal: Manager, db: Db) -> ChatResponse:
    return AIManagementService(db, principal).chat(payload.message)
