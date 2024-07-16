from fastapi import APIRouter
from fastapi.responses import RedirectResponse
import time


from app.utils.asyncio import run_in_threadpool


router = APIRouter()

@router.get("/policy")
async def policy():
    return {"message": "policy"}


@router.get("/async_test")
async def async_test():
    await run_in_threadpool(time.sleep, 5)

@router.get("/redirect_to_gmail")
async def redirect_to_gmail():
    return RedirectResponse(url="googlegmail://")