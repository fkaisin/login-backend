import asyncio
import logging

from celery import Celery
from celery.schedules import crontab
from src.celery.coingecko import coingecko_async_task

# from src.celery.dtao import fetch_cg_ids_on_coingecko_async_task
from src.celery.fiat import fiat_realtime_async_task, get_daily_fiat_history_async_task

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
    # sender.add_periodic_task(crontab(minute='*/5'), dtao_task.s(), name='dtao 5 min')
    sender.add_periodic_task(crontab(minute='*/2'), coingecko_task.s(), name='cg toutes les 2 min')
    sender.add_periodic_task(crontab(minute='*/5'), fiat_realtime_task.s(), name='fiat toutes les 5 min')
    sender.add_periodic_task(crontab(minute=0, hour=1), daily_fiat_history_task.s(), name='dailyfiat 1h du matin')


# @app.task
# def dtao_task():
#     logger.info('>>> Lancement de la tâche dtao_task')
#     asyncio.run(dtao_async_task())


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


# reconstruire l'historique via l'appel à taostats.io ?

# Tache journalière pour archiver la valeur du portefeuille ?

# Nettoyer la db token si pas utilisé et délai plus de X heures
