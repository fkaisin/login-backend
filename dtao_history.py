import asyncio
import time

import aiohttp
import pandas as pd
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import select
from src.db.main import get_session
from src.db.models import DtaoHistory
from src.utils.decoration import async_timeit
from src.utils.tvdatafeed import get_history_ohlc_single_symbol

BASE_URL = 'https://taostats.io/api/dtao/udf/history'
COINGECKO_MARKET_URL = 'https://api.coingecko.com/api/v3/coins/markets'

CONCURRENCY = 20
BATCH_SIZE = 1000


async def get_history(session, symbol, from_ts, to_ts, resolution='1D', semaphore=None):
    params = {'symbol': symbol, 'resolution': resolution, 'from': from_ts, 'to': to_ts}
    if semaphore:
        async with semaphore:
            return await _fetch(session, symbol, params)
    return await _fetch(session, symbol, params)


async def _fetch(session, symbol, params):
    try:
        async with session.get(BASE_URL, params=params) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return symbol, data
    except Exception as e:
        print(f'Erreur API pour {symbol} : {e}')
        return symbol, None


def sort_columns_num(df, prefix='SN'):
    # Trie les colonnes SN numériquement (ex: SN1, SN2, ...)
    def extract_num(col):
        if isinstance(col, str) and col.startswith(prefix):
            return int(col[len(prefix) :])
        return float('inf')

    return df[sorted(df.columns, key=extract_num)]


@async_timeit
async def insert_in_db(pivot_close: pd.DataFrame, batch_size: int = 500):
    # Assure que l'index porte bien le nom 'date_day' (obligatoire pour melt)
    pivot_close.index.name = 'date_day'

    # Transformation du pivot en format long
    df_long = pivot_close.reset_index().melt(id_vars='date_day', var_name='cg_id', value_name='close')

    # Convertit les dates en datetime natif (SQLite aime bien)
    df_long['date'] = pd.to_datetime(df_long['date_day'])

    # Supprime les lignes inutiles (ex: NaN ou None si tu veux)
    df_long = df_long.dropna(subset=['close'])
    df_long = df_long[df_long['close'] != 0]

    # Prépare les données en dictionnaires
    records = df_long[['cg_id', 'date', 'close']].to_dict(orient='records')

    async for session in get_session():
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]

            stmt = sqlite_insert(DtaoHistory).values(batch)
            stmt = stmt.on_conflict_do_update(index_elements=['cg_id', 'date'], set_={'close': stmt.excluded.close})

            await session.exec(stmt)

        await session.commit()


async def main():
    semaphore = asyncio.Semaphore(CONCURRENCY)
    to_ts = int(time.time())
    from_ts = to_ts - 365 * 24 * 3600

    all_data = []
    no_data_streak = 0
    subnet_id = 1

    async with aiohttp.ClientSession() as session:
        # Récupération asynchrone par batch jusqu'à 3 symboles sans données consécutifs
        while no_data_streak < 3:
            batch = [
                get_history(session, f'SUB-{subnet_id + i}', from_ts, to_ts, semaphore=semaphore)
                for i in range(CONCURRENCY)
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

    # Concatène et nettoie les données récupérées
    full_df = pd.concat(all_data, ignore_index=True)
    print(f'Total lignes récupérées : {len(full_df)}')
    full_df = full_df.dropna(subset=['close']).copy()
    full_df['date_day'] = full_df['date'].dt.normalize()
    full_df.sort_values('date', inplace=True)
    df_last = full_df.groupby(['date_day', 'symbol'], as_index=False).last()

    # Pivot pour obtenir les closes par date et symbol, tri et reindexation par dates complètes
    pivot_close = df_last.pivot(index='date_day', columns='symbol', values='close')
    pivot_close = sort_columns_num(pivot_close)
    full_date_range = pd.date_range(start=pivot_close.index.min(), end=pd.Timestamp.today().normalize(), freq='D')
    pivot_close = pivot_close.reindex(full_date_range)
    pivot_close.ffill(inplace=True)
    pivot_close.fillna(0, inplace=True)

    # Récupère les closes du symbole TAOUSDT (SN0), aligne et merge avec pivot_close
    df_tao = get_history_ohlc_single_symbol('TAOUSDT', 'MEXC')
    df_tao['date_day'] = df_tao.index.normalize()
    df_tao_close = df_tao.set_index('date_day')['close']
    df_tao_close.name = 'SN0'
    pivot_close = pivot_close.merge(df_tao_close, left_index=True, right_index=True, how='left')
    pivot_close = sort_columns_num(pivot_close)

    # Multiplie chaque colonne SN1+ par la colonne SN0, ligne par ligne
    sn0 = pivot_close['SN0']
    sn_cols = [col for col in pivot_close.columns if col.startswith('SN') and col != 'SN0']
    pivot_close[sn_cols] = pivot_close[sn_cols].multiply(sn0, axis=0)

    # Ajouter les cg_id correspondants pour chaque symbole SN
    sn_to_cgid = await get_cg_ids_for_sn(pivot_close)

    # Ajout de la colonne cg_id au DataFrame
    pivot_close = pivot_close.rename(columns=sn_to_cgid)

    # print(pivot_close.head())

    # Ajouter à la db
    # await insert_in_db(pivot_close)


async def get_coins_in_category(category: str, currency: str = 'usd'):
    async with aiohttp.ClientSession() as session:
        params = {'category': category, 'vs_currency': currency}
        async with session.get(COINGECKO_MARKET_URL, params=params) as resp:
            data = await resp.json()
            print(f"Coins récupérés pour la catégorie '{category}':")
            for coin in data:
                print(f'{coin["id"]} - {coin["symbol"]} - {coin["name"]}')


if __name__ == '__main__':
    # asyncio.run(main())
    asyncio.run(get_coins_in_category('bittensor-subnets'))
