from datetime import datetime, timedelta

from sqlmodel import select
from src.config import settings
from src.db.main import get_session

CALC_METHODS = [
    {'label': 'weighted average', 'value': 1},
    {'label': 'fifo', 'value': 2},
    {'label': 'lifo', 'value': 3},
]
calc_method = {'value': 3}


def get_asset_qty(token_id, transactions):
    qty = 0
    for trx in transactions:
        if trx.type in ['Swap', 'Achat', 'Vente']:
            if trx.actif_a_id == token_id:
                qty += trx.qty_a
            if trx.actif_v_id == token_id:
                qty -= trx.qty_a * trx.price
        elif trx.type in ['Depot', 'Interets', 'Airdrop', 'Emprunt']:
            if trx.actif_a_id == token_id:
                qty += trx.qty_a
        elif trx.type in ['Retrait', 'Perte', 'Remboursement']:
            if trx.actif_a_id == token_id:
                qty -= trx.qty_a
        if trx.actif_f_id == token_id:
            qty -= trx.qty_f

    return qty


async def get_asset_mean_buy(token_id, transactions, session):
    summary_table = []
    for t in transactions:
        qty_a = t.qty_a - t.qty_f if t.actif_f_id == t.actif_a_id else t.qty_a
        if t.actif_a_id == token_id and t.type in ['Swap', 'Achat', 'Vente', 'Emprunt', 'Depot', 'Airdrop']:
            price = t.value_a
            if t.actif_a_id in settings.FIATS:
                price = await get_fiat_price(t.actif_a_id, t.date, session)
            summary_table.append({'qty_a': qty_a, 'price': price})

        elif t.actif_a_id == token_id and t.type in ['Interets']:
            summary_table.append({'qty_a': qty_a, 'price': 0})

        elif calc_method['value'] == 1:  # Weighted average
            total = sum(row['qty_a'] for row in summary_table)
            if total == 0:
                print('Quantité = 0 pour le token: ', token_id)
                return 0

            if t.actif_a_id == token_id and t.type in ['Retrait', 'Remboursement', 'Perte']:
                for row in summary_table:
                    row['qty_a'] -= row['qty_a'] * t.qty_a / total

            elif t.actif_v_id == token_id and t.type in ['Swap', 'Achat', 'Vente']:
                for row in summary_table:
                    row['qty_a'] -= row['qty_a'] * t.qty_a * t.price / total

            if t.actif_f_id == token_id:
                for row in summary_table:
                    row['qty_a'] -= row['qty_a'] * t.qty_f / total

        elif calc_method['value'] in [2, 3]:  # fifo / lifo
            index_fifo_lifo = 0 if calc_method['value'] == 2 else -1
            qty_to_remove = 0

            if t.actif_a_id == token_id and t.type in ['Retrait', 'Remboursement', 'Perte']:
                qty_to_remove = t.qty_a

            elif t.actif_v_id == token_id and t.type in ['Swap', 'Achat', 'Vente']:
                qty_to_remove = t.qty_a * t.price

            if t.actif_f_id == token_id:
                qty_to_remove += t.qty_f

            while qty_to_remove > 0 and summary_table:
                if summary_table[index_fifo_lifo]['qty_a'] >= qty_to_remove:
                    summary_table[index_fifo_lifo]['qty_a'] -= qty_to_remove
                    qty_to_remove = 0
                else:
                    qty_to_remove -= summary_table[index_fifo_lifo]['qty_a']
                    summary_table.pop(index_fifo_lifo)

    total_buy_value = sum(row['price'] * row['qty_a'] for row in summary_table)
    total_buy_qty = sum(row['qty_a'] for row in summary_table)

    if total_buy_qty == 0:
        return 0
    average_price = total_buy_value / total_buy_qty

    return average_price


async def get_fiat_price(fiat, date, session):
    from src.db.models import FiatHistory

    price = None
    count = 0

    date = date.date()

    while price is None and count < 20:
        count += 1
        previous_day = date - timedelta(days=1)
        date = previous_day
        date = datetime.combine(date, datetime.min.time())

        statement = select(FiatHistory.close).where(FiatHistory.cg_id == fiat, FiatHistory.date == previous_day)
        result = await session.exec(statement)
        price = result.first()

    return price if price is not None else 0
