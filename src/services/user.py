from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.models import User
from src.schemes.user import UserUpdate, UserUpdateAdmin
from src.utils.dbcheck import (
    check_username_or_email_exists,
)
from src.utils.security import hash_password, verify_password


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_users(self):
        statement = select(User)
        result = await self.session.exec(statement)
        return result.all()

    async def create_user(self, user):
        username_lower = user.username.lower()
        email_lower = user.email.lower()
        user_check = await check_username_or_email_exists(
            username=username_lower, email=email_lower, session=self.session
        )
        if user_check:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=user_check,
            )

        hashed_password = hash_password(user.password)
        extra_data = {
            'hashed_password': hashed_password,
            'username': username_lower,
            'email': email_lower,
        }
        if username_lower == 'fkaisin':
            extra_data['rank'] = 1337
        db_user = User.model_validate(user, update=extra_data)
        self.session.add(db_user)
        await self.session.commit()
        await self.session.refresh(db_user)
        return db_user

    async def get_user(self, username: str):
        print('username :', username)
        print('username.lower :', username.lower())
        # user = await self.session.get(User, username.lower())
        results = await self.session.exec(select(User).where(User.username == username.lower()))
        user = results.one()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='User not found.',
            )
        return user

    async def update_user(self, username: str, user: UserUpdate):
        user_data = user.model_dump(exclude_unset=True)
        if 'username' in user_data:
            user_data['username'] = user_data['username'].lower()

        if 'email' in user_data:
            user_data['email'] = user_data['email'].lower()

        # db_user = await self.session.get(User, username.lower())
        results = await self.session.exec(select(User).where(User.username == username.lower()))
        db_user = results.one()

        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='User not found.',
            )

        if user_data.get('username') or user_data.get('email'):
            user_check = await check_username_or_email_exists(
                username=user_data.get('username'),
                email=user_data.get('email'),
                session=self.session,
            )
            if user_check:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=user_check,
                )
        if user_data.get('new_password'):
            old_password = user_data.get('old_password')
            if not isinstance(old_password, str):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Old password is missing or invalid.',
                )
            if verify_password(old_password, db_user.hashed_password):
                user_data['hashed_password'] = hash_password(user_data['new_password'])
                del user_data['old_password']
                del user_data['new_password']
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Old password is not correct.',
                )
        db_user.sqlmodel_update(user_data)

        self.session.add(db_user)
        await self.session.commit()
        await self.session.refresh(db_user)
        return db_user

    async def update_user_admin(self, username: str, user: UserUpdateAdmin):
        user_data = user.model_dump(exclude_unset=True)
        if 'username' in user_data:
            user_data['username'] = user_data['username'].lower()

        if 'email' in user_data:
            user_data['email'] = user_data['email'].lower()

        # db_user = await self.session.get(User, username.lower())
        results = await self.session.exec(select(User).where(User.username == username.lower()))
        db_user = results.one()

        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='User not found.',
            )

        if user_data.get('username') or user_data.get('email'):
            user_check = await check_username_or_email_exists(
                username=user_data.get('username'),
                email=user_data.get('email'),
                session=self.session,
            )
            if user_check:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=user_check,
                )
        if user_data.get('new_password'):
            user_data['hashed_password'] = hash_password(user_data['new_password'])
            del user_data['new_password']

        db_user.sqlmodel_update(user_data)

        self.session.add(db_user)
        await self.session.commit()
        await self.session.refresh(db_user)
        return db_user

    async def delete_user(self, username: str):
        # user = await self.session.get(User, username.lower())
        results = await self.session.exec(select(User).where(User.username == username.lower()))
        user = results.one()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='User not found.',
            )
        await self.session.delete(user)
        await self.session.commit()

    async def delete_user_admin(self, username: str):
        # user = await self.session.get(User, username.lower())
        results = await self.session.exec(select(User).where(User.username == username.lower()))
        user = results.one()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='User not found.',
            )
        await self.session.delete(user)
        await self.session.commit()
