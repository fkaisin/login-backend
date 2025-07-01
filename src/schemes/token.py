from datetime import datetime

from sqlmodel import Field, SQLModel


class TokenBase(SQLModel):
    cg_id: str = Field(primary_key=True)
    symbol: str = Field(index=True)
    name: str
    rank: int = 5000
    mcap: int | None = 0
    image: str | None = None
    price: float
    change_1h: float = 0
    change_24h: float = 0
    change_7d: float = 0
    change_30d: float = 0
    change_1y: float = 0


class TokenPublicSmall(SQLModel):
    cg_id: str
    symbol: str
    name: str
    rank: int


class TokenPublicAsset(SQLModel):
    cg_id: str
    name: str
    symbol: str
    price: float
    image: str
    updated_at: datetime


class TokenId(SQLModel):
    cg_id: str
