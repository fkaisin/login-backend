import uuid
from datetime import datetime

from pydantic import computed_field
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import selectinload
from sqlmodel import Field, SQLModel, select
from src.db.main import get_session
from src.schemes.token import TokenPublicAsset
from src.utils.asset import get_asset_mean_buy, get_asset_qty


class AssetBase(SQLModel):
  user_id: uuid.UUID | None = Field(default=None, index=True, foreign_key='users.uid', ondelete='CASCADE')
  token_id: str = Field(foreign_key='tokens.cg_id')

  qty: float = 0
  mean_buy: float = 0

  async def update_asset(self):
    from src.db.models import User

    async for session in get_session():
      try:
        statement = select(User).where(User.uid == self.user_id).options(selectinload(User.transactions))  # type: ignore
        results = await session.exec(statement)
        user = results.one()

        transactions = sorted(user.transactions, key=lambda trx: trx.date)

        self.qty = max(get_asset_qty(token_id=self.token_id, transactions=transactions), 0)
        self.mean_buy = get_asset_mean_buy(token_id=self.token_id, transactions=transactions) if self.qty != 0 else 0

      except NoResultFound:
        raise Exception('User not found in DB.')


class AssetPublic(SQLModel):
  qty: float = 0
  mean_buy: float = 0
  token: TokenPublicAsset | None = None
  updated_at: datetime

  @computed_field
  @property
  def value(self) -> float | None:
    return self.qty * self.token.price

  @computed_field
  @property
  def pnl_usd(self) -> float | None:
    return self.value - self.mean_buy * self.qty if self.qty != 0 else 0

  @computed_field
  @property
  def pnl_percent(self) -> float | None:
    if self.mean_buy != 0 and self.qty != 0:
      return (self.value / (self.mean_buy * self.qty)) - 1
