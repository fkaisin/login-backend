import datetime
from collections import defaultdict

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.models import DtaoCgList, Token, Transaction
from src.schemes.token import Ticker
from src.utils.tvdatafeed import find_longest_history, get_tv_search


class HistoryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # async def get_pf_history(self, current_user_id):
    #     statement = (
    #         select(Transaction)
    #         .where(Transaction.user_id == current_user_id)
    #         .options(
    #             selectinload(Transaction.actif_a).load_only(Token.symbol),
    #             selectinload(Transaction.actif_v).load_only(Token.symbol),
    #             selectinload(Transaction.actif_f).load_only(Token.symbol),
    #         )
    #     )
    #     transactions = (await self.session.exec(statement)).all()
    #     transactions.sort(key=lambda t: t.date)

    #     unique_dates = sorted({t.date.date() for t in transactions})
    #     pf_records = []

    #     trx_index = 0
    #     current_trx = []
    #     for dt in unique_dates:
    #         while trx_index < len(transactions) and transactions[trx_index].date.date() <= dt:
    #             current_trx.append(transactions[trx_index])
    #             trx_index += 1

    #         portfolio = get_portfolio_content(current_trx)
    #         for token in portfolio:
    #             pf_records.append(
    #                 {
    #                     'date': dt,
    #                     'symbol': token['symbol'],
    #                     'token_id': token['token_id'],
    #                     'qty': token['qty'],
    #                 }
    #             )

    #     df = pd.DataFrame(pf_records)
    #     pivot = df.pivot(index='date', columns='token_id', values='qty').fillna(0)

    #     # Compléter les jours manquants par copie de la veille
    #     start_date = pivot.index.min()
    #     end_date = datetime.date.today()
    #     all_days = pd.date_range(start=start_date, end=end_date, freq='D')

    #     pivot = pivot.reindex(all_days).ffill().fillna(0)
    #     pivot.index.name = 'date'

    #     return {
    #         'raw_df': df,
    #         'pivot_df': pivot,
    #     }

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

    async def calculate_histo_pf(self, current_user_uid, tv_list):
        df_qty = await self.build_portfolio_df(current_user_uid)
        first_date = df_qty.index[0]
        last_date = df_qty.index[-1]

        print(first_date)
        print(last_date)
        return

    async def get_best_ticker_exchange(self, cg_id: str):
        r = {}
        dtao_list_from_db = await self.session.exec(select(DtaoCgList.cg_id))
        dtao_id_list = dtao_list_from_db.all()

        if cg_id in dtao_id_list:
            result = await self.session.get(DtaoCgList, cg_id)
            if result is not None:
                r = {
                    'symbol': f'{result.symbol}USD',
                    'exchange': 'taostats.io',
                    'description': f'dtao {result.cg_id}',
                    'type': 'dtao',
                }

        else:
            result = await self.session.exec(select(Token.symbol).where(Token.cg_id == cg_id))
            try:
                token_symbol = result.one() + 'USD'
            except NoResultFound:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Token id non présent dans la DB.')

            except Exception as e:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e)

            exchange_list = get_tv_search(token_symbol)

            for r in exchange_list:
                if r['type'] == 'index' and r['symbol'] == token_symbol:
                    return r

            for r in exchange_list:
                if r['exchange'] == 'CRYPTO':
                    return r

            r = find_longest_history(exchange_list)

            if r is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail='Non trouvé. Veuillez entrer manuellement.'
                )

        return r


def check_ticker_exchange(ticker: Ticker):
    exchange_list = get_tv_search(ticker.ticker)
    item_found = False
    for item in exchange_list:
        if item['symbol'].lower() == ticker.ticker.lower() and item['exchange'].lower() == ticker.exchange.lower():
            item_found = True
            return item
    if not item_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Entrez un ticker et exchange valides de tradingview.'
        )
