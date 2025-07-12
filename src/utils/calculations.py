from datetime import datetime, timedelta

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

    # while price is None and count < 20:
    #     count += 1
    #     previous_day = date - timedelta(days=1)
    #     date = previous_day
    #     date = datetime.combine(date, datetime.min.time())

    #     statement = select(FiatHistory.close).where(FiatHistory.cg_id == fiat, FiatHistory.date == previous_day)
    #     result = await session.exec(statement)
    #     price = result.first()

    previous_day = date - timedelta(days=1)
    statement = (
        select(FiatHistory.close)
        .where(FiatHistory.cg_id == fiat, FiatHistory.date < previous_day)
        .order_by(desc(FiatHistory.date))
        .limit(1)
    )
    result = await session.exec(statement)
    price = result.first()

    return price if price is not None else 0


async def get_cash_in_usd(transactions: list[dict], df_pf_history):
    cash_in = 0
    cash_in_array = []

    for tr in transactions:
        trx = TransactionCreate.model_validate(tr)
        if trx.type == 'Achat' and trx.actif_v_id in settings.FIATS:
            cash_in += await calculate_transaction_value_in_usd(trx)
            cash_in_array.append({'date': trx.date, 'cash_in_fiat_usd': cash_in})

        if trx.type == 'Vente':
            pf_value = get_pf_value_at_date(trx.date, df_pf_history)
            trx_value = await calculate_transaction_value_in_usd(trx)
            cash_in = cash_in * (1 - (trx_value / pf_value))
            cash_in_array.append({'date': trx.date, 'cash_in_fiat_usd': cash_in})

    return cash_in_array


async def calculate_transaction_value_in_usd(t: TransactionCreate):
    val = 0

    if t.type in ['Depot', 'Retrait'] and t.actif_a_id in settings.FIATS:
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
        val = t.qty_a * t.value_a

    # On ajoute les frais si ils ne sont pas compris dans la meme actif que l'actif acheté car c'est en plus
    if (t.actif_f_id in settings.STABLECOINS or t.actif_f_id == 'fiat_usd') and t.actif_f_id != t.actif_a_id:
        val += t.qty_f

    elif t.actif_f_id != t.actif_a_id:
        try:
            if not t.value_f:
                value_f = None
                if t.actif_f_id == t.actif_v_id:
                    value_f = t.value_a / t.price
            else:
                value_f = t.value_f
            val += t.qty_f * value_f

        except TypeError:  # si qty_f = 0 ou val_f = 0 alors on ne fait rien
            pass

    return val


async def calculate_transaction_value_in_fiat(t: TransactionCreate, fiat: str):
    val = 0

    if t.type in ['Depot', 'Retrait'] and t.actif_a_id in settings.FIATS:
        if t.actif_a_id == fiat:
            fiat_price = 1
        else:
            date_normalized = t.date.replace(hour=0, minute=0, second=0, microsecond=0)
            async for session in get_session():
                transaction_fiat_price = await get_fiat_price(t.actif_a_id, date_normalized, session)
                function_fiat_price = await get_fiat_price(fiat, date_normalized, session)
                fiat_price = transaction_fiat_price / function_fiat_price

        val = t.qty_a * fiat_price

    #  Continuer ici

    elif t.actif_a_id in settings.STABLECOINS or t.actif_a_id == 'fiat_usd':
        val = t.qty_a

    elif t.actif_v_id in settings.STABLECOINS or t.actif_v_id == 'fiat_usd':
        if t.qty_a is not None and t.price is not None:
            val = t.qty_a * t.price  # val = qty_v

    else:
        val = t.qty_a * t.value_a

    # On ajoute les frais si ils ne sont pas compris dans la meme actif que l'actif acheté car c'est en plus
    if (t.actif_f_id in settings.STABLECOINS or t.actif_f_id == 'fiat_usd') and t.actif_f_id != t.actif_a_id:
        val += t.qty_f

    elif t.actif_f_id != t.actif_a_id:
        try:
            if not t.value_f:
                value_f = None
                if t.actif_f_id == t.actif_v_id:
                    value_f = t.value_a / t.price
            else:
                value_f = t.value_f
            val += t.qty_f * value_f

        except TypeError:  # si qty_f = 0 ou val_f = 0 alors on ne fait rien
            pass

    return val


def get_pf_value_at_date(date: datetime, df_history: pd.DataFrame, fiat: str = 'fiat_usd'):
    date = date.replace(hour=0, minute=0, second=0, microsecond=0)
    return df_history.at[date, f'total_{fiat}']
