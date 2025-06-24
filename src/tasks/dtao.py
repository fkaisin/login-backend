import asyncio
from datetime import datetime, timedelta

import bittensor as bt
from sqlmodel import func, select
from src.db.main import get_session
from src.db.models import Token


async def get_hist_tao_price_from_db(time='now'):
  async for session in get_session():
    results = await session.exec(select(Token).where(Token.cg_id == 'bittensor'))
    tao = results.one()

    if time == '1h' or time == '24h':
      return tao.price / (tao.change_1h + 1) if time == '1h' else tao.price / (tao.change_24h + 1)

    else:
      return tao.price


def clean_price(value):
  if value is None:
    return None
  if isinstance(value, float):
    return value
  try:
    # Enlève tout sauf chiffres, points, tirets
    return float(''.join(c for c in str(value) if c.isdigit() or c == '.'))
  except ValueError:
    return None


async def fetch_subnet_at_block(subtensor, netuid, block):
  try:
    return await subtensor.subnet(netuid=netuid, block=block)
  except Exception as e:
    print(f'Erreur pour netuid={netuid} : {e}')
    return None


async def fetch_hist_dtao(time):
  if time == '1h':
    blocks_back = 60 * 5
  elif time == '24h':
    blocks_back = 24 * 60 * 5
  else:
    return None

  sub = bt.AsyncSubtensor()
  sub_archive = bt.AsyncSubtensor(network='archive')
  tao_price = await get_hist_tao_price_from_db(time)

  async with sub, sub_archive:
    current_block = await sub.block

    try:
      all_subnet_infos = await sub_archive.all_subnets()
      all_netuids = [s.netuid for s in all_subnet_infos]
    except Exception as e:
      print(f'Erreur en récupérant la liste des subnets : {e}')
      return

    tasks = [
      fetch_subnet_at_block(subtensor=sub_archive, netuid=netuid, block=max(1, current_block - blocks_back))
      for netuid in all_netuids
    ]
    subnets_past = await asyncio.gather(*tasks)

    # cleaned_subnets = [
    #   {
    #     'netuid': int(subnet.netuid),
    #     'price': clean_price(subnet.price) * tao_price,
    #   }
    #   for subnet in subnets_past
    #   if subnet is not None
    # ]
    cleaned_subnets = []
    for subnet in subnets_past:
      if subnet is None:
        continue
      try:
        cleaned_subnets.append(
          {
            'netuid': int(subnet.netuid),
            'price': clean_price(subnet.price) * tao_price,
          }
        )
      except Exception as e:
        print(f'Erreur lors du nettoyage du subnet {subnet}: {e}')
        continue

    return cleaned_subnets


async def fetch_now_dtao():
  sub = bt.AsyncSubtensor()
  tao_price = await get_hist_tao_price_from_db()

  try:
    all_subnet_infos = await sub.all_subnets()
    # cleaned_subnets = [
    #   {
    #     'netuid': int(subnet.netuid),
    #     'name': subnet.subnet_name,
    #     'price': clean_price(subnet.price) * tao_price,
    #     'mcap': int(
    #       (clean_price(subnet.alpha_in) + clean_price(subnet.alpha_out)) * clean_price(subnet.price) * tao_price
    #     ),
    #     'price_in_tao': clean_price(subnet.price),
    #     'symbol': subnet.subnet_name.upper(),
    #     'cg_id': f'dtao-{subnet.netuid}-{subnet.subnet_name}'.lower(),
    #     'image': f'https://taostats.io/images/subnets/{subnet.netuid}.webp?w=32&q=75',
    #   }
    #   for subnet in all_subnet_infos[1:]
    #   if subnet is not None
    # ]
    cleaned_subnets = []
    for subnet in all_subnet_infos[1:]:
      if subnet is None:
        continue
      try:
        cleaned_subnets.append(
          {
            'netuid': int(subnet.netuid),
            'name': subnet.subnet_name,
            'price': clean_price(subnet.price) * tao_price,
            'mcap': int(
              (clean_price(subnet.alpha_in) + clean_price(subnet.alpha_out)) * clean_price(subnet.price) * tao_price
            ),
            'price_in_tao': clean_price(subnet.price),
            'symbol': subnet.subnet_name.upper(),
            'cg_id': f'dtao-{subnet.netuid}-{subnet.subnet_name}'.lower(),
            'image': f'https://taostats.io/images/subnets/{subnet.netuid}.webp?w=32&q=75',
          }
        )
      except Exception as e:
        print(f'Erreur lors du traitement du subnet {subnet.netuid}: {e}')
        continue

    _1h_subnets = await fetch_hist_dtao('1h')
    _24h_subnets = await fetch_hist_dtao('24h')

    for subnet in cleaned_subnets:
      async for session in get_session():
        statement = select(Token.rank).order_by(func.abs(Token.mcap - subnet['mcap'])).limit(1)
        result = await session.exec(statement)
        subnet['rank'] = result.first()

      matching_subnet_1h = next((s for s in _1h_subnets if s['netuid'] == subnet['netuid']), None)
      if matching_subnet_1h:
        subnet['change_1h'] = subnet['price'] / matching_subnet_1h['price'] - 1
      else:
        subnet['change_1h'] = 0

      matching_subnet_24h = next((s for s in _24h_subnets if s['netuid'] == subnet['netuid']), None)
      if matching_subnet_24h:
        subnet['change_24h'] = subnet['price'] / matching_subnet_24h['price'] - 1
      else:
        subnet['change_24h'] = 0

  except LookupError as e:
    print(f'Token introuvable : {e}')
    return []
  except ValueError as e:
    print(f'Erreur de conversion : {e}')
    return []
  except Exception as e:
    print(f'Erreur lors de la récupération des dtao : {e}')
    return []

  return cleaned_subnets


async def main():
  subnets = await fetch_now_dtao()
  async for session in get_session():
    for sub in subnets:
      db_sub = Token.model_validate(sub)
      existing_sub = await session.get(Token, db_sub.cg_id)
      if existing_sub:
        existing_sub.symbol = db_sub.symbol
        existing_sub.name = db_sub.name
        existing_sub.mcap = db_sub.mcap
        existing_sub.image = db_sub.image
        existing_sub.price = db_sub.price
        existing_sub.rank = db_sub.rank
        existing_sub.change_1h = db_sub.change_1h
        existing_sub.change_24h = db_sub.change_24h
        # existing_sub.change_7d = db_sub.change_7d
        # existing_sub.change_30d = db_sub.change_30d
        # existing_sub.change_1y = db_sub.change_1y
        session.add(existing_sub)
      else:
        session.add(db_sub)
      await session.commit()


async def get_next_execution_time(now):
  """
  Toutes les 5 minutes.
  """

  minutes_to_add = 5 - (now.minute % 5)
  next_execution_time = now.replace(second=0, microsecond=0) + timedelta(minutes=minutes_to_add)
  return next_execution_time


async def task_runner_dtao():
  """
  Exécute la tâche toutes les 5 minutes à 0 seconde, en synchronisant avec le début de la minute.
  """
  while True:
    now = datetime.now()
    next_execution_time = await get_next_execution_time(now)
    time_to_wait = (next_execution_time - now).total_seconds() + 30
    print(f'dtao next run : {next_execution_time} ({time_to_wait} secondes restantes).')

    await asyncio.sleep(time_to_wait)
    print('=' * 40, f'DTAO START {datetime.now()}', '=' * 41)
    await main()
    print('=' * 40, f'DTAO END {datetime.now()}', '=' * 43)
