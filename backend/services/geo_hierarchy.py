"""
Geographical hierarchy, sub-locations database, and regional bounding grids
for all 8 North Eastern Region (NER) states.

Includes authentic sub-locations across Sikkim, Meghalaya, Mizoram, Nagaland,
Arunachal Pradesh, Assam, Manipur, and Tripura.

Provides clean location abstraction:
    - get_location(lat, lon)
    - get_location_by_name(name)
    - search_locations(query)
    - get_region_sublocations(region_id)
    - get_region_grid(region_id)
"""

import math
from typing import Dict, List, Optional, Tuple

NER_REGIONS = {
    "sikkim": {
        "id": "sikkim",
        "name": "Sikkim",
        "state": "Sikkim",
        "center": [27.5330, 88.5122],
        "zoom": 9,
        "bounds": [[27.08, 88.00], [28.12, 88.92]],
        "districts": ["East Sikkim", "West Sikkim", "North Sikkim", "South Sikkim"],
        "description": "Himalayan mountainous state with steep gneiss/schist terrain and high landslide vulnerability."
    },
    "meghalaya": {
        "id": "meghalaya",
        "name": "Meghalaya",
        "state": "Meghalaya",
        "center": [25.5788, 91.8933],
        "zoom": 9,
        "bounds": [[25.02, 89.80], [26.11, 92.85]],
        "districts": ["East Khasi Hills", "West Khasi Hills", "Ri-Bhoi", "West Garo Hills", "Jaintia Hills"],
        "description": "Shillong plateau with extreme rainfall corridors (Cherrapunji/Mawsynram) and steep sandstone escarpments."
    },
    "mizoram": {
        "id": "mizoram",
        "name": "Mizoram",
        "state": "Mizoram",
        "center": [23.1645, 92.9376],
        "zoom": 8,
        "bounds": [[21.95, 92.25], [24.52, 93.45]],
        "districts": ["Aizawl", "Lunglei", "Champhai", "Kolasib", "Serchhip", "Mamit", "Lawngtlai", "Saiha"],
        "description": "Parallel north-south trending folded ridges with steep shale and siltstone slopes prone to road-cutting slides."
    },
    "nagaland": {
        "id": "nagaland",
        "name": "Nagaland",
        "state": "Nagaland",
        "center": [26.1584, 94.5624],
        "zoom": 8,
        "bounds": [[25.10, 93.30], [27.05, 95.25]],
        "districts": ["Kohima", "Dimapur", "Mokokchung", "Tuensang", "Wokha", "Zunheboto", "Phek", "Mon"],
        "description": "Young fold mountains of the Disang group; highly fractured shales prone to mudflows during monsoon."
    },
    "arunachal_pradesh": {
        "id": "arunachal_pradesh",
        "name": "Arunachal Pradesh",
        "state": "Arunachal Pradesh",
        "center": [28.2180, 94.7278],
        "zoom": 7,
        "bounds": [[26.65, 91.50], [29.45, 97.40]],
        "districts": ["Papum Pare", "West Kameng", "Tawang", "East Siang", "Lower Subansiri", "Lohit", "Changlang"],
        "description": "Steep eastern Himalayan slopes with high seismic activity, intense cloudbursts, and fragile Siwalik foothills."
    },
    "assam": {
        "id": "assam",
        "name": "Assam",
        "state": "Assam",
        "center": [26.2006, 92.9376],
        "zoom": 7,
        "bounds": [[24.15, 89.70], [27.95, 96.05]],
        "districts": ["Kamrup Metropolitan", "Dima Hasao", "Karbi Anglong", "Cachar", "Goalpara", "Dibrugarh"],
        "description": "Brahmaputra and Barak valleys with critical hill slope zones in Dima Hasao, Haflong and Guwahati urban hills."
    },
    "manipur": {
        "id": "manipur",
        "name": "Manipur",
        "state": "Manipur",
        "center": [24.6637, 93.9063],
        "zoom": 8,
        "bounds": [[23.83, 92.95], [25.68, 94.78]],
        "districts": ["Imphal West", "Noney", "Tamenglong", "Churachandpur", "Ukhrul", "Senapati", "Chandel"],
        "description": "Hill ranges enclosing central valley; Tupul/Noney railway corridor and NH-37 are historic landslide hotspots."
    },
    "tripura": {
        "id": "tripura",
        "name": "Tripura",
        "state": "Tripura",
        "center": [23.9408, 91.9882],
        "zoom": 8,
        "bounds": [[22.95, 91.15], [24.52, 92.35]],
        "districts": ["West Tripura", "North Tripura", "South Tripura", "Dhalai", "Khowai", "Gomati"],
        "description": "Anticlinal hill ranges (Baramura, Atharamura, Jampui) with moderate slopes vulnerable to flash rainfall."
    }
}

