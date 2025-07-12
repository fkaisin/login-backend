from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.main import get_session
from src.db.models import User
from src.schemes.history import UserHistoryBase
from src.schemes.token import Ticker, TokenId
from src.services.auth import get_current_user
from src.services.history import HistoryService, check_ticker_exchange

router = APIRouter(
    prefix='/histo',
    tags=['Historical'],
)


@router.get('/', status_code=status.HTTP_200_OK, response_model=list[UserHistoryBase])
async def get_pf_history(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return await HistoryService(session).get_pf_history(current_user.uid)


@router.post('/tv-single', status_code=status.HTTP_200_OK)
async def get_best_ticker_exchange(
    session: Annotated[AsyncSession, Depends(get_session)],
    tok: TokenId,
):
    return await HistoryService(session).get_best_ticker_exchange(tok.cg_id)


@router.post('/tv-single/check', status_code=status.HTTP_200_OK)
async def check_ticker_exchange_route(tok: Ticker):
    return check_ticker_exchange(tok)


@router.post('/', status_code=status.HTTP_200_OK)
async def calculate_histo_pf(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    tv_list: list[Ticker],
):
    return await HistoryService(session).calculate_histo_pf(current_user.uid, tv_list)
