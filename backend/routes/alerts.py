from fastapi import APIRouter

from ..database.mongodb import clean_document, db_manager

router = APIRouter()


@router.get("/alerts")
async def get_active_alerts():
    alerts = list(
        db_manager.alerts.find().sort(
            [("risk_score", -1), ("timestamp", -1)]
        ).limit(100)
    )
    return [clean_document(alert) for alert in alerts]