NER_SUBLOCATIONS = [
    # ------------------- SIKKIM -------------------
    {
        "id": "sik_gangtok",
        "name": "Gangtok",
        "region_id": "sikkim",
        "state": "Sikkim",
        "district": "East Sikkim",
        "lat": 27.3389,
        "lon": 88.6065,
        "elevation": 1650.0,
        "slope": 36.0,
        "aspect": 210.0,
        "historical_freq": 8,
        "soil_depth": 2.0,
        "cohesion": 18.0,
        "phi": 28.0,
        "porosity": 0.55,
        "unit_weight": 19.0,
        "corridor": "NH-10 Hill Highway / Gangtok Ridge",
        "description": "Capital ridge prone to debris slides and slope runoff along NH-10."
    },
    {
        "id": "sik_rimbi",
        "name": "Rimbi",
        "region_id": "sikkim",
        "state": "Sikkim",
        "district": "West Sikkim",
        "lat": 27.2025,
        "lon": 88.2114,
        "elevation": 1420.0,
        "slope": 38.5,
        "aspect": 195.0,
        "historical_freq": 7,
        "soil_depth": 2.2,
        "cohesion": 16.5,
        "phi": 27.5,
        "porosity": 0.58,
        "unit_weight": 18.8,
        "corridor": "Rimbi River Basin / Pelling-Yuksom Road",
        "description": "Steep valley slope along Rimbi River, prone to flash-flood toe erosion and rockfalls."
    },
    {
        "id": "sik_gyalshing",
        "name": "Gyalshing",
        "region_id": "sikkim",
        "state": "Sikkim",
        "district": "West Sikkim",
        "lat": 27.2831,
        "lon": 88.2536,
        "elevation": 1550.0,
        "slope": 35.0,
        "aspect": 180.0,
        "historical_freq": 6,
        "soil_depth": 2.0,
        "cohesion": 17.5,
        "phi": 28.0,
        "porosity": 0.56,
        "unit_weight": 18.9,
        "corridor": "West Sikkim District HQ Corridor",
        "description": "District administrative center on a high ridge overlooking Rangit valley."
    },
    {
        "id": "sik_pelling",
        "name": "Pelling",
        "region_id": "sikkim",
        "state": "Sikkim",
        "district": "West Sikkim",
        "lat": 27.3167,
        "lon": 88.2333,
        "elevation": 1900.0,
        "slope": 40.0,
        "aspect": 220.0,
        "historical_freq": 7,
        "soil_depth": 1.9,
        "cohesion": 17.0,
        "phi": 27.0,
        "porosity": 0.57,
        "unit_weight": 18.7,
        "corridor": "Upper Pelling Ridge",
        "description": "High altitude ridge terrain with high precipitation and jointed metamorphic rock."
    },
    {
        "id": "sik_yuksom",
        "name": "Yuksom",
        "region_id": "sikkim",
        "state": "Sikkim",
        "district": "West Sikkim",
        "lat": 27.3694,
        "lon": 88.2217,
        "elevation": 1780.0,
        "slope": 37.0,
        "aspect": 175.0,
        "historical_freq": 5,
        "soil_depth": 2.1,
        "cohesion": 18.5,
        "phi": 28.5,
        "porosity": 0.54,
        "unit_weight": 19.0,
        "corridor": "Khangchendzonga Foothill Trailhead",
        "description": "Historic gateway surrounded by dense forest cover and high gradient slopes."
    },
    {
        "id": "sik_singtam",
        "name": "Singtam",
        "region_id": "sikkim",
        "state": "Sikkim",
        "district": "East Sikkim",
        "lat": 27.2344,
        "lon": 88.4981,
        "elevation": 400.0,
        "slope": 31.0,
        "aspect": 150.0,
        "historical_freq": 8,
        "soil_depth": 2.3,
        "cohesion": 19.0,
        "phi": 29.0,
        "porosity": 0.53,
        "unit_weight": 19.2,
        "corridor": "Teesta River Confluence / NH-10",
        "description": "Crucial river basin junction heavily affected by Teesta flash floods and toe cuts."
    },
    {
        "id": "sik_singlitam",
        "name": "Singlitam",
        "region_id": "sikkim",
        "state": "Sikkim",
        "district": "West Sikkim",
        "lat": 27.1890,
        "lon": 88.2450,
        "elevation": 1280.0,
        "slope": 39.0,
        "aspect": 205.0,
        "historical_freq": 7,
        "soil_depth": 2.1,
        "cohesion": 16.0,
        "phi": 27.0,
        "porosity": 0.59,
        "unit_weight": 18.6,
        "corridor": "Lower West Sikkim Escarpment",
        "description": "Rural sub-settlement with terrace slopes subject to heavy seepage during monsoon."
    },
    {
        "id": "sik_mangan",
        "name": "Mangan",
        "region_id": "sikkim",
        "state": "Sikkim",
        "district": "North Sikkim",
        "lat": 27.5097,
        "lon": 88.5303,
        "elevation": 1310.0,
        "slope": 42.0,
        "aspect": 215.0,
        "historical_freq": 9,
        "soil_depth": 2.4,
        "cohesion": 15.0,
        "phi": 26.5,
        "porosity": 0.60,
        "unit_weight": 18.5,
        "corridor": "North Sikkim Highway (NSH)",
        "description": "High hazard zone with frequent monsoon debris flows cutting road links."
    },
    {
        "id": "sik_chungthang",
        "name": "Chungthang",
        "region_id": "sikkim",
        "state": "Sikkim",
        "district": "North Sikkim",
        "lat": 27.6042,
        "lon": 88.6475,
        "elevation": 1790.0,
        "slope": 44.0,
        "aspect": 190.0,
        "historical_freq": 9,
        "soil_depth": 2.2,
        "cohesion": 14.5,
        "phi": 26.0,
        "porosity": 0.61,
        "unit_weight": 18.4,
        "corridor": "Lachen & Lachung River Confluence",
        "description": "Epicenter of 2023 GLOF damage; high landslide hazard on steep canyon walls."
    },
    {
        "id": "sik_namchi",
        "name": "Namchi",
        "region_id": "sikkim",
        "state": "Sikkim",
        "district": "South Sikkim",
        "lat": 27.1667,
        "lon": 88.3500,
        "elevation": 1315.0,
        "slope": 32.0,
        "aspect": 170.0,
        "historical_freq": 5,
        "soil_depth": 2.0,
        "cohesion": 20.0,
        "phi": 29.5,
        "porosity": 0.54,
        "unit_weight": 19.1,
        "corridor": "South Sikkim Ridge",
        "description": "South district hub with moderate slopes and well-developed drainage networks."
    },

    # ------------------- MEGHALAYA -------------------
    {
        "id": "meg_shillong",
        "name": "Shillong",
        "region_id": "meghalaya",
        "state": "Meghalaya",
        "district": "East Khasi Hills",
        "lat": 25.5788,
        "lon": 91.8933,
        "elevation": 1525.0,
        "slope": 28.0,
        "aspect": 180.0,
        "historical_freq": 5,
        "soil_depth": 1.8,
        "cohesion": 22.0,
        "phi": 30.0,
        "porosity": 0.58,
        "unit_weight": 18.5,
        "corridor": "Central Shillong Plateau",
        "description": "State capital on undulating plateau with localized cut-slope instability."
    },
    {
        "id": "meg_mawlai",
        "name": "Mawlai",
        "region_id": "meghalaya",
        "state": "Meghalaya",
        "district": "East Khasi Hills",
        "lat": 25.6025,
        "lon": 91.8744,
        "elevation": 1490.0,
        "slope": 34.0,
        "aspect": 200.0,
        "historical_freq": 6,
        "soil_depth": 2.0,
        "cohesion": 20.0,
        "phi": 29.0,
        "porosity": 0.59,
        "unit_weight": 18.4,
        "corridor": "Mawlai Escarpment / GS Road Corridor",
        "description": "Densely populated valley slope prone to roadside mudslides during heavy rain."
    },
    {
        "id": "meg_cherrapunji",
        "name": "Cherrapunji (Sohra)",
        "region_id": "meghalaya",
        "state": "Meghalaya",
        "district": "East Khasi Hills",
        "lat": 25.2702,
        "lon": 91.7323,
        "elevation": 1430.0,
        "slope": 41.0,
        "aspect": 185.0,
        "historical_freq": 8,
        "soil_depth": 1.5,
        "cohesion": 19.0,
        "phi": 28.0,
        "porosity": 0.55,
        "unit_weight": 18.8,
        "corridor": "Southern Khasi Escarpment",
        "description": "One of the wettest spots on Earth with vertical gorge cliffs prone to rockfalls."
    },
    {
        "id": "meg_mawsynram",
        "name": "Mawsynram",
        "region_id": "meghalaya",
        "state": "Meghalaya",
        "district": "East Khasi Hills",
        "lat": 25.2974,
        "lon": 91.5828,
        "elevation": 1400.0,
        "slope": 43.0,
        "aspect": 190.0,
        "historical_freq": 8,
        "soil_depth": 1.6,
        "cohesion": 18.0,
        "phi": 27.5,
        "porosity": 0.56,
        "unit_weight": 18.7,
        "corridor": "Balat-Mawsynram Road",
        "description": "World-record rainfall regime causing intense surface stripping and debris flows."
    },
    {
        "id": "meg_nongpoh",
        "name": "Nongpoh",
        "region_id": "meghalaya",
        "state": "Meghalaya",
        "district": "Ri-Bhoi",
        "lat": 25.9038,
        "lon": 91.8806,
        "elevation": 580.0,
        "slope": 26.0,
        "aspect": 160.0,
        "historical_freq": 4,
        "soil_depth": 2.2,
        "cohesion": 24.0,
        "phi": 30.5,
        "porosity": 0.54,
        "unit_weight": 18.2,
        "corridor": "Guwahati-Shillong Expressway (NH-6)",
        "description": "Foothill sector with weathered red soils vulnerable to highway cut failures."
    },
    {
        "id": "meg_tura",
        "name": "Tura",
        "region_id": "meghalaya",
        "state": "Meghalaya",
        "district": "West Garo Hills",
        "lat": 25.5144,
        "lon": 90.2201,
        "elevation": 650.0,
        "slope": 35.0,
        "aspect": 210.0,
        "historical_freq": 6,
        "soil_depth": 2.0,
        "cohesion": 21.0,
        "phi": 28.5,
        "porosity": 0.58,
        "unit_weight": 18.5,
        "corridor": "Tura Peak Escarpment",
        "description": "Garo Hills administrative hub flanked by steep Tura range; flash floods trigger landslides."
    },

    # ------------------- MIZORAM -------------------
    {
        "id": "miz_aizawl",
        "name": "Aizawl",
        "region_id": "mizoram",
        "state": "Mizoram",
        "district": "Aizawl",
        "lat": 23.7271,
        "lon": 92.7176,
        "elevation": 1132.0,
        "slope": 42.0,
        "aspect": 250.0,
        "historical_freq": 9,
        "soil_depth": 1.6,
        "cohesion": 15.0,
        "phi": 27.0,
        "porosity": 0.60,
        "unit_weight": 18.5,
        "corridor": "Aizawl City Ridge / NH-54",
        "description": "State capital built directly on a razorback ridge with steep shale/sandstone beds."
    },
    {
        "id": "miz_durtlang",
        "name": "Durtlang Ridge",
        "region_id": "mizoram",
        "state": "Mizoram",
        "district": "Aizawl",
        "lat": 23.7833,
        "lon": 92.7333,
        "elevation": 1380.0,
        "slope": 45.0,
        "aspect": 260.0,
        "historical_freq": 9,
        "soil_depth": 1.4,
        "cohesion": 14.0,
        "phi": 26.0,
        "porosity": 0.62,
        "unit_weight": 18.3,
        "corridor": "Durtlang Geological Fault Zone",
        "description": "Famous geological fault zone with severe historical cliff collapse events."
    },
    {
        "id": "miz_lunglei",
        "name": "Lunglei",
        "region_id": "mizoram",
        "state": "Mizoram",
        "district": "Lunglei",
        "lat": 22.8875,
        "lon": 92.7380,
        "elevation": 1222.0,
        "slope": 39.0,
        "aspect": 230.0,
        "historical_freq": 7,
        "soil_depth": 1.8,
        "cohesion": 16.0,
        "phi": 27.5,
        "porosity": 0.59,
        "unit_weight": 18.6,
        "corridor": "Southern Mizoram Ridge",
        "description": "Major southern hub prone to slope creep and building foundation shear."
    },
    {
        "id": "miz_champhai",
        "name": "Champhai",
        "region_id": "mizoram",
        "state": "Mizoram",
        "district": "Champhai",
        "lat": 23.4735,
        "lon": 93.3283,
        "elevation": 1678.0,
        "slope": 33.0,
        "aspect": 190.0,
        "historical_freq": 5,
        "soil_depth": 1.9,
        "cohesion": 18.0,
        "phi": 29.0,
        "porosity": 0.57,
        "unit_weight": 18.8,
        "corridor": "Indo-Myanmar Border Corridor",
        "description": "High-altitude eastern border valley surrounded by steep tertiary strata."
    },

    # ------------------- NAGALAND -------------------
    {
        "id": "nag_kohima",
        "name": "Kohima",
        "region_id": "nagaland",
        "state": "Nagaland",
        "district": "Kohima",
        "lat": 25.6740,
        "lon": 94.1086,
        "elevation": 1444.0,
        "slope": 34.0,
        "aspect": 200.0,
        "historical_freq": 6,
        "soil_depth": 1.9,
        "cohesion": 17.0,
        "phi": 28.0,
        "porosity": 0.57,
        "unit_weight": 18.8,
        "corridor": "Kohima Saddle / NH-29 Corridor",
        "description": "Saddle ridge location prone to deep sinking zones along NH-29."
    },
    {
        "id": "nag_dzukou",
        "name": "Dzükou Valley Slope",
        "region_id": "nagaland",
        "state": "Nagaland",
        "district": "Kohima",
        "lat": 25.5539,
        "lon": 94.0628,
        "elevation": 2452.0,
        "slope": 41.0,
        "aspect": 175.0,
        "historical_freq": 7,
        "soil_depth": 1.7,
        "cohesion": 16.0,
        "phi": 27.5,
        "porosity": 0.59,
        "unit_weight": 18.6,
        "corridor": "High Montane Eco-Corridor",
        "description": "Steep alpine valley walls subjected to heavy moisture condensation and sliding."
    },
    {
        "id": "nag_mokokchung",
        "name": "Mokokchung",
        "region_id": "nagaland",
        "state": "Nagaland",
        "district": "Mokokchung",
        "lat": 26.3248,
        "lon": 94.5298,
        "elevation": 1325.0,
        "slope": 35.0,
        "aspect": 220.0,
        "historical_freq": 5,
        "soil_depth": 2.0,
        "cohesion": 18.5,
        "phi": 28.5,
        "porosity": 0.56,
        "unit_weight": 18.9,
        "corridor": "Central Ao Naga Hills",
        "description": "Continuous ridge settlements with frequent road cut collapses along Mokokchung-Amguri road."
    },
    {
        "id": "nag_wokha",
        "name": "Wokha",
        "region_id": "nagaland",
        "state": "Nagaland",
        "district": "Wokha",
        "lat": 26.0990,
        "lon": 94.2610,
        "elevation": 1313.0,
        "slope": 36.0,
        "aspect": 195.0,
        "historical_freq": 6,
        "soil_depth": 1.8,
        "cohesion": 17.5,
        "phi": 28.0,
        "porosity": 0.58,
        "unit_weight": 18.7,
        "corridor": "Mount Tiyi Slopes",
        "description": "Slopes of sacred Mount Tiyi vulnerable to clayey Disang soil mobilization."
    },

    # ------------------- ARUNACHAL PRADESH -------------------
    {
        "id": "aru_itanagar",
        "name": "Itanagar",
        "region_id": "arunachal_pradesh",
        "state": "Arunachal Pradesh",
        "district": "Papum Pare",
        "lat": 27.0844,
        "lon": 93.6053,
        "elevation": 320.0,
        "slope": 30.0,
        "aspect": 160.0,
        "historical_freq": 4,
        "soil_depth": 2.2,
        "cohesion": 20.0,
        "phi": 29.0,
        "porosity": 0.62,
        "unit_weight": 18.2,
        "corridor": "Banderdewa-Itanagar NH-415",
        "description": "State capital foothill terrain with heavy monsoon cloudburst vulnerability."
    },
    {
        "id": "aru_banderdewa",
        "name": "Banderdewa",
        "region_id": "arunachal_pradesh",
        "state": "Arunachal Pradesh",
        "district": "Papum Pare",
        "lat": 27.1350,
        "lon": 93.8167,
        "elevation": 190.0,
        "slope": 33.0,
        "aspect": 150.0,
        "historical_freq": 6,
        "soil_depth": 2.5,
        "cohesion": 19.0,
        "phi": 28.0,
        "porosity": 0.60,
        "unit_weight": 18.3,
        "corridor": "Assam-Arunachal Border Pass",
        "description": "Gateway pass with unconsolidated Siwalik sediments subject to rapid sliding."
    },
    {
        "id": "aru_tawang",
        "name": "Tawang",
        "region_id": "arunachal_pradesh",
        "state": "Arunachal Pradesh",
        "district": "Tawang",
        "lat": 27.5861,
        "lon": 91.8594,
        "elevation": 3048.0,
        "slope": 44.0,
        "aspect": 180.0,
        "historical_freq": 7,
        "soil_depth": 1.5,
        "cohesion": 16.0,
        "phi": 28.0,
        "porosity": 0.55,
        "unit_weight": 19.1,
        "corridor": "Sela Pass - Tawang Strategic Highway",
        "description": "High Himalayan periglacial terrain with freeze-thaw weathering and steep slopes."
    },
    {
        "id": "aru_pasighat",
        "name": "Pasighat",
        "region_id": "arunachal_pradesh",
        "state": "Arunachal Pradesh",
        "district": "East Siang",
        "lat": 28.0667,
        "lon": 95.3333,
        "elevation": 155.0,
        "slope": 28.0,
        "aspect": 140.0,
        "historical_freq": 5,
        "soil_depth": 2.4,
        "cohesion": 22.0,
        "phi": 30.0,
        "porosity": 0.58,
        "unit_weight": 18.4,
        "corridor": "Siang River Gorge Entry",
        "description": "Foot of mighty Siang River gorge; extreme water volume causes bank and slope failure."
    },

    # ------------------- ASSAM -------------------
    {
        "id": "asm_guwahati",
        "name": "Guwahati",
        "region_id": "assam",
        "state": "Assam",
        "district": "Kamrup Metropolitan",
        "lat": 26.1445,
        "lon": 91.7362,
        "elevation": 55.0,
        "slope": 25.0,
        "aspect": 90.0,
        "historical_freq": 3,
        "soil_depth": 2.0,
        "cohesion": 28.0,
        "phi": 32.0,
        "porosity": 0.52,
        "unit_weight": 17.8,
        "corridor": "Guwahati Urban Hills (Kamakhya, Narakasur)",
        "description": "Urban hill slopes prone to sudden earth cutting and gully erosion during flash rains."
    },
    {
        "id": "asm_haflong",
        "name": "Haflong",
        "region_id": "assam",
        "state": "Assam",
        "district": "Dima Hasao",
        "lat": 25.1764,
        "lon": 93.0200,
        "elevation": 680.0,
        "slope": 38.0,
        "aspect": 210.0,
        "historical_freq": 9,
        "soil_depth": 2.2,
        "cohesion": 17.0,
        "phi": 27.0,
        "porosity": 0.60,
        "unit_weight": 18.5,
        "corridor": "Lumding-Silchar Hill Railway Corridor",
        "description": "Historic landslide hub in Dima Hasao where 2022 monsoon devastated entire railway tracks."
    },
    {
        "id": "asm_silchar",
        "name": "Silchar",
        "region_id": "assam",
        "state": "Assam",
        "district": "Cachar",
        "lat": 24.8333,
        "lon": 92.7789,
        "elevation": 35.0,
        "slope": 14.0,
        "aspect": 80.0,
        "historical_freq": 2,
        "soil_depth": 2.6,
        "cohesion": 30.0,
        "phi": 33.0,
        "porosity": 0.50,
        "unit_weight": 17.6,
        "corridor": "Barak Valley Basin",
        "description": "Low-gradient valley basin, impacted by surrounding slope debris and river inundation."
    },

    # ------------------- MANIPUR -------------------
    {
        "id": "man_imphal",
        "name": "Imphal",
        "region_id": "manipur",
        "state": "Manipur",
        "district": "Imphal West",
        "lat": 24.8170,
        "lon": 93.9368,
        "elevation": 786.0,
        "slope": 22.0,
        "aspect": 140.0,
        "historical_freq": 3,
        "soil_depth": 2.0,
        "cohesion": 24.0,
        "phi": 31.0,
        "porosity": 0.56,
        "unit_weight": 18.0,
        "corridor": "Imphal Valley Rim",
        "description": "Central valley capital surrounded by sensitive sedimentary hill slopes."
    },
    {
        "id": "man_tupul",
        "name": "Tupul / Noney",
        "region_id": "manipur",
        "state": "Manipur",
        "district": "Noney",
        "lat": 24.7083,
        "lon": 93.6333,
        "elevation": 620.0,
        "slope": 44.0,
        "aspect": 240.0,
        "historical_freq": 9,
        "soil_depth": 2.3,
        "cohesion": 15.0,
        "phi": 26.0,
        "porosity": 0.61,
        "unit_weight": 18.5,
        "corridor": "Jiribam-Imphal Railway Project / Ijei River",
        "description": "Site of devastating 2022 massive debris avalanche blocking the Ijei River."
    },
    {
        "id": "man_churachandpur",
        "name": "Churachandpur",
        "region_id": "manipur",
        "state": "Manipur",
        "district": "Churachandpur",
        "lat": 24.3333,
        "lon": 93.6667,
        "elevation": 914.0,
        "slope": 31.0,
        "aspect": 170.0,
        "historical_freq": 4,
        "soil_depth": 2.1,
        "cohesion": 22.0,
        "phi": 29.0,
        "porosity": 0.57,
        "unit_weight": 18.2,
        "corridor": "Southwestern Manipur Hills",
        "description": "Rolling hills of Disang shale with moderate to high monsoon slip susceptibility."
    },

    # ------------------- TRIPURA -------------------
    {
        "id": "tri_agartala",
        "name": "Agartala",
        "region_id": "tripura",
        "state": "Tripura",
        "district": "West Tripura",
        "lat": 23.8315,
        "lon": 91.2868,
        "elevation": 15.0,
        "slope": 8.0,
        "aspect": 70.0,
        "historical_freq": 1,
        "soil_depth": 2.0,
        "cohesion": 30.0,
        "phi": 33.0,
        "porosity": 0.50,
        "unit_weight": 17.5,
        "corridor": "Howrah River Basin",
        "description": "Plain capital with low slope gradient and minimal mass movement risk."
    },
    {
        "id": "tri_baramura",
        "name": "Baramura Range",
        "region_id": "tripura",
        "state": "Tripura",
        "district": "Khowai",
        "lat": 23.8750,
        "lon": 91.5650,
        "elevation": 260.0,
        "slope": 29.0,
        "aspect": 110.0,
        "historical_freq": 4,
        "soil_depth": 2.2,
        "cohesion": 23.0,
        "phi": 29.5,
        "porosity": 0.55,
        "unit_weight": 18.1,
        "corridor": "NH-8 Baramura Hill Cut",
        "description": "Major highway corridor traversing forested anticlinal ridge with cut-slope slides."
    },
    {
        "id": "tri_jampui",
        "name": "Jampui Hills",
        "region_id": "tripura",
        "state": "Tripura",
        "district": "North Tripura",
        "lat": 23.9500,
        "lon": 92.2833,
        "elevation": 930.0,
        "slope": 34.0,
        "aspect": 160.0,
        "historical_freq": 5,
        "soil_depth": 1.9,
        "cohesion": 21.0,
        "phi": 28.5,
        "porosity": 0.56,
        "unit_weight": 18.3,
        "corridor": "Highest Range in Tripura / Vanghmun",
        "description": "Elevated ridge with orange orchards and steep valleys prone to rainfall-triggered slips."
    }
]


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance between two coordinates in kilometers."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2)**2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2)**2
    return 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(max(1 - a, 1e-12)))


