import uuid

from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import selectinload
from sqlmodel import Field, SQLModel, select
from src.calculation.asset import get_asset_mean_buy, get_asset_qty
from src.db.main import get_session
from src.schemes.token import TokenBase


class AssetBase(SQLModel):
  user_id: uuid.UUID | None = Field(default=None, index=True, foreign_key='users.uid', ondelete='CASCADE')
  token_id: str = Field(foreign_key='tokens.cg_id')

  qty: float = 0
  mean_buy: float = 0
  value: float = 0
  pnl_usd: float = 0
  pnl_percent: float = 0

  async def update_asset(self):
    from src.db.models import Token, User

    async for session in get_session():
      try:
        statement = select(User).where(User.uid == self.user_id).options(selectinload(User.transactions))  # type: ignore
        results = await session.exec(statement)
        user = results.one()

        transactions = sorted(user.transactions, key=lambda trx: trx.date)

        self.qty = max(get_asset_qty(token_id=self.token_id, transactions=transactions), 0)
        self.mean_buy = get_asset_mean_buy(token_id=self.token_id, transactions=transactions) if self.qty != 0 else 0

        token = await session.get(Token, self.token_id)
        self.value = self.qty * token.price
        self.pnl_usd = self.value - (self.qty * self.mean_buy) if self.qty != 0 else 0
        self.pnl_percent = self.value / (self.qty * self.mean_buy) - 1 if self.qty != 0 else 0

      except NoResultFound:
        raise Exception('User not found in DB.')

  async def refresh_asset(self):
    from src.db.models import Token

    async for session in get_session():
      try:
        token = await session.get(Token, self.token_id)
        self.value = self.qty * token.price
        self.pnl_usd = self.value - (self.qty * self.mean_buy) if self.qty != 0 else 0
        self.pnl_percent = self.value / (self.qty * self.mean_buy) - 1 if self.qty != 0 else 0

      except Exception as err:
        print('error :', err)
        raise Exception(f'error: {err}')


class AssetPublic(SQLModel):
  qty: float = 0
  mean_buy: float = 0
  value: float = 0
  pnl_usd: float = 0
  pnl_percent: float = 0
  token: TokenBase | None = None
