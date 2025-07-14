import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class UserBase(SQLModel):
    username: str = Field(index=True)
    email: str = Field(index=True)


class UserCreate(UserBase):
    password: str


class UserPublic(UserBase):
    uid: uuid.UUID
    created_at: datetime
    updated_at: datetime
    rank: int = 1020


class UserUpdateAdmin(SQLModel):
    username: str | None = None
    email: str | None = None
    new_password: str | None = None


class UserUpdate(UserUpdateAdmin):
    old_password: str | None = None
    fiat_id: str | None = None
    calc_method_display: str | None = None
    calc_method_tax: str | None = None


class UserLogin(SQLModel):
    username: str
    password: str


class UserParams(SQLModel):
    fiat_id: str
    calc_method_display: str
    calc_method_tax: str
    tax_principle: str


class UserParamsUpdate(SQLModel):
    fiat_id: str | None = None
    calc_method_display: str | None = None
    calc_method_tax: str | None = None
    tax_principle: str | None = None
