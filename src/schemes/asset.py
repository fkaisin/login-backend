import json
import uuid
from datetime import datetime

from pydantic import computed_field
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import selectinload
from sqlmodel import Field, SQLModel, select
from src.db.main import get_session
from src.schemes.token import TokenPublicAsset
from src.utils.asset import get_asset_mean_buy, get_asset_qty, get_asset_qty_by_wallet


class AssetBase(SQLModel):
    user_id: uuid.UUID | None = Field(default=None, index=True, foreign_key='users.uid', ondelete='CASCADE')
    token_id: str = Field(foreign_key='tokens.cg_id')

    qty: float = 0
    mean_buy: float = 0

    qty_by_wallet: str | None = None

    @property
    def qty_by_wallet_dict(self) -> dict:
        return json.loads(self.qty_by_wallet or '{}')

    @qty_by_wallet_dict.setter
    def qty_by_wallet_dict(self, value: dict):
        self.qty_by_wallet = json.dumps(value)

    async def update_asset(self, session):
        from src.db.models import Transaction

        try:
            statement = select(Transaction).where(Transaction.user_id == self.user_id).order_by(Transaction.date)
            results = await session.exec(statement)
            transactions = results.all()

            try:
                q, w = get_asset_qty_by_wallet(token_id=self.token_id, transactions=transactions)
                self.qty = q
                self.qty_by_wallet_dict = w

            except Exception as err:
                print('erreur dans get_asset_qty')
                print(err)
            try:
                self.mean_buy = (
                    await get_asset_mean_buy(token_id=self.token_id, transactions=transactions, session=session)
                    if self.qty != 0
                    else 0
                )
            except Exception as err:
                print('erreur dans get_asset_mean_buy')
                print(err)

        except NoResultFound:
            raise Exception('User not found in DB.')

        except Exception as err:
            print('erreur inconnue:', err)


class AssetPublic(SQLModel):
    qty: float = 0
    mean_buy: float = 0
    token: TokenPublicAsset | None = None
    updated_at: datetime
    qty_by_wallet: str | None = None

    @property
    def qty_by_wallet_dict(self) -> dict:
        return json.loads(self.qty_by_wallet or '{}')

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
