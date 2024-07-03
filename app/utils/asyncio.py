import asyncio
from concurrent.futures import ThreadPoolExecutor

async def run_in_threadpool(f, *args, **kwargs):
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        result = await loop.run_in_executor(
            pool, 
            lambda: f(*args, **kwargs)
        )
    return result