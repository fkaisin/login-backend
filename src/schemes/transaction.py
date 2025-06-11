import uuid
from datetime import datetime

from pydantic import ConfigDict, computed_field
from sqlmodel import Field, SQLModel
from src.schemes.token import TokenBase


class TransactionBase(SQLModel):
    date: datetime
    type: str
    qty_a: float
    price: float | None = None
    destination: str
    origin: str | None = None
    qty_f: float | None = None
    value_f: float | None = None
    value_a: float | None = None


class TransactionPublic(TransactionBase):
    id: uuid.UUID
    actif_a: TokenBase | None = None
    actif_v: TokenBase | None = None
    actif_f: TokenBase | None = None

    @computed_field
    @property
    def qty_v(self) -> float | None:
        if self.qty_a is not None and self.price is not None:
            return round(self.qty_a * self.price, 10)
        return None


class TransactionCreate(TransactionBase):
    actif_a_id: str | None = None
    actif_v_id: str | None = None
    actif_f_id: str | None = None


class TransactionUpdate(SQLModel):
    date: datetime | None = None
    type: str | None = None
    qty_a: float | None = None
    price: float | None = None
    destination: str | None = None
    origin: str | None = None
    qty_f: float | None = None
    value_f: float | None = None
    value_a: float | None = None
    actif_a_id: str | None = None
    actif_v_id: str | None = None
    actif_f_id: str | None = None
