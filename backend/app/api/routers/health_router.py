from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/")
async def health_check():
    return {"status": "Backend is active. Database and Workflow engines ready."}
