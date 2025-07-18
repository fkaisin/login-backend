import asyncio

from src.celery.fiat import get_all_fiat_history_in_db, get_daily_fiat_history_async_task

if __name__ == '__main__':
    # asyncio.run(get_all_fiat_history_in_db())
    asyncio.run(get_daily_fiat_history_async_task())
