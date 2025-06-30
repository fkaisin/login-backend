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

        result = await HistoryService(session).get_pf_history(current_user_id=user_id)
        pf_history = result['pivot_df']  # Tableau de quantités date vs token_id
        print(pf_history)


if __name__ == '__main__':
    user = 'fkaisin'
    asyncio.run(main(user))
