from datetime import datetime

from sqlmodel import SQLModel


class UserHistoryBase(SQLModel):
    date: datetime
    value_in_usd: float
    value_in_eur: float
    value_in_cad: float
    value_in_chf: float
