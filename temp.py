import asyncio
import uuid

from sqlmodel import Session, create_engine, select, text
from src.db.main import get_session
from src.db.models import Transaction, User
from src.utils.asset import get_fiat_price
from src.utils.decoration import timeit
from src.utils.tvdatafeed import (
    find_longest_history,
    get_history_ohlc_mutliple_symbols,
    get_history_ohlc_single_symbol,
    get_prices_for_dates,
    get_tv_search,
)

sqlite_url = 'sqlite:///./src/db/database.sqlite'

engine = create_engine(sqlite_url, echo=True)
with engine.begin() as conn:
    conn.execute(text('PRAGMA foreign_keys=ON'))  # for SQLite only


@timeit
def main_tradingview():
    symbol = 'arcusdt'
    exchange = 'bitget'
    # res = get_tv_search(symbol)
    # for r in res:
    #     print(r)

    res = get_history_ohlc_single_symbol(symbol, exchange)
    print(res)
    # find_longest_history(symbol)


async def get_cash_in():
    from src.utils.calculations import get_cash_in_usd

    # user_uid = uuid.UUID('197ea9b4fed7402dbffc6e569280e972')  # test
    user_uid = uuid.UUID('979863c4ba2b47998417dfca58aa477f')  # fkaisin
    async for session in get_session():
        statement = select(Transaction).where(Transaction.user_id == user_uid)
        results = await session.exec(statement)
        transactions = results.all()
        user = await session.get(User, user_uid)

    transactions_data = [t.model_dump() for t in transactions]

    await get_cash_in_usd(transactions_data, None)


if __name__ == '__main__':
    # main_tradingview()
    asyncio.run(get_cash_in())
