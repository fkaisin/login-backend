from collections import defaultdict
from datetime import datetime

import pandas as pd
from sqlmodel import desc, select
from src.config import settings
from src.db.main import get_session
from src.schemes.transaction import TransactionCreate


async def get_fiat_price(fiat, date, session):
    from src.db.models import FiatHistory

    price = None
    # count = 0

    date = date.date()

    statement = (
        select(FiatHistory.close)
        .where(FiatHistory.cg_id == fiat, FiatHistory.date < date)
        .order_by(desc(FiatHistory.date))
        .limit(1)
    )
    result = await session.exec(statement)
    price = result.first()

    if price is None or price == 0:
        raise LookupError(f'Prix fiat non trouvé pour {fiat} à la date : {date}')

    return price


async def get_cash_in_usd(transactions: list[dict], df_pf_history):
    cash_in = 0
    cash_in_array = []
    temp_cash_in_array = []

    for tr in transactions:
        trx = TransactionCreate.model_validate(tr)

        if trx.type == 'Achat' and trx.actif_v_id in settings.FIATS:
            trx_value = await calculate_transaction_value_in_usd(trx)
            pf_value_end_of_day = get_pf_value_at_date(trx.date, df_pf_history)
            temp_cash_in_array.append(
                {'date': trx.date, 'type': 'achat', 'trx_value': trx_value, 'pf': pf_value_end_of_day}
            )

        if trx.type == 'Vente':
            trx_value = await calculate_transaction_value_in_usd(trx)
            pf_value_end_of_day = get_pf_value_at_date(trx.date, df_pf_history)
            temp_cash_in_array.append(
                {'date': trx.date, 'type': 'vente', 'trx_value': trx_value, 'pf': pf_value_end_of_day}
            )

    # Gestion des cash in si meme date
    grouped_by_date = defaultdict(list)
    for row in temp_cash_in_array:
        grouped_by_date[row['date'].date()].append(row)

    for _, rows in grouped_by_date.items():
        cumulative = 0
        for row in reversed(rows):
            if row['type'] == 'achat':
                cumulative += row['trx_value']
            elif row['type'] == 'vente':
                cumulative -= row['trx_value']

            row['pf_before_trx'] = max(row['pf'] - cumulative, 0)

    for row in temp_cash_in_array:
        if row['type'] == 'achat':
            cash_in += row['trx_value']
            cash_in_array.append({'date': row['date'], 'cash_in_fiat_usd': cash_in})

        elif row['type'] == 'vente':
            cash_in = cash_in * (1 - (row['trx_value'] / row['pf_before_trx']))
            cash_in_array.append({'date': row['date'], 'cash_in_fiat_usd': cash_in})

    return cash_in_array


async def get_cash_in_fiat(transactions: list[dict], df_pf_history, fiat):
    cash_in = 0
    cash_in_array = []
    temp_cash_in_array = []

    for tr in transactions:
        trx = TransactionCreate.model_validate(tr)

        if trx.type == 'Achat' and trx.actif_v_id in settings.FIATS:
            trx_value = await calculate_transaction_value_in_fiat(trx, fiat)
            pf_value_end_of_day = get_pf_value_at_date(trx.date, df_pf_history, fiat=fiat)
            temp_cash_in_array.append(
                {'date': trx.date, 'type': 'achat', 'trx_value': trx_value, 'pf': pf_value_end_of_day}
            )

        if trx.type == 'Vente':
            trx_value = await calculate_transaction_value_in_fiat(trx, fiat)
            pf_value_end_of_day = get_pf_value_at_date(trx.date, df_pf_history, fiat=fiat)
            temp_cash_in_array.append(
                {'date': trx.date, 'type': 'vente', 'trx_value': trx_value, 'pf': pf_value_end_of_day}
            )

    # Gestion des cash in si meme date
    grouped_by_date = defaultdict(list)
    for row in temp_cash_in_array:
        grouped_by_date[row['date'].date()].append(row)

    for _, rows in grouped_by_date.items():
        cumulative = 0
        for row in reversed(rows):
            if row['type'] == 'achat':
                cumulative += row['trx_value']
            elif row['type'] == 'vente':
                cumulative -= row['trx_value']

            row['pf_before_trx'] = max(row['pf'] - cumulative, 0)

    for row in temp_cash_in_array:
        if row['type'] == 'achat':
            cash_in += row['trx_value']
            cash_in_array.append({'date': row['date'], f'cash_in_{fiat}': cash_in})

        elif row['type'] == 'vente':
            cash_in = cash_in * (1 - (row['trx_value'] / row['pf_before_trx']))
            cash_in_array.append({'date': row['date'], f'cash_in_{fiat}': cash_in})

    return cash_in_array


