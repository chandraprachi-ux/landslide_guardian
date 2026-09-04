from fastapi import APIRouter, HTTPException
import pandas as pd
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

router = APIRouter()

DATA_50K_PATH = BASE_DIR / "ml" / "real_landslide_50k_dataset.csv"
TRAIN_DATA_PATH = BASE_DIR / "ml" / "train_dataset.csv"
TEST_DATA_PATH = BASE_DIR / "ml" / "test_dataset.csv"

@router.get("/dataset/test")
def get_test_dataset(limit: int = 100):
    """
    Returns rows from the 50,000+ dataset for dashboard tracking & evaluation.
    """
    target = DATA_50K_PATH if os.path.exists(DATA_50K_PATH) else TEST_DATA_PATH
    if not os.path.exists(target):
        raise HTTPException(status_code=404, detail="Dataset file not found.")

    df = pd.read_csv(target)
    subset_df = df.head(limit)

    return {
        "total_records": len(df),
        "returned_records": len(subset_df),
        "dataset_name": target.name,
        "data": subset_df.to_dict(orient="records")
    }

@router.get("/dataset/train-summary")
def get_train_summary():
    """
    Returns statistical summary of the 55,000-sample training dataset.
    """
    target = DATA_50K_PATH if os.path.exists(DATA_50K_PATH) else TRAIN_DATA_PATH
    if not os.path.exists(target):
        raise HTTPException(status_code=404, detail="Training dataset file not found.")

    df = pd.read_csv(target)
    return {
        "total_samples": len(df),
        "dataset_name": target.name,
        "summary": df.describe().to_dict()
    }