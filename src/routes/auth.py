from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.main import get_session
from src.db.models import User
from src.schemes.auth import AccessTokenResponse
from src.schemes.user import UserCreate, UserPublic
from src.services.auth import AuthService, get_current_user, is_admin, logout
from src.services.user import UserService
from src.utils.security import decode_refresh_token_from_cookie

router = APIRouter(
  prefix='/auth',
  tags=['Authentication'],
)


@router.post(
  '/register',
  status_code=status.HTTP_201_CREATED,
  response_model=UserPublic,
)
async def create_user(user: UserCreate, session: Annotated[AsyncSession, Depends(get_session)]):
  return await UserService(session).create_user(user)


@router.post('/login', response_model=AccessTokenResponse)
async def login(
  form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
  session: Annotated[AsyncSession, Depends(get_session)],
):
  # Return a JSONResponse with "access_token" and "token_type" in content + "refresh_token" in HTTP only cookie.  # noqa: E501
  response = await AuthService(session).login(form_data)
  return response


@router.get('/me', status_code=status.HTTP_202_ACCEPTED, response_model=UserPublic)
async def read_user_me(
  current_user: Annotated[User, Depends(get_current_user)],
):
  return current_user


@router.get('/admin', status_code=status.HTTP_202_ACCEPTED, response_model=UserPublic)
async def read_is_admin(
  current_user: Annotated[User, Depends(is_admin)],
):
  return current_user


@router.post('/refresh', response_model=AccessTokenResponse)
async def generate_new_access_token(
  refresh_payload: Annotated[dict, Depends(decode_refresh_token_from_cookie)],
  session: Annotated[AsyncSession, Depends(get_session)],
):
  token = await AuthService(session).refresh_access_token(refresh_payload)
  return token


@router.post('/logout')
def logout_user():
  return logout()
