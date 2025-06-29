import pandas as pd
from src.utils.decoration import timeit
from tvDatafeed import Interval, TvDatafeed


@timeit
def get_history_ohlc_single_symbol(
    symbol: str, exchange: str, n_bars: int = 10000, interval: Interval = Interval.in_daily
):
    tv = TvDatafeed()
    res = tv.get_hist(symbol, exchange, interval, n_bars)
    return res


@timeit
def get_history_ohlc_mutliple_symbols(
    symbol: list, exchange: list, n_bars: int = 10000, interval: Interval = Interval.in_daily
):
    tv = TvDatafeed()
    all_results = [None] * len(symbol)
    for i, (symb, exch) in enumerate(zip(symbol, exchange)):
        print(f'Searching {symb} on {exch}...')
        res = tv.get_hist(symb, exch, interval, n_bars)
        if res is None:
            continue
        print('length:', len(res))
        all_results[i] = res
    return all_results


def get_prices_for_dates(df, date_list):
    # Normaliser l'index du DataFrame pour ignorer l'heure
    df_normalized = df.copy()
    df_normalized.index = df_normalized.index.normalize()

    # Convertir les dates en pd.Timestamp (avec heure = 00:00:00)
    date_list_ts = [pd.to_datetime(d).normalize() for d in date_list]

    results = []
    for dt in date_list_ts:
        if dt in df_normalized.index:
            close_price = float(df_normalized.loc[dt, 'close'])
            results.append({'date': dt.strftime('%Y-%m-%d'), 'close': close_price})
        else:
            # Optionnel : ajouter un None ou ignorer
            results.append({'date': dt.strftime('%Y-%m-%d'), 'close': None})

    return results


@timeit
def get_tv_search(symbol: str, exchange: str = ''):
    def strip_em_tags(text):
        return text.replace('<em>', '').replace('</em>', '')

    tv = TvDatafeed()
    results = tv.search_symbol(symbol, exchange)
    return [
        {
            'symbol': strip_em_tags(r.get('symbol', '')),
            'exchange': r.get('exchange', ''),
            'description': strip_em_tags(r.get('description', '')),
            'type': r.get('type', ''),
            # 'currency_code': r.get('currency_code', ''),
        }
        for r in results
        if r.get('type') in ['spot', 'index'] and r.get('currency_code', '').lower().startswith('usd')
    ]


def find_longest_history(exchange_list):
    symbols = [r['symbol'] for r in exchange_list]
    exchanges = [r['exchange'] for r in exchange_list]
    print(f'{len(exchange_list)} exchanges to check...')
    res = get_history_ohlc_mutliple_symbols(symbols, exchanges)
    max_length = -1
    max_index = -1

    for i, r in enumerate(res):
        if r is None:
            continue
        length = len(r)
        print(f'Index {i}, symbol {symbols[i]}, exchange {exchanges[i]}, length = {length}')
        if length > max_length:
            max_length = length
            max_index = i

    if max_index != -1:
        max_symbol = symbols[max_index]
        max_exchange = exchanges[max_index]
        print(f"Le symbol le plus long est {max_symbol} sur l'exchange {max_exchange} avec {max_length} lignes.")
        return exchange_list[max_index]
    else:
        print('Aucune donnée historique trouvée.')
        return None
