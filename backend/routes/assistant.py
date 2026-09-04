import os
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()

# ---------------------------------------------------------------------------
# RAG KNOWLEDGE BASE (DOMAIN GEOTECHNICAL & MATHEMATICAL CONTEXT)
# ---------------------------------------------------------------------------
RAG_KNOWLEDGE_BASE = [
    {
        "id": "pore_pressure_physics",
        "title": "Pore-Water Pressure (u) Formulation",
        "keywords": ["pore", "pressure", "pwp", "formula", "water pressure", "hydrostatic", "gamma", "u"],
        "content": (
            "PORE-WATER PRESSURE FORMULATION:\n"
            "• Fundamental Law: u = γ_w · h_w, where γ_w ≈ 9.81 kN/m³ (unit weight of water, equivalent to 9.81 kPa per metre of head).\n"
            "• Effective Head Rise (h_w): In our software screening pipeline, h_w is estimated via the Antecedent Rainfall Index (ARI):\n"
            "  ARI ≈ R_24h + 0.5 · R_72h (decayed precipitation storage).\n"
            "• Infiltration Head: h_w = [ARI · (S_eff - S_base)] capped by soil depth z_soil and porosity n.\n"
            "• Mechanical Impact: Positive pore pressure builds in the saturated zone, directly counteracting normal stress σ_n and lowering effective stress σ' = σ_n - u."
        )
    },
    {
        "id": "factor_of_safety",
        "title": "Mohr-Coulomb Limit Equilibrium Factor of Safety (FS)",
        "keywords": ["factor of safety", "fos", "fs", "mohr coulomb", "shear", "stability", "cohesion", "friction angle"],
        "content": (
            "FACTOR OF SAFETY (MOHR-COULOMB INFINITE SLOPE):\n"
            "• Formula: FS = [c' + (σ_n - u) · tan(φ')] / τ_shear\n"
            "  where:\n"
            "  - c' = effective soil cohesion (14–30 kPa across NER formations)\n"
            "  - φ' = effective internal friction angle (26°–33°)\n"
            "  - σ_n = γ · z · cos²(β) [Total normal stress at slip plane]\n"
            "  - u = pore-water pressure counteracting normal stress\n"
            "  - τ_shear = γ · z · sin(β) · cos(β) [Gravitational driving shear stress]\n"
            "• Classification: FS < 1.0 indicates critical active failure; FS < 1.3 indicates high vulnerability; FS ≥ 1.3 is conditionally stable."
        )
    },
    {
        "id": "composite_risk_score",
        "title": "Composite Risk Score Architecture",
        "keywords": ["risk score", "composite", "ml probability", "how is risk calculated", "calculation", "percentage", "weight"],
        "content": (
            "COMPOSITE RISK CALCULATION PIPELINE:\n"
            "• Final Risk Score (0–100%) = 0.55 · (ML_Prob · 100) + 0.25 · Geotechnical_Score + 0.20 · Criteria_Stress_Score.\n"
            "  1. ML Component (55% weight): ExtraTrees classifier trained on 55,000+ Northeast India samples incorporating 9 geotechnical/meteorological features.\n"
            "  2. Geotechnical Stability (25% weight): Normalized score derived from Mohr-Coulomb FS: Score = 100 · (1.55 - FS) / 0.75.\n"
            "  3. Multi-Criteria Trigger Stress (20% weight): Linear weighted stress of Rainfall (28%), Soil Saturation (27%), Pore Pressure (30%), and Tilt (15%).\n"
            "• Risk Tiers: LOW (<31%), MODERATE (31–60%), HIGH (61–80%), CRITICAL (>80%)."
        )
    },
    {
        "id": "data_consistency",
        "title": "Map and Assessment Data Colliding & Synchronization",
        "keywords": ["data different", "collide", "map vs assessment", "different section", "consistency", "same"],
        "content": (
            "DATA SYNCHRONIZATION PIPELINE:\n"
            "• Both the Interactive Regional Risk Map (/location/detail) and the AI Risk Assessment (/prediction/live) query the identical calculate_risk_assessment engine.\n"
            "• They resolve identical coordinates, evaluate the same live Open-Meteo precipitation, apply the same regional terrain parameters (slope, cohesion, porosity), compute identical pore pressure (u = γ_w · h_w), and infer the exact same 55k-sample ML model probability."
        )
    },
    {
        "id": "ner_hotspots",
        "title": "North Eastern Region (NER) Focus Areas and Hotspots",
        "keywords": ["gangtok", "sikkim", "aizawl", "mizoram", "shillong", "meghalaya", "tupul", "manipur", "haflong", "assam", "hotspot"],
        "content": (
            "NER GEOLOGICAL REGIONS & HOTSPOTS:\n"
            "• Sikkim: Steep Himalayan gneiss/schist (36°–42° slopes). High historical corridors: Gangtok NH-10, Rimbi, Mangan.\n"
            "• Mizoram: Folded anticlinal ridges with fractured shale/siltstone (38°–44° slopes). Hotspots: Durtlang Ridge, Aizawl.\n"
            "• Manipur: Railway cut-slopes and Siwalik colluvium (40°–44° slopes). Hotspot: Tupul / Noney railway corridor.\n"
            "• Meghalaya: High rainfall plateau escarpments (Mawlai, Cherrapunji/Sohra).\n"
            "• Assam: Dima Hasao (Haflong) hill section track collapse prone to continuous monsoon depression."
        )
    },
    {
        "id": "emergency_action",
        "title": "Emergency Response and NDMA Safety",
        "keywords": ["emergency", "112", "evacuate", "sos", "alert", "ndma", "safety"],
        "content": (
            "EMERGENCY ADVISORY PROTOCOL:\n"
            "• National Emergency Hotline: 112 (Disaster Management Helpline: 1070).\n"
            "• At HIGH (61–80%) or CRITICAL (>80%) risk, evacuate steep cut-slopes and debris-flow gullies immediately.\n"
            "• In Landslide Guardian, CRITICAL alerts automatically trigger regional SOS dispatches to registered residents in that state."
        )
    }
]

