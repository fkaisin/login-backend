import pandas as pd
from src.utils.tvdatafeed import (
    get_history_ohlc_mutliple_symbols,
    get_history_ohlc_single_symbol,
    get_prices_for_dates,
    get_tv_search,
)


def main_tradingview():
    # symbol = 'PEPEUSDT'
    # exchange = 'BINANCE'
    # dates = ['2025-06-25', '2025-06-27', '2025-06-30']

    # df = get_history_ohlc_single_symbol(symbol, exchange)
    # print(df)
    # res = get_prices_for_dates(df, dates)
    # print(res)

    symbol = 'naviusd'
    exchange = ''

    res = get_tv_search(symbol, exchange)
    for r in res:
        print(r)


if __name__ == '__main__':
    main_tradingview()
