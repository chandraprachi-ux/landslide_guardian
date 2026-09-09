import csv
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException

BASE_DIR = Path(__file__).resolve().parents[1]

router = APIRouter()

DATA_50K_PATH = BASE_DIR / "ml" / "real_landslide_50k_dataset.csv"
TRAIN_DATA_PATH = BASE_DIR / "ml" / "train_dataset.csv"
TEST_DATA_PATH = BASE_DIR / "ml" / "test_dataset.csv"


@router.get("/dataset/test")
def get_test_dataset(limit: int = 100):
    """
    Returns rows from the dataset for dashboard tracking & evaluation.
    """
    target = DATA_50K_PATH if os.path.exists(DATA_50K_PATH) else TEST_DATA_PATH
    if not os.path.exists(target):
        raise HTTPException(status_code=404, detail="Dataset file not found.")

    records = []
    total_count = 0
    with open(target, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_count += 1
            if len(records) < limit:
                # Convert numbers if possible
                parsed_row = {}
                for k, v in row.items():
                    try:
                        parsed_row[k] = float(v) if "." in v else int(v)
                    except ValueError:
                        parsed_row[k] = v
                records.append(parsed_row)

    return {
        "total_records": total_count,
        "returned_records": len(records),
        "dataset_name": target.name,
        "data": records
    }


@router.get("/dataset/train-summary")
def get_train_summary():
    """
    Returns statistical summary of the training dataset.
    """
    target = DATA_50K_PATH if os.path.exists(DATA_50K_PATH) else TRAIN_DATA_PATH
    if not os.path.exists(target):
        raise HTTPException(status_code=404, detail="Training dataset file not found.")

    total_samples = 0
    with open(target, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for _ in reader:
            total_samples += 1

    return {
        "total_samples": total_samples,
        "dataset_name": target.name,
        "summary": {"records": total_samples, "status": "NER Geotechnical Dataset Active"}
    }