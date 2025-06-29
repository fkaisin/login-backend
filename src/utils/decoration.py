import time
from functools import wraps


def timeit(func):
  @wraps(func)
  def wrapper(*args, **kwargs):
    start = time.perf_counter()
    result = func(*args, **kwargs)
    end = time.perf_counter()
    print(f'⏱️ {func.__name__} exécutée en {end - start:.4f} secondes')
    return result

  return wrapper


def async_timeit(func):
  @wraps(func)
  async def wrapper(*args, **kwargs):
    start = time.perf_counter()
    result = await func(*args, **kwargs)
    end = time.perf_counter()
    print(f'⏱️ {func.__name__} exécutée en {end - start:.4f} secondes')
    return result

  return wrapper
