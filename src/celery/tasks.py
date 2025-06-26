import asyncio
import logging

from celery import Celery
from celery.schedules import crontab
from src.celery.coingecko import coingecko_async_task
from src.celery.dtao import dtao_async_task

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
  sender.add_periodic_task(crontab(minute='*/5'), dtao_task.s(), name='dtao 5 min')
  sender.add_periodic_task(crontab(minute='*/2'), coingecko_task.s(), name='cg 2 min')


@app.task
def dtao_task():
  logger.info('>>> Lancement de la tâche dtao_task')
  asyncio.run(dtao_async_task())


@app.task
def coingecko_task():
  logger.info('>>> Lancement de la tâche coingecko_task')
  asyncio.run(coingecko_async_task())