def get_all_regions_meta() -> List[Dict]:
    """Returns metadata for all 8 NER regions."""
    return list(NER_REGIONS.values())


def get_region(region_id: str) -> Optional[Dict]:
    """Look up region by canonical ID."""
    return NER_REGIONS.get((region_id or "").strip().lower())


def get_all_sublocations() -> List[Dict]:
    """Returns all curated sub-locations across the 8 NER regions."""
    return list(NER_SUBLOCATIONS)


def get_sublocations_for_region(region_id: str) -> List[Dict]:
    """Filter sub-locations belonging to a specific region."""
    rid = (region_id or "").strip().lower()
    return [loc for loc in NER_SUBLOCATIONS if loc["region_id"] == rid]


def get_location_by_name(name: str) -> Optional[Dict]:
    """Find a sub-location by exact or substring name match."""
    q = (name or "").strip().lower()
    if not q:
        return None
    # 1. Exact match
    for loc in NER_SUBLOCATIONS:
        if loc["name"].lower() == q or loc["id"].lower() == q:
            return loc
    # 2. Substring match
    for loc in NER_SUBLOCATIONS:
        if q in loc["name"].lower() or loc["name"].lower() in q:
            return loc
    return None


def get_location(lat: float, lon: float, max_dist_km: float = 25.0) -> Dict:
    """
    Find the closest location or create an interpolated sub-location profile
    for arbitrary coordinates anywhere in the NER.
    """
    best_loc = None
    min_dist = float("inf")
    for loc in NER_SUBLOCATIONS:
        d = _distance_km(lat, lon, loc["lat"], loc["lon"])
        if d < min_dist:
            min_dist = d
            best_loc = loc

    if best_loc and min_dist <= max_dist_km:
        res = dict(best_loc)
        res["distance_km"] = round(min_dist, 2)
        res["match_type"] = "named_sublocation"
        return res

    # If further away, dynamically generate an interpolated local site profile
    # using the nearest regional anchor characteristics.
    nearest_region_id = "assam"
    min_region_dist = float("inf")
    for rid, rdata in NER_REGIONS.items():
        rdist = _distance_km(lat, lon, rdata["center"][0], rdata["center"][1])
        if rdist < min_region_dist:
            min_region_dist = rdist
            nearest_region_id = rid

    base = best_loc or NER_SUBLOCATIONS[0]
    return {
        "id": f"coord_{round(lat, 3)}_{round(lon, 3)}",
        "name": f"Lat {lat:.3f}°, Lon {lon:.3f}°",
        "region_id": nearest_region_id,
        "state": NER_REGIONS[nearest_region_id]["state"],
        "district": f"{NER_REGIONS[nearest_region_id]['name']} Sector",
        "lat": round(lat, 4),
        "lon": round(lon, 4),
        "elevation": base["elevation"],
        "slope": base["slope"],
        "aspect": base["aspect"],
        "historical_freq": base["historical_freq"],
        "soil_depth": base["soil_depth"],
        "cohesion": base["cohesion"],
        "phi": base["phi"],
        "porosity": base["porosity"],
        "unit_weight": base["unit_weight"],
        "corridor": f"{NER_REGIONS[nearest_region_id]['name']} Local Slopes",
        "description": f"Interpolated local monitoring point in {NER_REGIONS[nearest_region_id]['name']}.",
        "distance_km": round(min_dist, 2),
        "match_type": "interpolated_coordinate"
    }


