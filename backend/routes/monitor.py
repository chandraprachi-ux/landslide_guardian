from fastapi import APIRouter, HTTPException

from ..database.mongodb import clean_document, db_manager
from ..services.monitor import (
    get_monitoring_state, run_monitor_cycle, set_monitor_enabled,
)

router = APIRouter()


@router.get("/monitor/status")
async def monitoring_status():
    """Current automatic monitoring state, interval and last cycle summary."""
    return get_monitoring_state()


@router.post("/monitor/run-now")
async def run_now():
    """Trigger an immediate full monitoring cycle across all NER locations."""
    try:
        return await run_monitor_cycle(force=True)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/monitor/pause")
async def pause():
    """Pause automatic periodic monitoring (manual predicts still auto-dispatch)."""
    return {"enabled": set_monitor_enabled(False)}


@router.post("/monitor/resume")
async def resume():
    """Resume automatic periodic monitoring."""
    return {"enabled": set_monitor_enabled(True)}


@router.get("/monitor/logs")
async def logs(limit: int = 50):
    """Recent automatic SOS dispatch audit trail (admin/verification tool)."""
    docs = list(db_manager.notification_log.find().sort("timestamp", -1).limit(min(limit, 200)))
    return [clean_document(d) for d in docs]


@router.get("/monitoring/hotspots")
async def active_hotspots():
    """Returns detected emerging hotspots across the NER."""
    from ..services.monitor import get_active_hotspots
    spots = get_active_hotspots()
    return {
        "count": len(spots),
        "hotspots": spots
    }
