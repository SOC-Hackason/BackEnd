from fastapi import APIRouter
import time


from app.utils.asyncio import run_in_threadpool


router = APIRouter()

@router.get("/policy")
async def policy():
    return {"message": "policy"}


@router.get("/async_test")
async def async_test():
    await run_in_threadpool(time.sleep, 5)