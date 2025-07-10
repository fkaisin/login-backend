import asyncio
import time
from collections import defaultdict

import aiohttp
import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.config import settings
from src.db.models import DtaoCgList, Token, Transaction, UserPfHistory
from src.schemes.token import Ticker
from src.utils.tvdatafeed import find_longest_history, get_history_ohlc_single_symbol, get_tv_search


class HistoryService:
    def __init__(self, session: AsyncSession):
        self.session = session

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

        # Création du DataFrame pivoté et complété
        df = pd.DataFrame(rows)
        df_pivot = (
            df.pivot_table(index='date', columns='token_id', values='qty', aggfunc='last')
            .reindex(pd.date_range(df['date'].min(), pd.Timestamp.today().normalize(), freq='D'))
            .ffill()
            .fillna(0)
        )

        return df_pivot

    async def calculate_histo_pf(self, current_user_uid, tv_list):
        df_qty = await self.build_portfolio_df(current_user_uid)
        # print(df_qty)
        first_date_qty = df_qty.index[0]
        last_date_qty = df_qty.index[-2]
        all_histories = []
        ignored_tokens = []

        for token in df_qty.columns:
            # print('Récupération des données pour :', token)
            dates = df_qty.index[df_qty[token] > 0]
            first_date = dates.min()
            last_date = dates.max()

            if token in settings.STABLECOINS:
                date_range = pd.date_range(start=first_date, end=last_date, freq='D')
                df_stable = pd.DataFrame({'datetime': date_range, 'close': 1.0, 'token': token})
                all_histories.append(df_stable)

            elif token in settings.FIATS:
                continue  # On n'intègre pas les fiat dans le calcul historique du pf crypto

            else:
                ticker_obj = next((t for t in tv_list if t.cg_id == token), None)
                ticker = ticker_obj.ticker if ticker_obj else None
                exchange = ticker_obj.exchange if ticker_obj else None

                if exchange == 'taostats.io':
                    token_full_history = await get_dtao_history(ticker, token)

                else:
                    token_full_history = get_history_ohlc_single_symbol(ticker, exchange)
                    if token_full_history is None:
                        print("Impossible de récupérer l'historiuque pour :", token)
                        ignored_tokens.append(token)
                        continue

                token_history = token_full_history.loc[first_date:last_date, ['close']].copy()
                token_history['token'] = token
                token_history = token_history.reset_index()
                all_histories.append(token_history)

                await asyncio.sleep(0.5)

        df_all_history = pd.concat(all_histories, ignore_index=True)

        # S'assurer que 'datetime' est bien en datetime et créer la colonne 'date'
        df_all_history['date'] = pd.to_datetime(df_all_history['datetime']).dt.date

        # Pivot, tri, reindex et nettoyage en une séquence
        full_date_index = pd.date_range(start=first_date_qty.date(), end=last_date_qty.date(), freq='D')
        df_price = (
            df_all_history.pivot(index='date', columns='token', values='close')
            .sort_index()
            .reindex(full_date_index)
            .fillna(0)
        )
        df_price.index.name = 'date'

        # print(df_price)

        # Multiplication des deux df
        common_tokens = df_price.columns.intersection(df_qty.columns)
        common_dates = df_price.index.intersection(df_qty.index)
        price_aligned = df_price.loc[common_dates, common_tokens]
        qty_aligned = df_qty.loc[common_dates, common_tokens]
        df_value = price_aligned * qty_aligned
        df_value['total'] = df_value.sum(axis=1)

        # print(df_value)

        df_totals = df_value[['total']].copy()
        df_totals.reset_index(inplace=True)
        result = df_totals.to_dict(orient='records')  # Dict date + total

        # Supprimer les anciens historiques pour cet utilisateur
        statement = select(UserPfHistory).where(UserPfHistory.user_id == current_user_uid)
        results = await self.session.exec(statement)
        old_records = results.all()

        for record in old_records:
            await self.session.delete(record)

        await self.session.commit()

        # Ajouter les nouvelles données
        for row in result:
            new_item = UserPfHistory(user_id=current_user_uid, date=row['index'], value_in_usd=row['total'])
            self.session.add(new_item)

        await self.session.commit()

        # print(result)

        # Tracer la courbe
        # import matplotlib.pyplot as plt
        # plt.figure(figsize=(12, 6))
        # plt.plot(df_totals.index, df_totals['total'], label='Valeur totale', color='royalblue')
        # plt.title('Évolution de la valeur totale du portefeuille')
        # plt.xlabel('Date')
        # plt.ylabel('Total (€ ou $)')
        # plt.grid(True)
        # plt.legend()
        # plt.tight_layout()
        # plt.savefig('plot_portefeuille.png')  # ou JPG, PDF, etc.

        if len(ignored_tokens) > 0:
            response = {
                'data': result,
                'warning': f"L'historique n'a pas pu être récupéré pour les tokens suivants : {ignored_tokens}. Veuillez indiquer un autre exchange tradingview ou ces tokens seront ignorés dans l'historique.\nVous pouvez quitter cet outil si vous souhaitez ignorer ces tokens.",
            }
        else:
            response = {'data': result}

        return response

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


async def get_dtao_history(ticker: str, token: str):
    BASE_URL = 'https://taostats.io/api/dtao/udf/history'

    digits = ''.join(filter(str.isdigit, ticker))
    if not digits:
        print(f'Ticker invalide : {ticker}')
        return None, None
    number = int(digits)
    symbol = f'SUB-{number}'

    to_ts = int(time.time())
    from_ts = to_ts - 10 * 365 * 24 * 3600  # 10 ans

    params = {'symbol': symbol, 'resolution': '1D', 'from': from_ts, 'to': to_ts}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(BASE_URL, params=params) as resp:
                resp.raise_for_status()
                data = await resp.json()
                # return symbol, data
        except Exception as e:
            print(f'Erreur API pour {symbol} : {e}')
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Erreur lors de la récupération de l'historique du dtao {symbol}",
            )

    if data and data.get('s') == 'ok' and data.get('t'):
        df = pd.DataFrame(
            {
                # 'symbol': token,
                # 'timestamp': data['t'],
                'datetime': pd.to_datetime(data['t'], unit='s').normalize(),
                'symbol': symbol.replace('SUB-', 'SN'),
                'open': data['o'],
                'high': data['h'],
                'low': data['l'],
                'close': data['c'],
                'volume': data['v'],
            }
        )

    df.set_index('datetime', inplace=True)

    df_tao = get_history_ohlc_single_symbol('TAOUSDT', 'MEXC')

    df.index = pd.to_datetime(df.index).normalize()
    df_tao.index = pd.to_datetime(df_tao.index).normalize()

    df_combined = df.join(df_tao[['close']], rsuffix='_tao', how='left')
    df_combined['close'] = df_combined['close'] * df_combined['close_tao']

    df = df_combined
    df = df[~df.index.duplicated(keep='first')]

    return df
