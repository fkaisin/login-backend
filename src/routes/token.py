from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.main import get_session
from src.schemes.token import TokenPublicPrice, TokenPublicSmall
from src.services.token import TokenService

router = APIRouter(prefix='/token', tags=['Token'])


@router.get('/price/{search_string}', status_code=status.HTTP_200_OK, response_model=TokenPublicPrice)
async def search_token_price(search_string: str, session: Annotated[AsyncSession, Depends(get_session)]):
    return await TokenService(session).get_token(search_string)


@router.get('/{search_string}', status_code=status.HTTP_200_OK, response_model=list[TokenPublicSmall])
async def search_tokens(search_string: str, session: Annotated[AsyncSession, Depends(get_session)]):
    return await TokenService(session).search_tokens(search_string)
