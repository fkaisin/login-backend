from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, Request, status
from jwt import ExpiredSignatureError, InvalidTokenError
from passlib.context import CryptContext
from src.config import settings


def hash_password(password: str) -> str:
    pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: dict,
    expires_delta: timedelta = timedelta(minutes=settings.JWT_ACCESS_EXPIRATION_IN_MIN),
) -> str:
    # expires_delta = timedelta(seconds=10)
    to_encode = data.copy()
    expire = datetime.now(UTC) + expires_delta
    to_encode.update({'exp': expire})
    return jwt.encode(
        payload=to_encode,
        key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(
    data: dict,
    expires_delta: timedelta = timedelta(
        hours=settings.JWT_REFRESH_EXPIRATION_IN_HOURS
    ),
) -> str:
    # expires_delta = timedelta(seconds=20)
    to_encode = data.copy()
    expire = datetime.now(UTC) + expires_delta
    to_encode.update({'exp': expire})
    return jwt.encode(
        payload=to_encode,
        key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_refresh_token_from_cookie(request: Request):
    token = request.cookies.get('refreshToken')

    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Refresh token not found.'
        )

    try:
        payload = jwt.decode(
            token, key=settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )

        return payload

    except ExpiredSignatureError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Expired token signature. Please login.',
        ) from err
    except InvalidTokenError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid token signature. Please login.',
        ) from err