async def calculate_transaction_value_in_usd(t: TransactionCreate):
    val = 0

    if t.type in ['Depot', 'Retrait'] and t.actif_a_id in settings.FIATS:
        fiat_price = 0
        if t.actif_a_id == 'fiat_usd':
            fiat_price = 1
        else:
            date_normalized = t.date.replace(hour=0, minute=0, second=0, microsecond=0)
            async for session in get_session():
                fiat_price = await get_fiat_price(t.actif_a_id, date_normalized, session)

        val = t.qty_a * fiat_price

    elif t.actif_a_id in settings.STABLECOINS or t.actif_a_id == 'fiat_usd':
        val = t.qty_a

    elif t.actif_v_id in settings.STABLECOINS or t.actif_v_id == 'fiat_usd':
        if t.qty_a is not None and t.price is not None:
            val = t.qty_a * t.price  # val = qty_v

    else:
        val = t.qty_a * (t.value_a or 0)

    # On ajoute les frais si ils ne sont pas compris dans la meme actif que l'actif acheté car c'est en plus
    if (t.actif_f_id in settings.STABLECOINS or t.actif_f_id == 'fiat_usd') and t.actif_f_id != t.actif_a_id:
        val += t.qty_f or 0

    elif t.actif_f_id != t.actif_a_id:
        try:
            if not t.value_f:
                value_f = None
                if t.actif_f_id == t.actif_v_id:
                    value_f = (t.value_a or 0) / (t.price or 1)
            else:
                value_f = t.value_f
            val += (t.qty_f or 0) * (value_f or 0)

        except TypeError:  # si qty_f = 0 ou val_f = 0 alors on ne fait rien
            pass

    return val