def retrieve_relevant_context(query: str) -> str:
    """RAG Retriever: scores query against document keywords and content."""
    q_tokens = set(query.lower().replace("?", "").replace(",", "").split())
    scored_docs = []

    for doc in RAG_KNOWLEDGE_BASE:
        score = 0
        for kw in doc["keywords"]:
            if kw in query.lower():
                score += 3
        for token in q_tokens:
            if token in doc["content"].lower():
                score += 1
        if score > 0:
            scored_docs.append((score, doc["content"]))

    scored_docs.sort(key=lambda x: x[0], reverse=True)
    if not scored_docs:
        # Fallback to general architecture
        return RAG_KNOWLEDGE_BASE[2]["content"]
    
    # Return top 2 retrieved chunks
    return "\n\n".join([doc[1] for doc in scored_docs[:2]])

class AssistantRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)

@router.post("/assistant/chat")
async def assistant_chat(req: AssistantRequest):
    """
    RAG-grounded Assistant: Provides professional, clear, descriptive, and actionable
    geotechnical disaster intelligence, mathematical formulations, and safety guidance.
    """
    q = req.message.lower().strip()

    # 1. Immediate Life-Safety Emergencies
    if any(x in q for x in ("112", "emergency", "ambulance", "police", "help line", "evacuate now", "trapped")):
        return {
            "status": "ok",
            "reply": (
                "🚨 **URGENT EMERGENCY EVACUATION PROTOCOL**\n\n"
                "• **Emergency Hotlines in India:** Dial **112** (All-in-One National Emergency) or **1070** (State Disaster Management Control Room).\n"
                "• **Immediate Action:** If you notice fresh tension cracks in the ground, tilting utility poles, or rumbling sounds, evacuate laterally away from the slope path immediately.\n"
                "• **Do Not Re-enter:** Never attempt to retrieve belongings from a destabilized slope or valley bed during heavy rainfall."
            )
        }

    # 2. Pore-Water Pressure Calculations & Physics
    if any(x in q for x in ("pore", "pressure", "pwp", "u =")):
        return {
            "status": "ok",
            "reply": (
                "📐 **Pore-Water Pressure (u) Formulation & Geotechnical Significance:**\n\n"
                "**1. Fundamental Governing Equation:**\n"
                "`u = γ_w · h_w`\n"
                "• `γ_w = 9.81 kN/m³` represents the unit weight of water (equivalent to 9.81 kPa of hydrostatic pressure per vertical metre of water head).\n"
                "• `h_w` represents the effective water head rising above the unsaturated baseline in the slope profile.\n\n"
                "**2. Hydrological Wetting Front & Infiltration:**\n"
                "In software screening mode, effective head `h_w` is estimated using the **Antecedent Rainfall Index (ARI)**:\n"
                "`ARI ≈ R_24h + 0.5 · R_72h`\n"
                "As persistent precipitation infiltrates the soil matrix, saturation exceeds field capacity, inducing positive pore pressure within the weathered bedrock interface.\n\n"
                "**3. Why Pore Pressure Destabilizes Mountain Slopes:**\n"
                "According to Terzaghi's effective stress principle: `σ' = σ_n - u`.\n"
                "Positive pore-water pressure directly counteracts the normal confining stress `σ_n`. By pushing soil grains apart, it drastically reduces frictional shear resistance along the failure plane, triggering catastrophic slope failure."
            )
        }

    # 3. Factor of Safety & Geotechnical Stability
    if any(x in q for x in ("factor of safety", "fos", "mohr", "limit equilibrium", "stability")):
        return {
            "status": "ok",
            "reply": (
                "⚖️ **Mohr-Coulomb Limit Equilibrium Factor of Safety (FS):**\n\n"
                "**1. Analytical Equation (Infinite Slope Model):**\n"
                "`FS = [c' + (σ_n - u) · tan(φ')] / τ_shear`\n\n"
                "**2. Parameter Breakdown:**\n"
                "• **Resisting Forces (Shear Strength):**\n"
                "  - `c'`: Effective soil cohesion (typically 14–28 kPa in North-East Indian geological formations).\n"
                "  - `(σ_n - u)`: Effective normal stress counteracting buoyant pore-water pressure.\n"
                "  - `φ'`: Effective internal friction angle (26°–33° for regional weathered schist, shale, and colluvium).\n"
                "• **Driving Forces (Gravitational Shear Stress):**\n"
                "  - `τ_shear = γ · z · sin(β) · cos(β)`: Downslope gravitational stress governed by slope angle `β` and overburden depth `z`.\n\n"
                "**3. Safety Classification:**\n"
                "• **FS < 1.0 (CRITICAL FAILURE):** Driving shear forces exceed shear resistance; active slip in progress.\n"
                "• **1.0 ≤ FS < 1.3 (HIGH VULNERABILITY):** Slope is marginally stable; sensitive to acute precipitation.\n"
                "• **FS ≥ 1.3 (CONDITIONAL STABILITY):** Adequate structural safety factor under prevailing moisture."
            )
        }

    # 4. Overall Risk Score Architecture
    if any(x in q for x in ("how is risk", "composite", "formula", "score calculated", "percentage")):
        return {
            "status": "ok",
            "reply": (
                "📊 **Composite Multi-Tier Landslide Risk Score Architecture:**\n\n"
                "Our early-warning engine combines physics and artificial intelligence into a standardized 0–100% composite index:\n\n"
                "`Risk Score = 0.55 · (ML_Prob · 100) + 0.25 · Geotechnical_Score + 0.20 · Criteria_Stress`\n\n"
                "• **1. Machine Learning Component (55% Weight):**\n"
                "  An `ExtraTreesClassifier` trained on 55,000 regional samples evaluating multi-dimensional non-linear interactions across 9 parameters (precipitation, moisture, pressure, slope, tilt, acceleration).\n"
                "• **2. Geotechnical Limit Equilibrium (25% Weight):**\n"
                "  Directly derived from Mohr-Coulomb Factor of Safety: `Score = 100 · (1.55 - FS) / 0.75`, ensuring that slopes with $FS < 1.0$ push the risk into danger tiers.\n"
                "• **3. Multi-Criteria Trigger Stress (20% Weight):**\n"
                "  Real-time acute stress index blending 24h Rainfall (28%), Soil Saturation (27%), Pore Pressure (30%), and Ground Tilt (15%).\n\n"
                "**Risk Tiers:** 🟢 LOW (<31%) · 🟡 MODERATE (31–60%) · 🟠 HIGH (61–80%) · 🔴 CRITICAL (>80%)."
            )
        }

    # 5. Dataset, Machine Learning & Verification
    if any(x in q for x in ("50,000", "50000", "55000", "dataset", "accuracy", "train", "synthetic")):
        return {
            "status": "ok",
            "reply": (
                "🧠 **Machine Learning Model & Physics-Grounded Dataset:**\n\n"
                "• **Dataset Scale:** 54,996 total samples modeled across 12 high-vulnerability corridors in the 8 NER states.\n"
                "• **Why Physics-Consistent Synthesis is Required:** Real-world slope failure events are rare, destructively severing sensor links upon catastrophic collapse. We synthesized 55,000 physics-calibrated data points using genuine Mohr-Coulomb equations and Geological Survey of India (GSI) slope profiles.\n"
                "• **Model Architecture:** `ExtraTreesClassifier` (150 estimators, max depth 16) achieving high precision and 1.000 ROC-AUC across an 11,000-sample holdout test partition without overfitting."
            )
        }

    # 6. SOS Notification & Email Verification
    if any(x in q for x in ("sos", "email", "alert", "dispatch", "register", "verify")):
        return {
            "status": "ok",
            "reply": (
                "📬 **Emergency SOS Dispatch & Verification Architecture:**\n\n"
                "• **Strict Verification Requirement:** To protect citizens and disaster agencies from spoofed alerts, **only email-verified residents** (authenticated via secure 6-digit OTP) are eligible to receive emergency SOS dispatches.\n"
                "• **Automatic Dispatch:** When our continuous monitoring daemon detects that risk in a specific corridor or state reaches **HIGH (61–80%) or CRITICAL (>80%)**, automated emergency emails are immediately sent to all verified residents registered for that locality.\n"
                "• **Anti-Spam Cooldown:** A 60-minute locality cooldown prevents repetitive inbox flooding while an event is ongoing.\n"
                "• **Authorized Admin Override:** Verified disaster-management officers can execute an immediate direct manual dispatch via the restricted Administrator Console."
            )
        }

    # 7. Fallback Context via RAG
    context = retrieve_relevant_context(q)
    return {
        "status": "ok",
        "reply": (
            f"🛡️ **Guardian Geotechnical Assistant**\n\n"
            f"{context}\n\n"
            "You can ask me detailed technical questions regarding:\n"
            "• **Pore-water pressure formulation** (`u = γ_w · h_w`)\n"
            "• **Mohr-Coulomb Factor of Safety derivation** (`FS`)\n"
            "• **Composite risk score calculation** (ML + Geotechnical + Trigger Stress)\n"
            "• **Emergency SOS dispatch protocols & citizen verification**\n"
            "• **Specific geological hotspot analysis across the 8 NER states**"
        ),
        "context_used": True
    }

