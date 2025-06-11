import uuid
from datetime import timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.config import settings
from src.db.main import get_session
from src.db.models import User
from src.schemes.auth import AccessTokenResponse
from src.utils.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/auth/login')
at_expire_seconds = 60 * settings.JWT_ACCESS_EXPIRATION_IN_MIN
rt_expire_in_seconds = 24 * 60 * 60 * settings.JWT_REFRESH_EXPIRATION_IN_HOURS


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def login(self, form_data: OAuth2PasswordRequestForm):
        # user_db = await self.session.get(User, form_data.username.lower())
        results = await self.session.exec(select(User).where(User.username == form_data.username.lower()))
        user_db = results.one()

        print('=' * 100)
        print(user_db)
        print('=' * 100)

        if not user_db or not verify_password(form_data.password, user_db.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Invalid username or password.',
            )

        access_token = create_access_token(
            data={'sub': str(user_db.uid), 'rank': user_db.rank},
            expires_delta=timedelta(seconds=at_expire_seconds),
        )
        refresh_token = create_refresh_token(
            data={'sub': str(user_db.uid), 'rank': user_db.rank},
            expires_delta=timedelta(seconds=rt_expire_in_seconds),
        )

        response = JSONResponse(
            content={
                'access_token': access_token,
                'token_type': 'bearer',
            },
            status_code=status.HTTP_202_ACCEPTED,
        )

        response.set_cookie(
            key='refreshToken',
            value=refresh_token,
            httponly=True,
            secure=True,
            # samesite='Strict',
            samesite='none',
            max_age=rt_expire_in_seconds,
            path='/auth/refresh',
        )

        return response

    async def refresh_access_token(self, refresh_payload):
        user_uid = refresh_payload.get('sub')

        results = await self.session.exec(select(User).where(User.uid == uuid.UUID(user_uid)))
        user_db = results.first()

        if not user_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Refresh token user ID not found.',
            )

        access_token = create_access_token(data={'sub': user_uid}, expires_delta=timedelta(seconds=at_expire_seconds))

        return AccessTokenResponse(access_token=access_token)


def logout():
    response = JSONResponse(content={'detail': 'Logged out successfully.'})

    # Demande au client de supprimer le cookie !!! MEMES PARAMETRES QUE LORS DE LA CREATION !!!
    response.delete_cookie(key='refreshToken', path='/auth/refresh', secure=True, samesite='none')
    return response


# Dépendance utilisée dans les routes protégées
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    invalid_token_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Invalid token.',
        headers={'WWW-Authenticate': 'Bearer'},
    )

    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

        # Transforme le token type str en type UUID
        user_uid = uuid.UUID(payload.get('sub'))

        if user_uid is None:
            raise invalid_token_exception

        statement = select(User).where(User.uid == user_uid)
        result = await session.exec(statement)
        user_db = result.first()

        if not user_db:
            raise invalid_token_exception

        return user_db

    except ExpiredSignatureError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Token expired.',
            headers={'WWW-Authenticate': 'Bearer'},
        ) from err
    except InvalidTokenError as err:
        raise invalid_token_exception from err


# Dépendance utilisée dans les routes protégées admin
async def is_admin(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    invalid_token_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Invalid token.',
        headers={'WWW-Authenticate': 'Bearer'},
    )

    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

        # Transforme le token type str en type UUID
        user_uid = uuid.UUID(payload.get('sub'))

        if user_uid is None:
            raise invalid_token_exception

        statement = select(User).where(User.uid == user_uid)
        result = await session.exec(statement)
        user_db = result.first()

        if not user_db:
            raise invalid_token_exception

        if user_db.rank != 1337:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Requires admin privilege.',
            )
        return user_db

    except ExpiredSignatureError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Token expired.',
            headers={'WWW-Authenticate': 'Bearer'},
        ) from err
    except InvalidTokenError as err:
        raise invalid_token_exception from err
