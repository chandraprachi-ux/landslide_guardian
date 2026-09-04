from fastapi import APIRouter, HTTPException
from ..database.mongodb import clean_document, db_manager
from ..models.schemas import PredictRequest
from ..services.risk_service import calculate_risk_assessment

router = APIRouter()


@router.post("/risk/predict")
async def predict_risk(req: PredictRequest):
    try:
        return await calculate_risk_assessment(
            req.location_name, req.latitude, req.longitude, req.sensor_data
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/risk/latest")
async def get_latest_risk():
    doc = db_manager.risk_assessments.find_one(sort=[("timestamp", -1)])
    if doc:
        return clean_document(doc)
    try:
        return await calculate_risk_assessment("Gangtok, Sikkim", 27.3389, 88.6065)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/risk/all")
async def get_all_risks():
    docs = list(db_manager.risk_assessments.find().sort("timestamp", -1).limit(100))
    return [clean_document(doc) for doc in docs]
