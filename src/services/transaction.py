import uuid

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import NoResultFound, SQLAlchemyError
from sqlalchemy.orm import joinedload, selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.celery.tasks import get_total_pnl_task
from src.db.models import Token, Transaction, User
from src.services.asset import AssetService


class TransactionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_transactions(self, current_user_uid):
        statement = (
            select(User)
            .where(User.uid == current_user_uid)
            .options(
                selectinload(User.transactions).selectinload(Transaction.actif_a).load_only(Token.symbol, Token.rank, Token.name), # type: ignore 
                selectinload(User.transactions).selectinload(Transaction.actif_v).load_only(Token.symbol, Token.rank, Token.name), # type: ignore
                selectinload(User.transactions).selectinload(Transaction.actif_f).load_only(Token.symbol, Token.rank, Token.name), # type: ignore
            )
        )  # fmt: skip
        result = await self.session.exec(statement)
        user_with_tx = result.one()
        missing_tokens = [str(t.actif_a_id) for t in user_with_tx.transactions if t.actif_a is None]
        if missing_tokens:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'token(s) {", ".join(missing_tokens)} missing in DB. Contact administrator.',
            )

        return sorted(user_with_tx.transactions, key=lambda trx: trx.date, reverse=True) if user_with_tx else []

    async def create_transactions(self, trx_data, current_user: User):
        user_id = current_user.uid
        fiat = current_user.fiat_id

        extra_data = {'user_id': user_id}
        try:
            db_trx = Transaction.model_validate(trx_data, update=extra_data)
            self.session.add(db_trx)
            await self.session.commit()
            await self.session.refresh(db_trx)

            statement = (
                select(Transaction)
                .options(
                    joinedload(Transaction.actif_a).load_only(Token.symbol, Token.rank, Token.name),  # type: ignore
                    joinedload(Transaction.actif_v).load_only(Token.symbol, Token.rank, Token.name),  # type: ignore
                    joinedload(Transaction.actif_f).load_only(Token.symbol, Token.rank, Token.name),  # type: ignore
                )
                .where(Transaction.id == db_trx.id)
            )

            result = await self.session.exec(statement)
            transaction_with_relations = result.first()
            if not transaction_with_relations:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail='Transaction not found after creation'
                )

            await self.update_assets_from_transaction(transaction_with_relations, user_id)  # Update Assets

            get_total_pnl_task.delay(user_id=user_id, fiat='fiat_usd')
            if fiat != 'fiat_usd':
                get_total_pnl_task.delay(user_id=user_id, fiat=fiat)

            return transaction_with_relations

        except ValidationError as ve:
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(ve))

        except SQLAlchemyError:
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Database error')

        except Exception:
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Unexpected error')

    async def delete_transaction(self, trx_id, current_user: User):
        user_id = current_user.uid
        fiat = current_user.fiat_id
        trx_uid = uuid.UUID(trx_id)

        try:
            statement = select(Transaction).where(Transaction.id == trx_uid)
            result = await self.session.exec(statement)
            trx_to_delete = result.one()

        except NoResultFound as err:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Transaction not found in DB.') from err
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f'Error retrieving transaction: {str(err)}'
            ) from err

        if trx_to_delete.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,  # 403 = interdit
                detail='You are not authorized to delete this transaction.',
            )

        try:
            await self.session.delete(trx_to_delete)
            await self.session.commit()
            await self.update_assets_from_transaction(trx_to_delete, user_id)

            get_total_pnl_task.delay(user_id=user_id, fiat='fiat_usd')
            if fiat != 'fiat_usd':
                get_total_pnl_task.delay(user_id=user_id, fiat=fiat)

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

    async def update_transactions(self, trx_data, current_user: User):
        user_id = current_user.uid
        fiat = current_user.fiat_id

        try:
            db_trx = Transaction.model_validate(trx_data)

            existing_transaction = await self.session.get(Transaction, db_trx.id)
            if not existing_transaction:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f'Transaction ID {db_trx.id} not found.'
                )

            existing_transaction.type = db_trx.type
            existing_transaction.date = db_trx.date
            existing_transaction.qty_a = db_trx.qty_a
            existing_transaction.qty_f = db_trx.qty_f or None
            existing_transaction.actif_a_id = db_trx.actif_a_id
            existing_transaction.actif_v_id = db_trx.actif_v_id or None
            existing_transaction.actif_f_id = db_trx.actif_f_id or None
            existing_transaction.price = db_trx.price or None
            existing_transaction.value_a = db_trx.value_a or None
            existing_transaction.value_f = db_trx.value_f or None
            existing_transaction.origin = db_trx.origin or None
            existing_transaction.destination = db_trx.destination

            self.session.add(existing_transaction)
            await self.session.commit()

            statement = (
                select(Transaction)
                .options(
                    joinedload(Transaction.actif_a).load_only(Token.symbol, Token.rank, Token.name),
                    joinedload(Transaction.actif_v).load_only(Token.symbol, Token.rank, Token.name),
                    joinedload(Transaction.actif_f).load_only(Token.symbol, Token.rank, Token.name),
                )
                .where(Transaction.id == db_trx.id)
            )

            result = await self.session.exec(statement)
            transaction_with_relations = result.first()

            await self.update_assets_from_transaction(transaction_with_relations, transaction_with_relations.user_id)

            get_total_pnl_task.delay(user_id=user_id, fiat='fiat_usd')
            if fiat != 'fiat_usd':
                get_total_pnl_task.delay(user_id=user_id, fiat=fiat)

            return transaction_with_relations

        except ValidationError as ve:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f'Validation error: {ve.errors()}'
            )

        except SQLAlchemyError as db_err:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f'Database error: {str(db_err)}'
            )

        except Exception as e:
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f'Unexpected error: {str(e)}')

    async def update_assets_from_transaction(self, transaction: Transaction, current_user_uid: uuid.UUID):
        # token_ids = {
        #   transaction.actif_a_id,
        #   transaction.actif_v_id,
        #   transaction.actif_f_id,
        # } - {None}
        token_ids = {
            actif_id
            for actif_id in {transaction.actif_a_id, transaction.actif_v_id, transaction.actif_f_id}
            if actif_id is not None and not str(actif_id).startswith('fiat_')
        }

        if token_ids:
            await AssetService(self.session).update_specific_assets(current_user_uid, token_ids)
