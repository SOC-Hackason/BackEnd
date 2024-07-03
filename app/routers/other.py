from fastapi import APIRouter

router = APIRouter()

@router.get("/policy")
async def policy():
    return {"message": "policy"}