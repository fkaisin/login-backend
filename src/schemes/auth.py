from sqlmodel import SQLModel


class AccessTokenBase(SQLModel):
  access_token: str
  token_type: str = 'bearer'


class AccessTokenResponse(AccessTokenBase):
  pass
