import asyncio
import uuid

from sqlmodel import Session, create_engine, select, text
from src.db.models import Transaction
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


if __name__ == '__main__':
    main_tradingview()
