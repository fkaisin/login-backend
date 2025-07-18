from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.main import get_session
from src.db.models import User
from src.schemes.transaction import TransactionCreate, TransactionPublic, TransactionUpdate
from src.services.auth import get_current_user
from src.services.transaction import TransactionService

router = APIRouter(
  prefix='/transactions',
  tags=['Transactions'],
)


@router.get(
  '/',
  status_code=status.HTTP_200_OK,
  response_model=list[TransactionPublic],
)
async def get_user_transactions(
  session: Annotated[AsyncSession, Depends(get_session)],
  current_user: Annotated[User, Depends(get_current_user)],
):
  return await TransactionService(session).get_user_transactions(current_user.uid)


@router.post(
  '/',
  status_code=status.HTTP_201_CREATED,
  response_model=TransactionPublic,
)
async def create_transactions(
  trx_data: TransactionCreate,
  session: Annotated[AsyncSession, Depends(get_session)],
  current_user: Annotated[User, Depends(get_current_user)],
):
  return await TransactionService(session).create_transactions(trx_data, current_user.uid)


@router.patch(
  '/',
  status_code=status.HTTP_202_ACCEPTED,
  response_model=TransactionPublic,
)
async def update_transactions(
  trx_data: TransactionUpdate,
  session: Annotated[AsyncSession, Depends(get_session)],
  current_user: Annotated[User, Depends(get_current_user)],
):
  return await TransactionService(session).update_transactions(trx_data)


@router.delete('/', status_code=status.HTTP_200_OK)
async def delete_transaction(
  trx_id: str,
  session: Annotated[AsyncSession, Depends(get_session)],
  current_user: Annotated[User, Depends(get_current_user)],
):
  return await TransactionService(session).delete_transaction(trx_id, current_user.uid)
