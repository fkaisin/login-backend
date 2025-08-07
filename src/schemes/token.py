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


class TokenPublicPrice(SQLModel):
    cg_id: str
    price: float


class TokenPublicAsset(SQLModel):
    cg_id: str
    name: str
    symbol: str
    price: float
    image: str | None
    updated_at: datetime
    change_1h: float
    change_24h: float
    change_7d: float
    change_30d: float
    change_1y: float
    rank: int


class TokenId(SQLModel):
    cg_id: str


class Ticker(TokenId):
    ticker: str
    exchange: str
