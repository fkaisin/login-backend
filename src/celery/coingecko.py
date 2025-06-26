import asyncio
from datetime import datetime, timedelta

import aiohttp
from sqlmodel import select
from src.db.main import get_session
from src.db.models import SmallToken, Token


async def get_small_tokens():
  small_tokens = []
  total_pages = []

  async for session in get_session():
    results = await session.exec(select(SmallToken))
    small_tokens = [token.id for token in results.all()]
    n_small_tokens = len(small_tokens)
    n_pages = n_small_tokens // 1000 + 1 if n_small_tokens != 0 else 0
    total_pages = n_pages + 2  # On prend doffice 2 pages pour le top 2000

  return [small_tokens, total_pages]


async def call_api(session, url, params, page, all_cryptos):
  async with session.get(url, params=params) as response:
    response.raise_for_status()
    data = await response.json()
    # print(f'Page {page} : {len(data)} cryptos récupérées.')
    if data:
      all_cryptos.extend(data)


async def write_to_db(raw_data):
  if raw_data:
    db_token_list = [
      Token.model_validate(
        {
          'cg_id': crypto.get('id', '') or '',
          'name': crypto.get('name', '') or '',
          'symbol': crypto.get('symbol', '').upper() or '',
          'mcap': crypto.get('market_cap', 0) or 0,
          'image': crypto.get('image', '') or '',
          'price': crypto.get('current_price', 0) or 0,
          'rank': crypto.get('market_cap_rank', 5000) or 5000,
          'change_1h': float((crypto.get('price_change_percentage_1h_in_currency') or 0) / 100),
          'change_24h': float((crypto.get('price_change_percentage_24h_in_currency') or 0) / 100),
          'change_7d': float((crypto.get('price_change_percentage_7d_in_currency') or 0) / 100),
          'change_30d': float((crypto.get('price_change_percentage_30d_in_currency') or 0) / 100),
          'change_1y': float((crypto.get('price_change_percentage_1y_in_currency') or 0) / 100),
        }
      )
      for crypto in raw_data
    ]

    async for session in get_session():
      for db_tok in db_token_list:
        existing_tok = await session.get(Token, db_tok.cg_id)
        if existing_tok:
          existing_tok.symbol = db_tok.symbol
          existing_tok.name = db_tok.name
          existing_tok.mcap = db_tok.mcap
          existing_tok.image = db_tok.image
          existing_tok.price = db_tok.price
          existing_tok.rank = db_tok.rank
          existing_tok.change_1h = db_tok.change_1h
          existing_tok.change_24h = db_tok.change_24h
          existing_tok.change_7d = db_tok.change_7d
          existing_tok.change_30d = db_tok.change_30d
          existing_tok.change_1y = db_tok.change_1y
          session.add(existing_tok)
        else:
          session.add(db_tok)
      await session.commit()

      # Delete old entries
      statement = select(Token).where(Token.updated_at < datetime.now() - timedelta(days=2))
      old_tokens = await session.exec(statement)
      for tok in old_tokens:
        await session.delete(tok)
      await session.commit()
      print('Cryptos écrites dans la DB.')


async def coingecko_async_task():
  """
  Fonction représentant la tâche à exécuter toutes les 2 minutes.
  Ici, on simule une tâche qui prend entre 5 et 15 secondes.
  """
  start_time = datetime.now()
  print(f'Tâche démarrée à {start_time}')

  [small_tokens, pages] = await get_small_tokens()
  page_range = pages - (start_time.minute // 2) % pages

  url = 'https://api.coingecko.com/api/v3/coins/markets'
  all_cryptos = []
  tasks = []

  async with aiohttp.ClientSession() as session:
    common_params = {
      'vs_currency': 'usd',
      'order': 'market_cap_desc',
      'per_page': 250,
      'price_change_percentage': '1h,24h,7d,30d,1y',
    }

    if page_range < 3:
      for page in range(page_range * 4, page_range * 4 - 4, -1):
        params = common_params.copy()
        params['page'] = page  # Ajout de la page spécifique
        tasks.append(call_api(session, url, params, page, all_cryptos))

    elif small_tokens:
      # print(f'Récupération des id suivants {small_tokens}')
      total_pages = len(small_tokens) // 250 + 1
      liste_format = ','.join(small_tokens)

      params = common_params.copy()
      params['ids'] = liste_format

      for page in range(1, total_pages + 1):
        params['page'] = page
        tasks.append(call_api(session, url, params, page, all_cryptos))

    await asyncio.gather(*tasks)

  await write_to_db(all_cryptos)

  end_time = datetime.now()
  print(f'Tâche terminée à {end_time}')


async def get_next_execution_time(now):
  """
  Calcule la prochaine minute paire (00, 02, 04, etc.) pour l'exécution de la tâche.
  """

  minutes_to_add = ((now.minute + 1) % 2) + 1

  next_execution_time = now.replace(second=0, microsecond=0) + timedelta(minutes=minutes_to_add)

  return next_execution_time


async def task_runner_coingecko():
  """
  Exécute la tâche toutes les 2 minutes à 0 seconde, en synchronisant avec le début de la minute.
  """
  while True:
    now = datetime.now()
    next_execution_time = await get_next_execution_time(now)
    time_to_wait = (next_execution_time - now).total_seconds() + 15
    print(f'coingecko next run : {next_execution_time} ({time_to_wait} secondes restantes).')

    await asyncio.sleep(time_to_wait)
    print('=' * 40, f'COINGECKO START {datetime.now()}', '=' * 36)
    await coingecko_async_task()
    print('=' * 40, f'COINGECKO END {datetime.now()}', '=' * 38)
