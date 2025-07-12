import aiohttp
from sqlalchemy.exc import IntegrityError
from sqlmodel import delete
from src.db.main import get_session
from src.db.models import DtaoCgList

COINGECKO_MARKET_URL = 'https://api.coingecko.com/api/v3/coins/markets'


async def fetch_cg_ids_on_coingecko_async_task():
    cg_entries = []

    async with aiohttp.ClientSession() as session:
        params = {'category': 'bittensor-subnets', 'vs_currency': 'usd'}
        async with session.get(COINGECKO_MARKET_URL, params=params) as resp:
            data = await resp.json()
            for coin in data:
                symbol = coin.get('symbol', '').upper()
                if symbol.startswith('SN'):
                    cg_entries.append(DtaoCgList(cg_id=coin['id'], symbol=symbol))

    async for session in get_session():
        try:
            await session.exec(delete(DtaoCgList))
            session.add_all(cg_entries)
            await session.commit()

        except IntegrityError as e:
            print(f'Erreur d’insertion : {e}')
            await session.rollback()
