from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.main import get_session
from src.db.models import User
from src.schemes.user import UserParams, UserParamsUpdate, UserPublic, UserUpdate, UserUpdateAdmin
from src.services.auth import get_current_user, is_admin
from src.services.user import UserService

router = APIRouter(
    prefix='/users',
    tags=['User'],
)


@router.get('/', response_model=list[UserPublic])
async def read_users(session: Annotated[AsyncSession, Depends(get_session)]):
    return await UserService(session).get_all_users()


@router.patch('/', response_model=UserPublic)
async def update_user(
    user: UserUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    username = current_user.username
    return await UserService(session).update_user(username, user)


@router.delete('/', status_code=status.HTTP_200_OK)
async def delete_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    username = current_user.username
    await UserService(session).delete_user(username)
    return {'detail': f'User {username} deleted successfully.'}


@router.get('/params', status_code=status.HTTP_200_OK, response_model=UserParams)
async def get_params(
    current_user: Annotated[User, Depends(get_current_user)],
):
    return current_user


@router.patch('/params', status_code=status.HTTP_200_OK, response_model=UserParams)
async def update_params(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    params: UserParamsUpdate,
):
    return await UserService(session).update_params(current_user.uid, params)


@router.get('/{username}', status_code=status.HTTP_200_OK, response_model=UserPublic)
async def read_user(username: str, session: Annotated[AsyncSession, Depends(get_session)]):
    return await UserService(session).get_user(username)


@router.patch('/{username}', response_model=UserPublic)
async def update_user_admin(
    username: str,
    user: UserUpdateAdmin,
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(is_admin)],
):
    return await UserService(session).update_user_admin(username, user)


@router.delete('/{username}', status_code=status.HTTP_200_OK)
async def delete_user_admin(
    username: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(is_admin)],
):
    await UserService(session).delete_user(username)
    return {'detail': f'User {username} deleted successfully.'}
