from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.models import Transaction, User


class TransactionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_transactions(self, current_user_uid):
        # Recharge le user avec ses transactions explicitement
        statement = (
            select(User)
            .where(User.uid == current_user_uid)
            .options(
                selectinload(User.transactions).selectinload(Transaction.actif_a),
                selectinload(User.transactions).selectinload(Transaction.actif_v),
                selectinload(User.transactions).selectinload(Transaction.actif_f),
            )
        )
        result = await self.session.exec(statement)
        user_with_tx = result.one()
        # return user_with_tx.transactions if user_with_tx else []
        return (
            sorted(user_with_tx.transactions, key=lambda trx: trx.date, reverse=True)
            if user_with_tx
            else []
        )

    async def create_transactions(self, trx_data, current_user_uid):
        extra_data = {
            'user_id': current_user_uid,
        }
        try:
            db_trx = Transaction.model_validate(trx_data, update=extra_data)
            self.session.add(db_trx)
            await self.session.commit()
            await self.session.refresh(db_trx)
            return db_trx

        except IntegrityError as err:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Invalid data: token id not found.',
            ) from err
