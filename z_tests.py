import asyncio
import uuid

from src.db.models import Asset

# from src.tasks.dtao import main as get_dtao


async def main():
  a = {'user_id': uuid.UUID('979863c4ba2b47998417dfca58aa477f'), 'token_id': 'bittensor'}
  asset = Asset(**a)
  await asset.update_asset()
  print('quantity: ', asset.qty)
  print('value: ', asset.value)
  print('mean buy: ', asset.mean_buy)
  print('pnl $: ', asset.pnl_usd)
  print('pnl %: ', asset.pnl_percent)


# async def main():
#   await get_dtao()


if __name__ == '__main__':
  asyncio.run(main())