def search_locations(query: str, limit: int = 15) -> List[Dict]:
    """
    Search across all NER regions, districts, and named sub-locations.
    Returns ranked matches.
    """
    q = (query or "").strip().lower()
    if not q:
        return NER_SUBLOCATIONS[:limit]

    results = []
    # 1. Search sub-locations
    for loc in NER_SUBLOCATIONS:
        score = 0
        name_lower = loc["name"].lower()
        district_lower = loc.get("district", "").lower()
        state_lower = loc["state"].lower()
        corridor_lower = loc.get("corridor", "").lower()

        if name_lower == q:
            score += 100
        elif name_lower.startswith(q):
            score += 70
        elif q in name_lower:
            score += 50
        elif q in district_lower:
            score += 30
        elif q in state_lower:
            score += 20
        elif q in corridor_lower:
            score += 15

        if score > 0:
            item = dict(loc)
            item["search_score"] = score
            results.append(item)

    # 2. Search regions
    for rid, reg in NER_REGIONS.items():
        rname = reg["name"].lower()
        if q in rname:
            results.append({
                "id": f"reg_{rid}",
                "name": reg["name"],
                "region_id": rid,
                "state": reg["state"],
                "district": "All Districts",
                "lat": reg["center"][0],
                "lon": reg["center"][1],
                "elevation": 1200.0,
                "slope": 30.0,
                "aspect": 180.0,
                "historical_freq": 5,
                "soil_depth": 2.0,
                "cohesion": 20.0,
                "phi": 29.0,
                "porosity": 0.57,
                "unit_weight": 18.5,
                "corridor": f"{reg['name']} Regional Territory",
                "description": reg["description"],
                "search_score": 40 if rname.startswith(q) else 25,
                "is_region": True
            })

    results.sort(key=lambda x: x.get("search_score", 0), reverse=True)
    return results[:limit]


