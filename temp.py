import asyncio
import uuid
from datetime import datetime

from sqlmodel import Session, create_engine, select, text
from src.db.main import get_session
from src.db.models import Transaction, User
from src.schemes.token import Ticker
from src.services.history import HistoryService
from src.utils.asset import get_fiat_price
from src.utils.decoration import timeit
from src.utils.tvdatafeed import (
    find_longest_history,
    get_history_ohlc_mutliple_symbols,
    get_history_ohlc_single_symbol,
    get_prices_for_dates,
    get_tv_search,
)

data = [
    {'cg_id': 'bitcoin', 'ticker': 'BTCUSD', 'exchange': 'INDEX'},
    {'cg_id': 'ethereum', 'ticker': 'ETHUSD', 'exchange': 'INDEX'},
    {'cg_id': 'binancecoin', 'ticker': 'BNBUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'solana', 'ticker': 'SOLUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'cardano', 'ticker': 'ADAUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'chainlink', 'ticker': 'LINKUSD', 'exchange': 'OSMOSIS'},
    {'cg_id': 'pepe', 'ticker': 'PEPEUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'bitget-token', 'ticker': 'BGBUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'aave', 'ticker': 'AAVEUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'bittensor', 'ticker': 'TAOUSDT', 'exchange': 'MEXC'},
    {'cg_id': 'algorand', 'ticker': 'ALGOUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'render-token', 'ticker': 'RENDERUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'fetch-ai', 'ticker': 'FETUSD', 'exchange': 'OSMOSIS'},
    {'cg_id': 'injective-protocol', 'ticker': 'INJUSD', 'exchange': 'OSMOSIS'},
    {'cg_id': 'immutable-x', 'ticker': 'IMXUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'the-graph', 'ticker': 'GRTUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'theta-token', 'ticker': 'THETAUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'reserve-rights-token', 'ticker': 'RSRUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'syrup', 'ticker': 'SYRUPUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'akash-network', 'ticker': 'AKTUSD', 'exchange': 'OSMOSIS'},
    {'cg_id': 'livepeer', 'ticker': 'LPTUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'mina-protocol', 'ticker': 'MINAUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'havven', 'ticker': 'SNXUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'ai16z', 'ticker': 'AI16ZUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'ordinals', 'ticker': 'ORDIUSDT', 'exchange': 'Binance'},
    {'cg_id': 'frax-share', 'ticker': 'FXSUSDT', 'exchange': 'Binance'},
    {'cg_id': 'nervos-network', 'ticker': 'CKBUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'ankr', 'ticker': 'ANKRUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'origintrail', 'ticker': 'TRACUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'gmx', 'ticker': 'GMXUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'zelcash', 'ticker': 'FLUXUSDT', 'exchange': 'KuCoin'},
    {'cg_id': '0x0-ai-ai-smart-contract', 'ticker': '0X0USD', 'exchange': 'CRYPTO'},
    {'cg_id': 'chutes', 'ticker': 'SN64USD', 'exchange': 'taostats.io'},
    {'cg_id': 'ocean-protocol', 'ticker': 'OCEANUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'nosana', 'ticker': 'NOSUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'hamster-kombat', 'ticker': 'HMSTRUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'autonolas', 'ticker': 'OLASWETH_09D1D7.USD', 'exchange': 'Uniswap v2 Ethereum'},
    {'cg_id': 'airtor-protocol', 'ticker': 'ATORUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'truefi', 'ticker': 'TRUUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'gradients', 'ticker': 'SN56USD', 'exchange': 'taostats.io'},
    {'cg_id': 'ai-rig-complex', 'ticker': 'ARCUSDT', 'exchange': 'Bitget'},
    {'cg_id': 'realio-network', 'ticker': 'RIOUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'lukso-token-2', 'ticker': 'LYXUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'nineteen-ai', 'ticker': 'SN19USD', 'exchange': 'taostats.io'},
    {'cg_id': 'clore-ai', 'ticker': 'CLOREUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'swarm-markets', 'ticker': 'SMTUSDT', 'exchange': 'MEXC'},
    {'cg_id': 'atlas-navi', 'ticker': 'NAVIUSDT', 'exchange': 'KuCoin'},
    {'cg_id': 'router-protocol-2', 'ticker': 'ROUTEUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'revest-finance', 'ticker': 'RVSTWETH_649082.USD', 'exchange': 'Uniswap v2 Ethereum'},
    {'cg_id': 'htx-dao', 'ticker': 'HTXUSD', 'exchange': 'CRYPTO'},
    {'cg_id': 'route', 'ticker': 'ROUTEUSDT', 'exchange': 'KuCoin'},
]
exchange_list = [Ticker.model_validate(t) for t in data]


sqlite_url = 'sqlite:///./src/db/database.sqlite'

engine = create_engine(sqlite_url, echo=True)
with engine.begin() as conn:
    conn.execute(text('PRAGMA foreign_keys=ON'))  # for SQLite only


@timeit
def main_tradingview():
    symbol = 'arcusdt'
    exchange = 'bitget'
    # res = get_tv_search(symbol)
    # for r in res:
    #     print(r)

    res = get_history_ohlc_single_symbol(symbol, exchange)
    print(res)
    # find_longest_history(symbol)


async def get_cash_in():
    from src.utils.calculations import get_cash_in_usd

    user_uid = uuid.UUID('197ea9b4fed7402dbffc6e569280e972')  # test
    user_uid = uuid.UUID('979863c4ba2b47998417dfca58aa477f')  # fkaisin
    async for session in get_session():
        # statement = select(Transaction).where(Transaction.user_id == user_uid)
        # results = await session.exec(statement)
        # transactions = results.all()
        # user = await session.get(User, user_uid)

        # transactions_data = [t.model_dump() for t in transactions]

        # await get_cash_in_usd(transactions_data, None)

        await HistoryService(session).calculate_histo_pf(user_uid, exchange_list)


if __name__ == '__main__':
    # main_tradingview()
    asyncio.run(get_cash_in())
