from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from backend.core.config import Settings, get_settings
from backend.security.ops import require_ops_api
from backend.services.operations import OperationsService

router = APIRouter(prefix="/api/ops", tags=["operations"], dependencies=[Depends(require_ops_api)])


@router.get("/overview")
async def overview(request: Request, settings: Settings = Depends(get_settings)) -> dict[str, int]:
    return await OperationsService(request.app.state.db, settings).overview()


@router.get("/queues")
async def queues(
    request: Request,
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=100, ge=1, le=250),
) -> dict[str, object]:
    return await OperationsService(request.app.state.db, settings).queues(limit=limit)


@router.post("/deliveries/{entitlement_id}/retry")
async def retry_delivery(
    entitlement_id: UUID, request: Request, settings: Settings = Depends(get_settings)
) -> dict[str, object]:
    try:
        return await OperationsService(request.app.state.db, settings).retry_delivery(
            entitlement_id=entitlement_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None


@router.post("/maintenance/run")
async def run_maintenance(request: Request, settings: Settings = Depends(get_settings)) -> dict[str, int]:
    return await OperationsService(request.app.state.db, settings).maintenance_tick(schedule_next=False)