def generate_region_grid(region_id: str, step_deg: float = 0.22) -> List[Dict]:
    """
    Generates a geographical grid of cells for a region to provide continuous
    surface coverage (A1, A2, B1...) without substituting generic city points.
    """
    reg = get_region(region_id)
    if not reg:
        return []

    bounds = reg["bounds"]
    min_lat, min_lon = bounds[0]
    max_lat, max_lon = bounds[1]

    grid_cells = []
    row_idx = 0
    curr_lat = max_lat - (step_deg / 2)

    while curr_lat >= min_lat:
        row_char = chr(ord('A') + (row_idx % 26))
        col_idx = 1
        curr_lon = min_lon + (step_deg / 2)
        while curr_lon <= max_lon:
            cell_id = f"{region_id[:3].upper()}-{row_char}{col_idx}"
            center_lat = round(curr_lat, 4)
            center_lon = round(curr_lon, 4)

            # Find nearest known sub-location to calibrate terrain characteristics
            nearest = min(
                [loc for loc in NER_SUBLOCATIONS if loc["region_id"] == region_id] or NER_SUBLOCATIONS,
                key=lambda x: _distance_km(center_lat, center_lon, x["lat"], x["lon"])
            )

            # Bounding box of the grid cell
            cell_bounds = [
                [round(curr_lat - step_deg / 2, 4), round(curr_lon - step_deg / 2, 4)],
                [round(curr_lat + step_deg / 2, 4), round(curr_lon + step_deg / 2, 4)]
            ]

            grid_cells.append({
                "cell_id": cell_id,
                "region_id": region_id,
                "region_name": reg["name"],
                "name": f"{reg['name']} Grid {cell_id}",
                "center": [center_lat, center_lon],
                "bounds": cell_bounds,
                "lat": center_lat,
                "lon": center_lon,
                "slope": nearest["slope"],
                "elevation": nearest["elevation"],
                "historical_freq": nearest["historical_freq"],
                "soil_depth": nearest["soil_depth"],
                "cohesion": nearest["cohesion"],
                "phi": nearest["phi"],
                "porosity": nearest["porosity"],
                "unit_weight": nearest["unit_weight"],
                "nearest_sublocation": nearest["name"]
            })
            col_idx += 1
            curr_lon += step_deg
        row_idx += 1
        curr_lat -= step_deg

    return grid_cells
