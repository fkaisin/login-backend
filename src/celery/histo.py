import logging
import time
from io import StringIO

import pandas as pd
import requests
from fastapi import HTTPException, status
from src.config import settings
from src.utils.calculations import get_cash_in_usd
from src.utils.tvdatafeed import get_history_ohlc_single_symbol

# Setup logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def compute_pf_history(df_qty_json, tv_list_data, transactions):
    """
    Calcule l'historique de valeur du portefeuille (avec df_qty) via Celery.

    :param df_qty_json: un DataFrame en format JSON (orient='split')
    :param tv_list_data: liste de dicts contenant les tickers (cg_id, ticker, exchange)
    :return: dict contenant 'result' et 'ignored_tokens'
    """
    df_qty = pd.read_json(StringIO(df_qty_json), orient='split')

    first_date_qty = df_qty.index[0]
    last_date_qty = df_qty.index[-2]
    all_histories = []
    ignored_tokens = []

    for token in df_qty.columns:
        dates = df_qty.index[df_qty[token] > 0]
        first_date = dates.min()
        last_date = dates.max()

        if token in settings.STABLECOINS:
            date_range = pd.date_range(start=first_date, end=last_date, freq='D')
            df_stable = pd.DataFrame({'datetime': date_range, 'close': 1.0, 'token': token})
            all_histories.append(df_stable)

        elif token in settings.FIATS:
            continue

        else:
            ticker_obj = next((t for t in tv_list_data if t['cg_id'] == token), None)
            ticker = ticker_obj['ticker'] if ticker_obj else None
            exchange = ticker_obj['exchange'] if ticker_obj else None

            if exchange == 'taostats.io':
                token_full_history = get_dtao_history(ticker)
            else:
                token_full_history = get_history_ohlc_single_symbol(ticker, exchange)
                if token_full_history is None:
                    ignored_tokens.append(token)
                    continue

            token_history = token_full_history.loc[first_date:last_date, ['close']].copy()
            token_history['token'] = token
            token_history = token_history.reset_index()
            all_histories.append(token_history)

            time.sleep(0.5)

    if not all_histories:
        return {'result': [], 'ignored_tokens': ignored_tokens}

    df_all_history = pd.concat(all_histories, ignore_index=True)
    df_all_history['date'] = pd.to_datetime(df_all_history['datetime']).dt.date

    full_date_index = pd.date_range(start=first_date_qty.date(), end=last_date_qty.date(), freq='D')
    df_price = (
        df_all_history.pivot(index='date', columns='token', values='close')
        .sort_index()
        .reindex(full_date_index)
        .fillna(0)
    )
    df_price.index.name = 'date'

    common_tokens = df_price.columns.intersection(df_qty.columns)
    common_dates = df_price.index.intersection(df_qty.index)
    price_aligned = df_price.loc[common_dates, common_tokens]
    qty_aligned = df_qty.loc[common_dates, common_tokens]
    df_value = price_aligned * qty_aligned
    df_value['total_fiat_usd'] = df_value.sum(axis=1)

    df_totals = df_value[['total_fiat_usd']].copy()

    # Ajout du cash in

    # print(df_totals)
    # get_cash_in_usd(transactions, df_totals)

    # Fin ajout du cash in

    df_totals.reset_index(inplace=True)
    result = df_totals.to_dict(orient='records')

    return {'result': result, 'ignored_tokens': ignored_tokens}


def get_dtao_history(ticker: str):
    BASE_URL = 'https://taostats.io/api/dtao/udf/history'

    digits = ''.join(filter(str.isdigit, ticker))
    if not digits:
        print(f'Ticker invalide : {ticker}')
        return None
    number = int(digits)
    symbol = f'SUB-{number}'

    to_ts = int(time.time())
    from_ts = to_ts - 10 * 365 * 24 * 3600  # 10 ans

    params = {'symbol': symbol, 'resolution': '1D', 'from': from_ts, 'to': to_ts}

    try:
        resp = requests.get(BASE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f'Erreur API pour {symbol} : {e}')
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Erreur lors de la récupération de l'historique du dtao {symbol}",
        )

    if data and data.get('s') == 'ok' and data.get('t'):
        df = pd.DataFrame(
            {
                'datetime': pd.to_datetime(data['t'], unit='s').normalize(),
                'symbol': symbol.replace('SUB-', 'SN'),
                'open': data['o'],
                'high': data['h'],
                'low': data['l'],
                'close': data['c'],
                'volume': data['v'],
            }
        )
    else:
        return None

    df.set_index('datetime', inplace=True)

    df_tao = get_history_ohlc_single_symbol('TAOUSDT', 'MEXC')

    df.index = pd.to_datetime(df.index).normalize()
    df_tao.index = pd.to_datetime(df_tao.index).normalize()

    df_combined = df.join(df_tao[['close']], rsuffix='_tao', how='left')
    df_combined['close'] = df_combined['close'] * df_combined['close_tao']

    df = df_combined
    df = df[~df.index.duplicated(keep='first')]

    return df
