import asyncio
from datetime import datetime, timedelta

import pandas as pd
from sqlmodel import delete, select
from src.db.main import get_session
from src.db.models import FiatHistory, Token
from src.utils.tvdatafeed import get_history_ohlc_mutliple_symbols
from tvDatafeed import Interval

FIAT_LIST = [
    ('EURUSD', 'OANDA', 'Euro', 'EUR', 'fiat_eur'),
    ('CADUSD', 'SAXO', 'Dollar canadien', 'CAD', 'fiat_cad'),
    ('CHFUSD', 'SAXO', 'Franc suisse', 'CHF', 'fiat_chf'),
]
symbols = [s for s, _, _, _, _ in FIAT_LIST]
exchanges = [e for _, e, _, _, _ in FIAT_LIST]


def get_closest_past_value(df, target_time):
    if df is None or df.empty:
        return None
    df.index = pd.to_datetime(df.index)
    past_times = df.index[df.index <= target_time]
    if not past_times.empty:
        closest_time = past_times[-1]
        return float(df.loc[closest_time]['close'])
    return None


def calc_change(current, past):
    if current is None or past is None or past == 0:
        return 0
    return (current - past) / past


def get_fiat_realtime_data():
    now = datetime.now().replace(second=0, microsecond=0)
    result = []

    # Get hourly and minute history for all symbols
    h1_all = get_history_ohlc_mutliple_symbols(symbols, exchanges, n_bars=10000, interval=Interval.in_1_hour)
    m1_all = get_history_ohlc_mutliple_symbols(symbols, exchanges, n_bars=2000, interval=Interval.in_1_minute)

    for i, (_, _, name, symbol, id) in enumerate(FIAT_LIST):
        h1_hist = h1_all[i]
        m1_hist = m1_all[i]

        m1_close = get_closest_past_value(m1_hist, now - timedelta(minutes=1))
        h1_close = get_closest_past_value(m1_hist, now - timedelta(hours=1))
        h24_close = get_closest_past_value(m1_hist, now - timedelta(hours=24))
        d7_close = get_closest_past_value(h1_hist, now - timedelta(days=7))
        d30_close = get_closest_past_value(h1_hist, now - timedelta(days=30))
        y1_close = get_closest_past_value(h1_hist, now - timedelta(days=365))

        dict = {
            'cg_id': id,
            'name': name,
            'symbol': symbol,
            'price': m1_close,
            'change_1h': calc_change(m1_close, h1_close),
            'change_24h': calc_change(m1_close, h24_close),
            'change_7d': calc_change(m1_close, d7_close),
            'change_30d': calc_change(m1_close, d30_close),
            'change_1y': calc_change(m1_close, y1_close),
            'rank': 0,
        }

        tok = Token(**dict)
        result.append(tok)
    usd = Token(
        **{
            'cg_id': 'fiat_usd',
            'name': 'Dollar US',
            'symbol': 'USD',
            'price': 1,
            'change_1h': 0,
            'change_24h': 0,
            'change_7d': 0,
            'change_30d': 0,
            'change_1y': 0,
            'rank': 0,
        }
    )
    result.append(usd)

    return result


async def write_realtime_to_db(fiat_list):
    async for session in get_session():
        statement = select(Token).where(Token.cg_id.in_(['fiat_eur', 'fiat_cad', 'fiat_chf', 'fiat_usd']))
        res = await session.exec(statement)
        fiat_db = res.all()

        for fiat_to_update in fiat_db:
            corresponding_fiat = next((fiat for fiat in fiat_list if fiat.cg_id == fiat_to_update.cg_id), None)
            fiat_to_update.sqlmodel_update(corresponding_fiat)
            session.add(fiat_to_update)

        await session.commit()


async def fiat_realtime_async_task():
    fiat_data = get_fiat_realtime_data()
    await write_realtime_to_db(fiat_data)


async def get_all_fiat_history_in_db():
    daily_hist = get_history_ohlc_mutliple_symbols(symbols, exchanges)

    fiat_histories = []

    for i, (_, _, _, symbol, cg_id) in enumerate(FIAT_LIST):
        df = daily_hist[i]
        if df is None or df.empty:
            continue

        df.index = pd.to_datetime(df.index)

        for dt, row in df.iterrows():
            fiat_histories.append(
                FiatHistory(
                    id=f'{symbol.lower()}_{dt.strftime("%d%m%Y")}',
                    cg_id=cg_id,
                    date=dt.date(),
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                )
            )

    async for session in get_session():
        await session.exec(delete(FiatHistory))
        await session.commit()
        session.add_all(fiat_histories)
        await session.commit()
        print(f'{len(fiat_histories)} entrées insérées dans FiatHistory')


async def get_daily_fiat_history_async_task():
    symbols = [s for s, _, _, _, _ in FIAT_LIST]
    exchanges = [e for _, e, _, _, _ in FIAT_LIST]

    # Récupération des données journalières
    daily_histories = get_history_ohlc_mutliple_symbols(symbols, exchanges, n_bars=10, interval=Interval.in_daily)

    # Dates pour les 3 derniers jours
    target_dates = sorted(
        {(datetime.now() - timedelta(days=i + 1)).replace(hour=0, minute=0, second=0, microsecond=0) for i in range(3)}
    )

    fiat_histories = []

    async for session in get_session():
        # Récupération des IDs existants
        stmt = select(FiatHistory.id)
        res = await session.exec(stmt)
        existing_ids = set(res.all())

        for i, (_, _, _, symbol, cg_id) in enumerate(FIAT_LIST):
            df = daily_histories[i]
            if df is None or df.empty:
                continue

            df.index = pd.to_datetime(df.index).tz_localize(None)
            df = df.sort_index()

            for target_date in target_dates:
                entry_id = f'{symbol.lower()}_{target_date.strftime("%d%m%Y")}'
                if entry_id in existing_ids:
                    continue

                # Si la date exacte n'est pas dans l'index, on cherche la dernière date avant
                if target_date in df.index:
                    row = df.loc[target_date]
                else:
                    prior_dates = df[df.index < target_date]
                    if prior_dates.empty:
                        continue  # Pas de données disponibles avant cette date
                    last_available = prior_dates.iloc[-1]
                    row = last_available

                fiat_histories.append(
                    FiatHistory(
                        id=entry_id,
                        cg_id=cg_id,
                        date=target_date,
                        open=float(row['open']),
                        high=float(row['high']),
                        low=float(row['low']),
                        close=float(row['close']),
                    )
                )

        if fiat_histories:
            session.add_all(fiat_histories)
            await session.commit()
            print(f'{len(fiat_histories)} nouvelles entrées ajoutées à FiatHistory')
        else:
            print('Aucune nouvelle entrée à ajouter.')


if __name__ == '__main__':
    asyncio.run(fiat_realtime_async_task())
