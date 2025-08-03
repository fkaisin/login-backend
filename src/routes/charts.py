from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.main import get_session
from src.db.models import User
from src.services.auth import get_current_user
from src.services.charts import ChartService

router = APIRouter(
    prefix='/chart',
    tags=['Charts'],
)


@router.get(
    '/cash_in',
    status_code=status.HTTP_200_OK,
)
async def get_user_cash_in(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
):
    return {f'cash_in_{fiat}': getattr(user, f'cash_in_{fiat}') for fiat in ['usd', 'eur', 'cad', 'chf']}
