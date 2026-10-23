import os
from fastapi import APIRouter

router = APIRouter()


@router.get("")
@router.get("/", include_in_schema=False)  # accept the trailing slash too, but keep /docs tidy
async def root():
    """
    Root endpoint - Health check
    """
    return {
        "message": "if u see this , the API is running",
        "status": "online",
        "API_VERSION": f"{os.getenv('API_VERSION', '')}",
    }
