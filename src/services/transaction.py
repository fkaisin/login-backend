import uuid

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, NoResultFound, SQLAlchemyError
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
        return sorted(user_with_tx.transactions, key=lambda trx: trx.date, reverse=True) if user_with_tx else []

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

    async def delete_transaction(self, trx_id, current_user_uid):
        trx_uid = uuid.UUID(trx_id)

        try:
            statement = select(Transaction).where(Transaction.id == trx_uid)
            result = await self.session.exec(statement)
            trx_to_delete = result.one()

        except NoResultFound:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Transaction not found in DB.')
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f'Error retrieving transaction: {str(e)}'
            )

        if trx_to_delete.user_id != current_user_uid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,  # 403 = interdit
                detail='You are not authorized to delete this transaction.',
            )

        try:
            await self.session.delete(trx_to_delete)
            await self.session.commit()
            return JSONResponse(status_code=status.HTTP_200_OK, content={'detail': 'Transaction deleted successfully.'})

        except SQLAlchemyError as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f'Database error while deleting transaction: {str(e)}',
            )
        except Exception as e:
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f'Unexpected error: {str(e)}')
