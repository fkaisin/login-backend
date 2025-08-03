import time
from collections import defaultdict
from datetime import timedelta

import aiohttp
import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.exc import NoResultFound
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.celery.tasks import compute_pf_history_task, wait_for_celery_result
from src.config import settings
from src.db.models import DtaoCgList, FiatHistory, Token, Transaction, User, UserPfHistory
from src.schemes.token import Ticker
from src.utils.calculations import get_cash_in_fiat, get_cash_in_usd
from src.utils.tvdatafeed import find_longest_history, get_history_ohlc_single_symbol, get_tv_search


class HistoryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def build_portfolio_df(self, current_user_id):
        # Récupération des transactions de l'utilisateur
        statement = select(Transaction).where(Transaction.user_id == current_user_id)
        transactions = list((await self.session.exec(statement)).all())
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
                    asset_quantities[trx.actif_v_id] -= trx.qty_a * (trx.price or 0)
            elif trx.type in ['Depot', 'Interets', 'Airdrop', 'Emprunt']:
                if trx.actif_a_id:
                    asset_quantities[trx.actif_a_id] += trx.qty_a
            elif trx.type in ['Retrait', 'Perte', 'Remboursement']:
                if trx.actif_a_id:
                    asset_quantities[trx.actif_a_id] -= trx.qty_a

            if trx.actif_f_id:
                asset_quantities[trx.actif_f_id] -= trx.qty_f or 0

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

        return (df_pivot, transactions)

    async def calculate_histo_pf(self, current_user_uid, tv_list):
        df_qty, transactions = await self.build_portfolio_df(current_user_uid)

        # Conversion pour Celery
        df_qty_json = df_qty.to_json(orient='split')
        tv_list_data = [t.dict() for t in tv_list]
        transactions_data = [t.model_dump() for t in transactions]

        # get_cash_in_usd(transactions_data)

        # Tache sans celery (work pc)
        # -------------------------------------------------------------------------------------
        # async_result = compute_pf_history_task(df_qty_json, tv_list_data, transactions_data)
        # result = async_result['result']
        # ignored_tokens = async_result['ignored_tokens']
        # -------------------------------------------------------------------------------------

        # Tache celery (home pc)
        # -------------------------------------------------------------------------------------
        async_result = compute_pf_history_task.delay(df_qty_json, tv_list_data, transactions_data)

        # ⏳ Attente non bloquante du résultat
        try:
            task_result = await wait_for_celery_result(async_result.id, timeout=300, poll_interval=2)
        except TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail='Délai dépassé pour le calcul du portefeuille.'
            )

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f'Erreur dans la tâche Celery : {str(e)}'
            )

        result = task_result['result']
        ignored_tokens = task_result['ignored_tokens']
        # -------------------------------------------------------------------------------------

        # Ajout colonne des totaux en fiat_usd

        for fiat_id in [f for f in settings.FIATS if f != 'fiat_usd']:
            min_date = result[0]['index'] - timedelta(days=20)
            max_date = result[-1]['index']
            statement = select(FiatHistory.date, FiatHistory.close).where(
                FiatHistory.cg_id == fiat_id, FiatHistory.date >= min_date, FiatHistory.date <= max_date
            )
            results = await self.session.exec(statement)
            fiat_history_dict = {date: rate for date, rate in results.all()}  # ✅ proper dict

            sorted_dates = sorted(fiat_history_dict.keys())

            for row in result:
                date = row['index']

                # Cherche la dernière date <= date
                nearest_rate = None
                for d in reversed(sorted_dates):  # on parcourt depuis la fin
                    if d <= date:
                        nearest_rate = fiat_history_dict[d]
                        break

                if row['total_fiat_usd'] != 0 and nearest_rate is not None:
                    row[f'total_{fiat_id}'] = row['total_fiat_usd'] / nearest_rate
                else:
                    row[f'total_{fiat_id}'] = 0.0

        # Fin ajout de la colonne en fiat_usd

        df_result = pd.DataFrame(result)
        df_result['index'] = pd.to_datetime(df_result['index']).dt.normalize()
        df_result = df_result.set_index('index')

        # Ajout des colonnes cash in
        # -------------------------------------------------------------------------------------------------------------------------

        async def process_cash_in(transactions_data, df_result, fiat='fiat_usd'):
            if fiat == 'fiat_usd':
                # USD
                cash_in = await get_cash_in_usd(transactions_data, df_result)
                col_name = 'cash_in_fiat_usd'
            else:
                # autres FIATS
                cash_in = await get_cash_in_fiat(transactions_data, df_result, fiat)
                col_name = f'cash_in_{fiat}'

            df_cash_in = pd.DataFrame(cash_in)
            df_cash_in['date'] = df_cash_in['date'].dt.normalize()
            df_cash_in = df_cash_in.set_index('date')
            df_cash_in = df_cash_in[~df_cash_in.index.duplicated(keep='last')]

            cash_in_series = df_cash_in.reindex(df_result.index, method='ffill')
            cash_in_series[col_name] = cash_in_series[col_name].fillna(0)

            df_result[col_name] = cash_in_series[col_name]

        for fiat in settings.FIATS:
            await process_cash_in(transactions_data, df_result, fiat=fiat)

        # -------------------------------------------------------------------------------------------------------------------------
        # Fin ajout des colonnes cash in

        # Ajout des colonnes performances en %
        # -------------------------------------------------------------------------------------------------------------------------

        for fiat in settings.FIATS:
            df_result[f'pnl_percent_{fiat}'] = (
                df_result[f'total_{fiat}'] / df_result[f'cash_in_{fiat}'].replace(0, pd.NA) - 1
            )
            df_result[f'pnl_percent_{fiat}'] = df_result[f'pnl_percent_{fiat}'].fillna(0)

        # -------------------------------------------------------------------------------------------------------------------------
        # Fin ajout des colonnes performances en %

        # Supprimer les anciens historiques pour cet utilisateur
        statement = select(UserPfHistory).where(UserPfHistory.user_id == current_user_uid)
        results = await self.session.exec(statement)
        old_records = results.all()

        for record in old_records:
            await self.session.delete(record)

        # On passe le paramètre d'initialisation du pf à false
        usr = await self.session.get(User, current_user_uid)
        usr.history_init = False
        self.session.add(usr)

        await self.session.commit()

        # Ajouter les nouvelles données
        for row in df_result.reset_index().to_dict(orient='records'):
            new_item = UserPfHistory(
                user_id=current_user_uid,
                date=row['index'],
                value_in_usd=row['total_fiat_usd'],
                value_in_eur=row['total_fiat_eur'],
                value_in_cad=row['total_fiat_cad'],
                value_in_chf=row['total_fiat_chf'],
                cash_in_usd=row['cash_in_fiat_usd'],
                cash_in_eur=row['cash_in_fiat_eur'],
                cash_in_cad=row['cash_in_fiat_cad'],
                cash_in_chf=row['cash_in_fiat_chf'],
                pnl_percent_fiat_usd=row['pnl_percent_fiat_usd'],
                pnl_percent_fiat_eur=row['pnl_percent_fiat_eur'],
                pnl_percent_fiat_cad=row['pnl_percent_fiat_cad'],
                pnl_percent_fiat_chf=row['pnl_percent_fiat_chf'],
            )
            self.session.add(new_item)

        # On passe le paramètre d'initialisation du pf à true
        usr = await self.session.get(User, current_user_uid)
        usr.history_init = True
        self.session.add(usr)

        await self.session.commit()

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

    async def get_pf_history(self, current_user_uid):
        statement = select(UserPfHistory).where(UserPfHistory.user_id == current_user_uid)
        results = await self.session.exec(statement)
        return results.all()


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
