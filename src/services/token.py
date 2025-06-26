from sqlmodel import or_, select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.models import Token


class TokenService:
  def __init__(self, session: AsyncSession):
    self.session = session

  async def search_tokens(self, search_string):
    search = f'%{search_string}%'
    statement = select(Token).where(
      or_(Token.symbol.ilike(search), Token.cg_id.ilike(search), Token.name.ilike(search))  # type: ignore
    )
    result = await self.session.exec(statement)
    tokens = result.all()

    return tokens
