from datetime import datetime

from sqlmodel import SQLModel


class UserHistoryBase(SQLModel):
    date: datetime
    value_in_usd: float
    value_in_eur: float
    value_in_cad: float
    value_in_chf: float
    cash_in_usd: float
    cash_in_eur: float
    cash_in_cad: float
    cash_in_chf: float
    pnl_percent_fiat_usd: float
    pnl_percent_fiat_eur: float
    pnl_percent_fiat_cad: float
    pnl_percent_fiat_chf: float
