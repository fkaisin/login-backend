import datetime

import pandas as pd
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.models import Token, Transaction
from src.utils.asset import get_asset_qty
from src.utils.decoration import async_timeit


def get_portfolio_content(transactions):
    content = []
    token_symbols = {}

    token_ids = set()
    for trx in transactions:
        for attr in ['actif_a', 'actif_v', 'actif_f']:
            token = getattr(trx, attr)
            token_id = getattr(trx, f'{attr}_id')
            if token_id is not None:
                token_ids.add(token_id)
                if token and token_id not in token_symbols:
                    token_symbols[token_id] = token.symbol

    for token_id in token_ids:
        qty = get_asset_qty(token_id, transactions)
        if qty > 0:
            symbol = token_symbols.get(token_id, '')
            content.append({'token_id': token_id, 'symbol': symbol, 'qty': qty})

    return content


class HistoryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    @async_timeit
    async def get_pf_history(self, current_user_id):
        statement = (
            select(Transaction)
            .where(Transaction.user_id == current_user_id)
            .options(
                selectinload(Transaction.actif_a).load_only(Token.symbol),
                selectinload(Transaction.actif_v).load_only(Token.symbol),
                selectinload(Transaction.actif_f).load_only(Token.symbol),
            )
        )
        transactions = (await self.session.exec(statement)).all()
        transactions.sort(key=lambda t: t.date)

        unique_dates = sorted({t.date.date() for t in transactions})
        pf_records = []

        trx_index = 0
        current_trx = []
        for dt in unique_dates:
            while trx_index < len(transactions) and transactions[trx_index].date.date() <= dt:
                current_trx.append(transactions[trx_index])
                trx_index += 1

            portfolio = get_portfolio_content(current_trx)
            for token in portfolio:
                pf_records.append(
                    {
                        'date': dt,
                        'symbol': token['symbol'],
                        'token_id': token['token_id'],
                        'qty': token['qty'],
                    }
                )

        df = pd.DataFrame(pf_records)
        pivot = df.pivot(index='date', columns='token_id', values='qty').fillna(0)

        # ➕ Compléter les jours manquants par copie de la veille
        start_date = pivot.index.min()
        end_date = datetime.date.today()
        all_days = pd.date_range(start=start_date, end=end_date, freq='D')

        pivot = pivot.reindex(all_days).ffill().fillna(0)
        pivot.index.name = 'date'

        return {
            'raw_df': df,
            'pivot_df': pivot,
        }
