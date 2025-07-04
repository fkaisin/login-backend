import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel
from src.schemes.token import TokenBase
from src.schemes.transaction import TransactionBase
from src.schemes.user import UserBase


class User(UserBase, table=True):
  __tablename__ = 'users'  # type: ignore
  uid: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
  hashed_password: str
  rank: int = 1020
  created_at: datetime = Field(default_factory=datetime.now)
  updated_at: datetime = Field(default_factory=datetime.now, sa_column_kwargs={'onupdate': datetime.now})

  transactions: list['Transaction'] = Relationship(back_populates='user', cascade_delete=True)


class Token(TokenBase, table=True):
  __tablename__ = 'tokens'  # type: ignore
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


class DtaoHistory(SQLModel, table=True):
  __tablename__ = 'dtaohistory'  # type: ignore
  uid: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
  netuid: int = Field(index=True)
  date: datetime = Field(index=True)
  price: float
