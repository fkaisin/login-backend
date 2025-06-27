import uuid

from sqlalchemy.orm import selectinload
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
          await self.session.merge(new_asset)
        else:
          asset = assets_dict[tok_id]
          await asset.update_asset()
          await self.session.merge(asset)

      await self.session.commit()

      assets = await self.get_user_assets(current_user_uid, refresh=False)

      return assets

    except Exception as err:
      await self.session.rollback()
      print(err)

  async def get_user_assets(self, current_user_uid, refresh: bool = True):
    try:
      statement = (
        select(Asset)
        .where(Asset.user_id == current_user_uid)
        .options(
          selectinload(Asset.token).load_only(Token.symbol, Token.price, Token.image, Token.updated_at, Token.name)  # type: ignore
        )
      )
      results = await self.session.exec(statement)
      assets = list(results.all())

      # Supprimer fiat et valeur < $0.01
      for asset in assets[:]:  # Crée une copie de la liste pour l'itération pour ne pas sauter certains éléments
        if asset.qty * asset.token.price < 0.01 or asset.token.cg_id.startswith('fiat_'):
          assets.remove(asset)

      # Pour ne pas rentrer dans une boucle infinie
      if refresh and len(assets) == 0:
        await self.update_user_assets(current_user_uid)
        return await self.get_user_assets(current_user_uid, refresh=False)

      return assets

    except Exception as err:
      await self.session.rollback()
      print(err)

  async def update_specific_assets(self, user_id: uuid.UUID, token_ids: set[str]):
    if not token_ids:
      return  # Rien à faire

    try:
      # 1. Récupérer les assets existants de l'utilisateur pour les token_ids
      statement = select(Asset).where(Asset.user_id == user_id, Asset.token_id.in_(token_ids))
      result = await self.session.exec(statement)
      existing_assets = result.all()
      existing_ids = {asset.token_id for asset in existing_assets}

      # 2. Préparer les nouveaux assets à créer
      new_ids = token_ids - existing_ids
      new_assets = [Asset(token_id=tok_id, user_id=user_id) for tok_id in new_ids]

      # 3. Mettre à jour tous les assets (existants + nouveaux)
      all_assets = list(existing_assets) + new_assets
      for asset in all_assets:
        await asset.update_asset()
        self.session.add(asset)

      await self.session.commit()

    except Exception as e:
      await self.session.rollback()
      print(f'[Asset Update Error] {e}')
      raise  # Re-raise pour un handling externe éventuel
