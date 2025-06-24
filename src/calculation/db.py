import uuid

from sqlmodel import asc, or_, select
from src.db.main import get_session_with_context_manager


async def get_user_token_transactions(user_id: uuid.UUID, token_id: str):
  from src.db.models import Transaction

  #   async for session in get_session():
  async with get_session_with_context_manager() as session:
    statement = (
      select(Transaction)
      .where(Transaction.user_id == user_id)
      .where(
        or_(Transaction.actif_a_id == token_id, Transaction.actif_v_id == token_id, Transaction.actif_f_id == token_id)
      )
      .order_by(asc(Transaction.date))
    )

    results = await session.exec(statement)
    transactions = results.all()
    return transactions
