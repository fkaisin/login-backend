import asyncio

from sqlmodel import select
from src.db.main import get_session
from src.db.models import User
from src.services.history import HistoryService
from src.utils.decoration import async_timeit


@async_timeit
async def main(user: str):
    async for session in get_session():
        result = await session.exec(select(User.uid).where(User.username == user))
        user_id = result.first()

        result = await HistoryService(session).build_portfolio_df(current_user_id=user_id)
        # result.to_csv('pf.csv')

        print(result)


if __name__ == '__main__':
    user = 'fkaisin'
    asyncio.run(main(user))
