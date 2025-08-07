import uuid

from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.celery.tasks import get_total_pnl_task, wait_for_celery_result
from src.db.models import User
from src.utils.calculations import get_current_total_pnl


class ChartService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_total_pnl(self, user: User):
        response = []
        fiat = user.fiat_id
        user_id = user.uid

        # Tache sans celery (work pc)
        # -------------------------------------------------------------------------------------
        # async_result_usd = get_total_pnl_task(user_id=user_id)
        # result_usd = async_result_usd
        # -------------------------------------------------------------------------------------

        # Tache celery (home pc)
        # -------------------------------------------------------------------------------------
        async_result_usd = get_total_pnl_task.delay(user_id=user_id)
        try:
            task_result_usd = await wait_for_celery_result(async_result_usd.id, timeout=300)
        except TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail='Délai dépassé pour le calcul du portefeuille.'
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f'Erreur dans la tâche Celery : {str(e)}'
            )

        result_usd = task_result_usd
        # -------------------------------------------------------------------------------------

        result_usd['fiat'] = 'USD'
        response.append(result_usd)

        if fiat != 'fiat_usd':
            # Tache sans celery (work pc)
            # -------------------------------------------------------------------------------------
            # async_result_fiat = get_total_pnl_task(user_id=user_id, fiat=fiat)
            # result_fiat = async_result_fiat
            # -------------------------------------------------------------------------------------

            # Tache celery (home pc)
            # -------------------------------------------------------------------------------------
            async_result_fiat = get_total_pnl_task.delay(user_id=user_id, fiat=fiat)
            try:
                task_result_fiat = await wait_for_celery_result(async_result_fiat.id, timeout=300)
            except TimeoutError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail='Délai dépassé pour le calcul du portefeuille.'
                )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f'Erreur dans la tâche Celery : {str(e)}'
                )

            result_fiat = task_result_fiat
            # -------------------------------------------------------------------------------------

            fiat_symbol = fiat.removeprefix('fiat_').upper()
            result_fiat['fiat'] = fiat_symbol
            response.append(result_fiat)

        return response
