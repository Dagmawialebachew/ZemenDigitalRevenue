from fastapi import APIRouter

from backend.api.routes.control import router as control_router
from backend.api.routes.health import router as health_router
from backend.api.routes.final_control import router as final_control_router
from backend.api.routes.miniapp import router as miniapp_router
from backend.api.routes.marketing import router as marketing_router
from backend.api.routes.operations import router as operations_router
from backend.api.routes.product_control import router as product_control_router
from backend.api.routes.public_media import router as public_media_router
from backend.api.routes.telegram import router as telegram_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(control_router)
api_router.include_router(final_control_router)
api_router.include_router(marketing_router)
api_router.include_router(product_control_router)
api_router.include_router(public_media_router)
api_router.include_router(telegram_router)
api_router.include_router(miniapp_router)
api_router.include_router(operations_router)
