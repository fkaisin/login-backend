from sqlmodel import Field, SQLModel


class TokenBase(SQLModel):
    cg_id: str = Field(primary_key=True)
    symbol: str
    name: str
