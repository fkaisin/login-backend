import datetime
from collections import defaultdict

import pandas as pd
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.models import Token, Transaction
from src.utils.asset import get_asset_qty
from src.utils.decoration import async_timeit


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

        # Compléter les jours manquants par copie de la veille
        start_date = pivot.index.min()
        end_date = datetime.date.today()
        all_days = pd.date_range(start=start_date, end=end_date, freq='D')

        pivot = pivot.reindex(all_days).ffill().fillna(0)
        pivot.index.name = 'date'

        return {
            'raw_df': df,
            'pivot_df': pivot,
        }

    @async_timeit
    async def build_portfolio_df(self, current_user_id):
        # Récupération des transactions de l'utilisateur
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

        # Dictionnaire pour suivre les quantités cumulées
        asset_quantities = defaultdict(float)
        rows = []

        for trx in transactions:
            date = pd.to_datetime(trx.date).normalize()

            # Liste des tokens affectés
            tokens = set()
            if trx.actif_a_id:
                tokens.add(trx.actif_a_id)
            if trx.actif_v_id:
                tokens.add(trx.actif_v_id)
            if trx.actif_f_id:
                tokens.add(trx.actif_f_id)

            # Application de la logique métier (comme dans get_asset_qty, mais de manière incrémentale)
            if trx.type in ['Swap', 'Achat', 'Vente']:
                if trx.actif_a_id:
                    asset_quantities[trx.actif_a_id] += trx.qty_a
                if trx.actif_v_id:
                    asset_quantities[trx.actif_v_id] -= trx.qty_a * trx.price
            elif trx.type in ['Depot', 'Interets', 'Airdrop', 'Emprunt']:
                if trx.actif_a_id:
                    asset_quantities[trx.actif_a_id] += trx.qty_a
            elif trx.type in ['Retrait', 'Perte', 'Remboursement']:
                if trx.actif_a_id:
                    asset_quantities[trx.actif_a_id] -= trx.qty_a

            if trx.actif_f_id:
                asset_quantities[trx.actif_f_id] -= trx.qty_f

            # Enregistre l'état courant pour les tokens affectés
            for token_id in tokens:
                rows.append({'date': date, 'token_id': token_id, 'qty': asset_quantities[token_id]})

        # Création du DataFrame
        df = pd.DataFrame(rows)
        df_pivot = df.pivot_table(index='date', columns='token_id', values='qty', aggfunc='last')

        full_date_range = pd.date_range(start=df_pivot.index.min(), end=pd.Timestamp.today().normalize(), freq='D')
        df_pivot = df_pivot.reindex(full_date_range)

        # Propagation des quantités sur les jours sans transaction
        df_pivot.ffill(inplace=True)
        df_pivot.fillna(0, inplace=True)

        return df_pivot
