import asyncio
import uuid

from src.utils.calculations import get_current_total_pnl


def get_total_pnl(user_id: uuid.UUID, fiat: str):
    # return get_current_total_pnl(user_id=user_id, fiat=fiat)
    return asyncio.run(get_current_total_pnl(user_id=user_id, fiat=fiat))
