from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.main import get_session
from src.db.models import User
from src.schemes.asset import AssetPublic
from src.services.asset import AssetService
from src.services.auth import get_current_user

router = APIRouter(
    prefix='/assets',
    tags=['Assets'],
)


@router.get(
    '/',
    status_code=status.HTTP_200_OK,
    response_model=list[AssetPublic],
)
async def get_user_assets(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return await AssetService(session).get_user_assets(current_user.uid)


@router.post(
    '/',
    status_code=status.HTTP_200_OK,
    response_model=list[AssetPublic],
)
async def update_user_assets(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return await AssetService(session).update_user_assets(current_user.uid)
