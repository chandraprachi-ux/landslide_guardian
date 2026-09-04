from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from ..services.geo_hierarchy import (
    NER_REGIONS, NER_SUBLOCATIONS,
    get_all_regions_meta, get_region,
    get_all_sublocations, get_sublocations_for_region,
    get_location, get_location_by_name,
    search_locations as search_geo,
    generate_region_grid
)

router = APIRouter()

PREDEFINED_LOCATIONS = [
    {"name": "Gangtok, Sikkim", "state": "Sikkim", "latitude": 27.3389, "longitude": 88.6065},
    {"name": "Shillong, Meghalaya", "state": "Meghalaya", "latitude": 25.5788, "longitude": 91.8933},
    {"name": "Aizawl, Mizoram", "state": "Mizoram", "latitude": 23.7271, "longitude": 92.7176},
    {"name": "Kohima, Nagaland", "state": "Nagaland", "latitude": 25.6740, "longitude": 94.1086},
    {"name": "Itanagar, Arunachal Pradesh", "state": "Arunachal Pradesh", "latitude": 27.0844, "longitude": 93.6053},
    {"name": "Guwahati, Assam", "state": "Assam", "latitude": 26.1445, "longitude": 91.7362},
    {"name": "Imphal, Manipur", "state": "Manipur", "latitude": 24.8170, "longitude": 93.9368},
    {"name": "Agartala, Tripura", "state": "Tripura", "latitude": 23.8315, "longitude": 91.2868}
]


@router.get("/location/search")
async def search_locations(q: str = ""):
    """
    Rich location search: autocompletes across all 8 regions, districts, and named sub-locations
    (e.g., Rimbi, Singlitam, Mawlai, Durtlang, Tupul, etc.).
    Preserves backwards-compatibility with old search consumer format while adding rich metadata.
    """
    if not q:
        # Return merged list: predefined anchors + top sub-locations
        items = []
        for loc in NER_SUBLOCATIONS:
            items.append({
                "name": f"{loc['name']}, {loc['state']}",
                "location_name": loc["name"],
                "state": loc["state"],
                "region_id": loc["region_id"],
                "district": loc.get("district", ""),
                "latitude": loc["lat"],
                "longitude": loc["lon"],
                "lat": loc["lat"],
                "lon": loc["lon"],
                "elevation": loc["elevation"],
                "slope": loc["slope"],
                "corridor": loc.get("corridor", ""),
            })
        return items

    results = search_geo(q, limit=20)
    out = []
    for r in results:
        out.append({
            "name": f"{r['name']}, {r['state']}" if not r.get("is_region") else f"{r['name']} (Region)",
            "location_name": r["name"],
            "state": r["state"],
            "region_id": r["region_id"],
            "district": r.get("district", ""),
            "latitude": r["lat"],
            "longitude": r["lon"],
            "lat": r["lat"],
            "lon": r["lon"],
            "elevation": r.get("elevation", 1000.0),
            "slope": r.get("slope", 25.0),
            "corridor": r.get("corridor", ""),
            "is_region": r.get("is_region", False),
            "description": r.get("description", "")
        })
    return out


@router.get("/locations/hierarchy")
async def get_locations_hierarchy():
    """Complete NER hierarchy: 8 regions with their districts and sub-locations."""
    regions_out = []
    for rid, reg in NER_REGIONS.items():
        sublocs = get_sublocations_for_region(rid)
        regions_out.append({
            **reg,
            "sublocations_count": len(sublocs),
            "sublocations": sublocs
        })
    return {
        "count": len(regions_out),
        "total_sublocations": len(NER_SUBLOCATIONS),
        "regions": regions_out
    }


@router.get("/locations/region/{region_id}")
async def get_region_locations(region_id: str):
    """Sub-locations for a specific region."""
    reg = get_region(region_id)
    if not reg:
        raise HTTPException(status_code=404, detail="Region not found.")
    sublocs = get_sublocations_for_region(region_id)
    return {
        "region": reg,
        "count": len(sublocs),
        "sublocations": sublocs
    }


@router.get("/locations/grid/{region_id}")
async def get_region_grid_route(region_id: str, step: float = Query(default=0.22, ge=0.1, le=1.0)):
    """Generates geographical grid cells covering the entire area of a region."""
    reg = get_region(region_id)
    if not reg:
        raise HTTPException(status_code=404, detail="Region not found.")
    cells = generate_region_grid(region_id, step_deg=step)
    return {
        "region_id": region_id,
        "region_name": reg["name"],
        "count": len(cells),
        "cells": cells
    }


@router.get("/location/resolve")
async def resolve_location(lat: float = Query(..., ge=-90, le=90),
                           lon: float = Query(..., ge=-180, le=180),
                           name: Optional[str] = None):
    """Resolve an exact coordinate to nearest sub-location or dynamic local sector."""
    if name:
        match = get_location_by_name(name)
        if match:
            return match
    return get_location(lat, lon)