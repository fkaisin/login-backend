import pandas as pd
from src.utils.decoration import timeit
from src.utils.tvdatafeed import (
    find_longest_history,
    get_history_ohlc_mutliple_symbols,
    get_history_ohlc_single_symbol,
    get_prices_for_dates,
    get_tv_search,
)


@timeit
def main_tradingview():
    symbol = 'RVSTWETH_649082.USD'
    exchange = 'uniswap'
    res = get_tv_search(symbol)
    # for r in res:
    #     print(r)

    # res = get_history_ohlc_single_symbol(symbol, exchange)
    print(res)
    # find_longest_history(symbol)


if __name__ == '__main__':
    main_tradingview()
