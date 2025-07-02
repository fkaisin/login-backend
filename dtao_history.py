import asyncio
import time

import aiohttp
import pandas as pd
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from src.db.main import get_session
from src.db.models import DtaoHistory
from src.utils.decoration import async_timeit
from src.utils.tvdatafeed import get_history_ohlc_single_symbol

BASE_URL = 'https://taostats.io/api/dtao/udf/history'
COINGECKO_MARKET_URL = 'https://api.coingecko.com/api/v3/coins/markets'
CONCURRENCY = 20


def sort_columns_num(df, prefix='SN'):
    def extract_num(col):
        return int(col[len(prefix) :]) if isinstance(col, str) and col.startswith(prefix) else float('inf')

    return df[sorted(df.columns, key=extract_num)]


async def fetch_history(session, symbol, from_ts, to_ts, semaphore):
    params = {'symbol': symbol, 'resolution': '1D', 'from': from_ts, 'to': to_ts}
    async with semaphore:
        try:
            async with session.get(BASE_URL, params=params) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return symbol, data
        except Exception as e:
            print(f'Erreur API pour {symbol} : {e}')
            return symbol, None


async def insert_in_db(pivot_close: pd.DataFrame, batch_size: int = 500):
    pivot_close.index.name = 'date_day'
    df_long = pivot_close.reset_index().melt(id_vars='date_day', var_name='cg_id', value_name='close')
    df_long['date'] = pd.to_datetime(df_long['date_day'])
    df_long = df_long.dropna(subset=['close'])
    df_long = df_long[df_long['close'] != 0]
    records = df_long[['cg_id', 'date', 'close']].to_dict(orient='records')
    async for session in get_session():
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            stmt = sqlite_insert(DtaoHistory).values(batch)
            stmt = stmt.on_conflict_do_update(index_elements=['cg_id', 'date'], set_={'close': stmt.excluded.close})
            await session.exec(stmt)
        await session.commit()


async def fetch_cg_ids():
    cg_ids = {}
    async with aiohttp.ClientSession() as session:
        params = {'category': 'bittensor-subnets', 'vs_currency': 'usd'}
        async with session.get(COINGECKO_MARKET_URL, params=params) as resp:
            data = await resp.json()
            for coin in data:
                symbol = coin.get('symbol', '').upper()
                if symbol.startswith('SN'):
                    cg_ids[symbol] = coin['id']
    return cg_ids


async def main():
    semaphore = asyncio.Semaphore(CONCURRENCY)
    to_ts = int(time.time())
    from_ts = to_ts - 365 * 24 * 3600
    all_data, no_data_streak, subnet_id = [], 0, 1

    async with aiohttp.ClientSession() as session:
        while no_data_streak < 3:
            batch = [
                fetch_history(session, f'SUB-{subnet_id + i}', from_ts, to_ts, semaphore) for i in range(CONCURRENCY)
            ]
            results = await asyncio.gather(*batch)
            for symbol, data in results:
                print(f'Traitement {symbol} ...')
                if data and data.get('s') == 'ok' and data.get('t'):
                    df = pd.DataFrame(
                        {
                            'symbol': symbol.replace('SUB-', 'SN'),
                            'timestamp': data['t'],
                            'date': pd.to_datetime(data['t'], unit='s'),
                            'open': data['o'],
                            'high': data['h'],
                            'low': data['l'],
                            'close': data['c'],
                            'volume': data['v'],
                        }
                    )
                    all_data.append(df)
                    no_data_streak = 0
                    print(f'  OK, {len(df)} points ajoutés.')
                else:
                    print(f'  Pas de données pour {symbol}.')
                    no_data_streak += 1
                    if no_data_streak >= 3:
                        break
            subnet_id += CONCURRENCY

    print('\nFin de la collecte (3 symboles consécutifs sans données).')
    if not all_data:
        print('Aucune donnée récupérée.')
        return

    full_df = pd.concat(all_data, ignore_index=True).dropna(subset=['close'])
    full_df['date_day'] = full_df['date'].dt.normalize()
    full_df.sort_values('date', inplace=True)
    df_last = full_df.groupby(['date_day', 'symbol'], as_index=False).last()
    pivot_close = df_last.pivot(index='date_day', columns='symbol', values='close')
    pivot_close = sort_columns_num(pivot_close)
    full_date_range = pd.date_range(start=pivot_close.index.min(), end=pd.Timestamp.today().normalize(), freq='D')
    pivot_close = pivot_close.reindex(full_date_range).ffill().fillna(0)

    df_tao = get_history_ohlc_single_symbol('TAOUSDT', 'MEXC')
    df_tao['date_day'] = df_tao.index.normalize()
    df_tao_close = df_tao.set_index('date_day')['close']
    df_tao_close.name = 'SN0'
    pivot_close = pivot_close.merge(df_tao_close, left_index=True, right_index=True, how='left')
    pivot_close = sort_columns_num(pivot_close)

    sn0 = pivot_close['SN0']
    sn_cols = [col for col in pivot_close.columns if col.startswith('SN') and col != 'SN0']
    pivot_close[sn_cols] = pivot_close[sn_cols].multiply(sn0, axis=0)

    cg_ids = await fetch_cg_ids()
    pivot_close = pivot_close.rename(columns={col: cg_ids.get(col, col) for col in pivot_close.columns})
    pivot_close.columns.name = 'cg_id'
    print(pivot_close)

    await insert_in_db(pivot_close)


if __name__ == '__main__':
    asyncio.run(main())
