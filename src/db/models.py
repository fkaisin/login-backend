import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint
from src.schemes.asset import AssetBase
from src.schemes.history import UserHistoryBase
from src.schemes.token import TokenBase
from src.schemes.transaction import TransactionBase
from src.schemes.user import UserBase


class User(UserBase, table=True):
    __tablename__ = 'users'  # type: ignore
    uid: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    rank: int = 1020
    fiat_id: str = Field(default='fiat_eur', foreign_key='tokens.cg_id')
    calc_method_display: str = Field(default='weighted average')
    calc_method_tax: str = Field(default='fifo')
    tax_principle: str = Field(default='pv')
    history_init: bool = Field(default=False)
    cash_in_usd: float = Field(default=0.0)
    cash_in_eur: float = Field(default=0.0)
    cash_in_cad: float = Field(default=0.0)
    cash_in_chf: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now, sa_column_kwargs={'onupdate': datetime.now})

    transactions: list['Transaction'] = Relationship(back_populates='user', cascade_delete=True)
    assets: list['Asset'] = Relationship(back_populates='user', cascade_delete=True)
    pf_history: list['UserPfHistory'] = Relationship(back_populates='user', cascade_delete=True)


class Token(TokenBase, table=True):
    __tablename__ = 'tokens'  # type: ignore
    updated_at: datetime = Field(default_factory=datetime.now, sa_column_kwargs={'onupdate': datetime.now})


class Asset(AssetBase, table=True):
    __tablename__ = 'assets'  # type: ignore
    __table_args__ = (UniqueConstraint('token_id', 'user_id', name='unique_token_user'),)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    token: Token = Relationship()
    user: User = Relationship(back_populates='assets')
    updated_at: datetime = Field(default_factory=datetime.now, sa_column_kwargs={'onupdate': datetime.now})


class Transaction(TransactionBase, table=True):
    __tablename__ = 'transactions'  # type: ignore
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID | None = Field(default=None, index=True, foreign_key='users.uid', ondelete='CASCADE')

    user: User = Relationship(back_populates='transactions')

    actif_a_id: str | None = Field(default=None, foreign_key='tokens.cg_id', ondelete='SET NULL')
    actif_v_id: str | None = Field(default=None, foreign_key='tokens.cg_id', ondelete='SET NULL')
    actif_f_id: str | None = Field(default=None, foreign_key='tokens.cg_id', ondelete='SET NULL')

    actif_a: Optional['Token'] = Relationship(
        sa_relationship_kwargs={
            'foreign_keys': lambda: [Transaction.__table__.c.actif_a_id]  # type: ignore[attr-defined]
        }
    )
    actif_v: Optional['Token'] = Relationship(
        sa_relationship_kwargs={
            'foreign_keys': lambda: [Transaction.__table__.c.actif_v_id]  # type: ignore[attr-defined]
        }
    )
    actif_f: Optional['Token'] = Relationship(
        sa_relationship_kwargs={
            'foreign_keys': lambda: [Transaction.__table__.c.actif_f_id]  # type: ignore[attr-defined]
        }
    )


class SmallToken(SQLModel, table=True):
    __tablename__ = 'smalltokens'  # type: ignore
    id: str = Field(primary_key=True)


class FiatHistory(SQLModel, table=True):
    __tablename__ = 'fiat_history'  # type: ignore
    id: str = Field(primary_key=True)
    cg_id: str
    date: datetime = Field(index=True)
    open: float
    high: float
    low: float
    close: float


class DtaoCgList(SQLModel, table=True):
    __tablename__ = 'dtao_list'
    cg_id: str = Field(primary_key=True)
    symbol: str = Field(index=True)


class UserPfHistory(UserHistoryBase, table=True):
    __tablename__ = 'user_portfolio_history'
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID | None = Field(default=None, index=True, foreign_key='users.uid', ondelete='CASCADE')

    user: User = Relationship(back_populates='pf_history')