async def calculate_transaction_value_in_fiat(t: TransactionCreate, fiat: str):
    val = 0
    date_normalized = t.date.replace(hour=0, minute=0, second=0, microsecond=0)

    async for session in get_session():
        if t.type in ['Depot', 'Retrait'] and t.actif_a_id in settings.FIATS:
            if t.actif_a_id == fiat:
                fiat_price = 1

            elif t.actif_a_id == 'fiat_usd':
                fiat_price = await get_fiat_price(fiat, date_normalized, session)

            else:
                transaction_fiat_price = await get_fiat_price(t.actif_a_id, date_normalized, session)
                function_fiat_price = await get_fiat_price(fiat, date_normalized, session)
                fiat_price = transaction_fiat_price / function_fiat_price

        elif t.type in ['Swap', 'Achat', 'Vente']:
            if t.actif_a_id == fiat:
                fiat_price = 1

            elif t.actif_a_id in settings.FIATS and t.actif_a_id != 'fiat_usd':  # actif A est en fiat
                if t.actif_v_id in settings.STABLECOINS or t.actif_v_id == 'fiat_usd':
                    function_fiat_price = await get_fiat_price(fiat, date_normalized, session)
                    fiat_price = t.price / function_fiat_price

                elif t.actif_v_id == fiat:
                    fiat_price = t.price

                else:
                    transaction_fiat_price = await get_fiat_price(t.actif_a_id, date_normalized, session)
                    function_fiat_price = await get_fiat_price(fiat, date_normalized, session)
                    fiat_price = transaction_fiat_price / function_fiat_price

            elif t.actif_a_id in settings.STABLECOINS or t.actif_a_id == 'fiat_usd':  # actif A est en USD
                if t.actif_v_id == fiat:
                    fiat_price = t.price

                else:
                    function_fiat_price = await get_fiat_price(fiat, date_normalized, session)
                    fiat_price = 1 / function_fiat_price

            else:  # actif A est une crypto classique
                if t.actif_v_id == fiat:
                    fiat_price = t.price

                elif t.actif_v_id in settings.STABLECOINS or t.actif_v_id == 'fiat_usd':
                    function_fiat_price = await get_fiat_price(fiat, date_normalized, session)
                    fiat_price = t.price / function_fiat_price

                elif t.actif_v_id in settings.FIATS:
                    transaction_fiat_price = await get_fiat_price(t.actif_v_id, date_normalized, session)
                    function_fiat_price = await get_fiat_price(fiat, date_normalized, session)
                    fiat_price = t.price * transaction_fiat_price / function_fiat_price

                else:
                    function_fiat_price = await get_fiat_price(fiat, date_normalized, session)
                    fiat_price = t.value_a / function_fiat_price

        else:  # [Transfert, Mise en staking, Retrait de staking, Interets, Airdrop, Perte, Emprunt, Remboursement]
            if t.actif_a_id == fiat:
                fiat_price = 1

            elif t.actif_a_id in settings.STABLECOINS or t.actif_a_id == 'fiat_usd':
                function_fiat_price = await get_fiat_price(fiat, date_normalized, session)
                fiat_price = 1 / function_fiat_price

            elif t.actif_a_id in settings.FIATS:
                transaction_fiat_price = await get_fiat_price(t.actif_a_id, date_normalized, session)
                function_fiat_price = await get_fiat_price(fiat, date_normalized, session)
                fiat_price = transaction_fiat_price / function_fiat_price
            else:
                function_fiat_price = await get_fiat_price(fiat, date_normalized, session)
                fiat_price = t.value_a / function_fiat_price

        val = t.qty_a * (fiat_price or 0)

        # On ajoute les frais si ils ne sont pas compris dans la meme actif que l'actif acheté car c'est en plus
        if t.actif_f_id != t.actif_a_id and t.actif_f_id is not None:
            try:
                if t.actif_f_id == fiat:
                    val += t.qty_f or 0

                elif t.actif_f_id == t.actif_v_id:
                    function_fiat_price = await get_fiat_price(fiat, date_normalized, session)
                    val += (t.qty_f or 0) / (t.price or 1) * (t.value_a or 0) / function_fiat_price

                elif t.actif_f_id in settings.STABLECOINS or t.actif_f_id == 'fiat_usd':
                    function_fiat_price = await get_fiat_price(fiat, date_normalized, session)
                    val += t.qty_f / function_fiat_price

                elif t.actif_f_id in settings.FIATS:
                    transaction_fiat_price = await get_fiat_price(t.actif_f_id, date_normalized, session)
                    function_fiat_price = await get_fiat_price(fiat, date_normalized, session)
                    val += t.qty_f * transaction_fiat_price / function_fiat_price

                else:
                    function_fiat_price = await get_fiat_price(fiat, date_normalized, session)
                    val += (t.qty_f or 0) * (t.value_f or 0) / function_fiat_price

            except TypeError as err:
                print('TypeError:', err)
                pass

            # except ValueError as err:
            #     print('ValueError:', err)

    return val


def get_pf_value_at_date(date: datetime, df_history: pd.DataFrame, fiat: str = 'fiat_usd'):
    date = date.replace(hour=0, minute=0, second=0, microsecond=0)
    return df_history.at[date, f'total_{fiat}']
