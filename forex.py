"""
https://tradermade.com (florian.kaisin@akkodis.com, mdp habituel)
"""

import asyncio
from datetime import datetime, timedelta

import httpx
from src.db.main import get_session
from src.db.models import FiatHistory


async def request(date, currency):
    print('request fired.')
    async with httpx.AsyncClient() as client:
        response = await client.get(
            'https://marketdata.tradermade.com/api/v1/historical',
            params={'date': date, 'currency': currency, 'api_key': 'QO6rWST5dDJCPw3tIW7y'},
        )

        if response.status_code != 200:
            raise ValueError(f'API error: {response.status_code} - {response.text}')

        data = (
            response.json()
            if hasattr(response, 'json') and not asyncio.iscoroutinefunction(response.json)
            else await response.json()
        )

        quote = data['quotes'][0]
        base_currency = quote['base_currency'].lower()

        requested_date = datetime.strptime(date, '%Y-%m-%d').date()
        date_obj = datetime.strptime(data['date'], '%Y-%m-%d').date()

        if date_obj != requested_date:
            date_obj = requested_date

        id_str = f'fiat_{base_currency}_{date_obj.strftime("%d%m%Y")}'

        return FiatHistory(
            id=id_str,
            cg_id=f'fiat_{base_currency}',
            date=date_obj,
            open=quote['open'],
            high=quote['high'],
            low=quote['low'],
            close=quote['close'],
        )


async def forex_async_task():
    date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    currencies = ['EURUSD', 'CADUSD', 'CHFUSD']

    async for session in get_session():
        fiat_hist_objects = []
        for currency in currencies:
            base_currency = currency[:3].lower()
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
            id_str = f'fiat_{base_currency}_{date_obj.strftime("%d%m%Y")}'
            existing = await session.get(FiatHistory, id_str)
            if existing:
                fiat_hist_objects.append(existing)
            else:
                obj = await request(date, currency)
                fiat_hist_objects.append(obj)
        for r in fiat_hist_objects:
            await session.merge(r)
        await session.commit()


asyncio.run(forex_async_task())
