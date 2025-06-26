from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.main import get_session
from src.schemes.token import TokenPublicSmall
from src.services.token import TokenService

router = APIRouter(prefix='/token', tags=['Token'])


@router.get('/{search_string}', status_code=status.HTTP_200_OK, response_model=list[TokenPublicSmall])
async def search_tokens(search_string: str, session: Annotated[AsyncSession, Depends(get_session)]):
  return await TokenService(session).search_tokens(search_string)
