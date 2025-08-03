import asyncio
import logging

from celery import Celery
from celery.result import AsyncResult
from celery.schedules import crontab
from src.celery.charts import get_total_pnl
from src.celery.coingecko import coingecko_async_task
from src.celery.fiat import fiat_realtime_async_task, get_daily_fiat_history_async_task
from src.celery.histo import compute_pf_history

# Setup logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = Celery(
    'tasks',
    broker='redis://:i5mEvUw95F02id7@192.168.129.17:6379/0',
    backend='redis://:i5mEvUw95F02id7@192.168.129.17:6379/1',
)

app.conf.update(result_expires=1800)
app.conf.timezone = 'Europe/Paris'


@app.on_after_configure.connect
def setup_periodic_tasks(sender: Celery, **kwargs):
    sender.add_periodic_task(crontab(minute='*/2'), coingecko_task.s(), name='cg toutes les 2 min')
    sender.add_periodic_task(crontab(minute='*/5'), fiat_realtime_task.s(), name='fiat toutes les 5 min')
    sender.add_periodic_task(crontab(minute=0, hour=1), daily_fiat_history_task.s(), name='dailyfiat 1h du matin')


# ------------ periodic functions --------------


@app.task
def coingecko_task():
    logger.info('>>> Lancement de la tâche coingecko_task')
    asyncio.run(coingecko_async_task())


@app.task
def fiat_realtime_task():
    logger.info('>>> Lancement de la tâche fiat_realtime_task')
    asyncio.run(fiat_realtime_async_task())


@app.task
def daily_fiat_history_task():
    logger.info('>>> Lancement de la tâche daily_fiat_history_task')
    asyncio.run(get_daily_fiat_history_async_task())


# ------------ delayed functions --------------


@app.task(name='compute_pf_history_task')
def compute_pf_history_task(df_qty_json, tv_list_data, transactions):
    return compute_pf_history(df_qty_json, tv_list_data, transactions)


@app.task(name='get_total_pnl_task')
def get_total_pnl_task(user_id, fiat='fiat_usd'):
    return get_total_pnl(user_id, fiat)


# Tache journalière pour archiver la valeur du portefeuille ?

# Nettoyer la db token si pas utilisé et délai plus de X heures


async def wait_for_celery_result(task_id: str, timeout: int = 60, poll_interval: int = 0.5):
    """
    Attend un résultat Celery de manière asynchrone (avec timeout).
    """
    result = AsyncResult(task_id)
    elapsed = 0

    while not result.ready():
        if elapsed >= timeout:
            raise TimeoutError('Tâche trop longue, délai dépassé.')
            # raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail='Tâche trop longue, délai dépassé.')
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    if result.failed():
        raise Exception(f'La tâche a échoué : {result.result}')

    return result.result
