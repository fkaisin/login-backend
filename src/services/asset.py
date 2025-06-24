from sqlalchemy.orm import load_only, selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.models import Asset, Token, User


class AssetService:
  def __init__(self, session: AsyncSession):
    self.session = session

  async def update_user_assets(self, current_user_uid):
    try:
      statement = (
        select(User)
        .where(User.uid == current_user_uid)
        .options(
          selectinload(User.transactions),  # type: ignore
          selectinload(User.assets),  # type: ignore
        )
      )
      result = await self.session.exec(statement)
      user = result.one()

      token_ids = set()
      for trx in user.transactions:
        token_ids.add(trx.actif_a_id)
        token_ids.add(trx.actif_v_id)
        token_ids.add(trx.actif_f_id)
      token_ids.discard(None)

      assets_dict = {asset.token_id: asset for asset in user.assets}

      for tok_id in token_ids:
        if tok_id not in assets_dict:
          new_asset = Asset(token_id=tok_id, user_id=current_user_uid)
          await new_asset.update_asset()
          self.session.add(new_asset)
        else:
          asset = assets_dict[tok_id]
          await asset.update_asset()
          self.session.add(asset)

      await self.session.commit()

      statement = (
        select(Asset)
        .where(Asset.user_id == current_user_uid)
        .options(
          selectinload(Asset.token).load_only(Token.symbol, Token.price, Token.image)  # type: ignore
        )
      )
      results = await self.session.exec(statement)
      assets = list(results.all())

      # Supprimer fiat et valeur < $0.01
      assets = user.assets
      for asset in assets[:]:  # Crée une copie de la liste pour l'itération pour ne pas sauter certains éléments
        if asset.value < 0.01 or asset.token_id.startswith('fiat_'):
          assets.remove(asset)

      return assets

    except Exception as err:
      print(err)
