from fastapi import APIRouter

from app.features.counter.router import router as counter_router
from app.features.genai.api import router as genai_router
from app.features.uploads.api import router as uploads_router

api_router = APIRouter()
api_router.include_router(counter_router)
api_router.include_router(genai_router)
api_router.include_router(uploads_router)
