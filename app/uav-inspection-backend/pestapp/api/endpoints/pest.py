from fastapi import APIRouter
from pestapp.api.endpoints.pest_telemetry import router as telemetry_router
from pestapp.api.endpoints.pest_routes import router as routes_router
from pestapp.api.endpoints.pest_models import router as models_router
from pestapp.api.endpoints.pest_reports import router as reports_router
from pestapp.api.endpoints.pest_missions import router as missions_router
from pestapp.api.endpoints.pest_media import router as media_router

router = APIRouter()

router.include_router(telemetry_router)
router.include_router(routes_router)
router.include_router(models_router)
router.include_router(reports_router)
router.include_router(missions_router)
router.include_router(media_router)