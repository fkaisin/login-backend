import asyncio
import time

import aiohttp
import pandas as pd

BASE_URL = 'https://taostats.io/api/dtao/udf/history'
CONCURRENCY = 5  # nombre max d'appels simultanés


async def get_history(session, symbol, from_ts, to_ts, resolution='1D', semaphore=None):
    params = {
        'symbol': symbol,
        'resolution': resolution,
        'from': from_ts,
        'to': to_ts,
    }
    if semaphore:
        async with semaphore:
            return await _fetch(session, symbol, params)
    else:
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


async def main():
    semaphore = asyncio.Semaphore(CONCURRENCY)
    to_ts = int(time.time())
    from_ts = to_ts - 365 * 24 * 3600

    all_data = []
    no_data_streak = 0
    subnet_id = 1

    async with aiohttp.ClientSession() as session:
        while no_data_streak < 3:
            batch = []
            for i in range(CONCURRENCY):
                symbol = f'SUB-{subnet_id + i}'
                batch.append(get_history(session, symbol, from_ts, to_ts, semaphore=semaphore))

            results = await asyncio.gather(*batch)

            for symbol, data in results:
                print(f'Traitement {symbol} ...')
                if data and data.get('s') == 'ok' and data.get('t'):
                    timestamps = data['t']
                    opens = data['o']
                    highs = data['h']
                    lows = data['l']
                    closes = data['c']
                    volumes = data['v']

                    df = pd.DataFrame(
                        {
                            'symbol': symbol,
                            'timestamp': timestamps,
                            'date': pd.to_datetime(timestamps, unit='s'),
                            'open': opens,
                            'high': highs,
                            'low': lows,
                            'close': closes,
                            'volume': volumes,
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

    if all_data:
        full_df = pd.concat(all_data, ignore_index=True)
        print(f'Total lignes récupérées : {len(full_df)}')
        print(full_df.head(10))

        # dupes = full_df.duplicated(subset=['date', 'symbol'], keep=False)
        # print(full_df[dupes].sort_values(['symbol', 'date']))

        # Supprimer les lignes où close est NaN
        full_df_clean = full_df.dropna(subset=['close'])

        pivot_close = full_df_clean.pivot_table(
            index='date',
            columns='symbol',
            values='close',
            aggfunc='first',  # ou 'mean' si tu préfères
        )

        print(pivot_close.head())

    else:
        print('Aucune donnée récupérée.')


if __name__ == '__main__':
    asyncio.run(main())
