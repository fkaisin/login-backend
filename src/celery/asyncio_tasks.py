import asyncio

from .coingecko import task_runner_coingecko
from .dtao import task_runner_dtao


# Fonction pour démarrer la tâche dans le background
async def start_periodic_task():
  """
  Lance le `task_runner` en arrière-plan.
  """
  asyncio.create_task(task_runner_coingecko())
  asyncio.create_task(task_runner_dtao())
