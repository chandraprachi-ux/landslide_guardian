# Landslide Guardian — SIH Software-Only Prototype v2.3

## What this version does

- 100% software demonstration; no physical hardware is required.
- **Real-time rainfall → estimated pore pressure → region-specific threshold → risk → ML** pipeline (`backend/services/rainfall_service.py`, `pore_pressure.py`, `region_config.py`, `risk_service.py`).
- **8 region configs** (Sikkim, Assam, Meghalaya, Mizoram, Nagaland, Arunachal Pradesh, Manipur, Tripura), each with its own geotechnical site profile, infiltration model and calibrated screening thresholds (labelled RESEARCH/CALIBRATION, not officially validated).
- **Email OTP verification**: residents register, receive a one-time code by email, and only **verified** emails receive SOS. Wrong codes are rate-limited; OTPs expire and are stored hashed (never plaintext) — except in the unconfigured-SMTP demo where the code is shown client-side.
- **Verified-only automatic regional SOS**: background monitor recomputes risk for all regions and auto-emails verified residents whose region matches on HIGH/CRITICAL, with a per-region cooldown.
- **Admin-only manual SOS dispatch** and **admin registered-user management** (list, verify status, delete).
- Live weather for 8 NER focus locations with a 7-day forecast.
- Location-aware thresholds for: 1. Rainfall 2. Soil saturation/moisture 3. Pore-water pressure 4. Ground tilt.
- ML risk probability using a corrected Random Forest feature pipeline.
- Simplified Mohr-Coulomb factor-of-safety screening.
- Future sensor-compatible API: `/api/sensors/data`. **Tilt is isolated as a hardware-only sensor and is never simulated.**
- Public citizen registration requires only name, email and location; no user login.
- Restricted server-authenticated admin console.
- While an admin session is active, public pages redirect back to the admin console until logout.
- MongoDB Atlas remains supported; memory mode is retained for offline demonstration.

### Key scientific safeguards (per SIH master specification)

- **No synthetic/random rainfall or tilt** is ever injected into the Live Now pipeline. Tilt is hardware-only.
- **Pore pressure ≠ rainfall**: pore pressure is *estimated* from rainfall via a physically-based infiltration/head model and clearly labelled "ESTIMATED · site calibration required", never presented as measured or as rainfall.
- **No fabricated validated thresholds**: all region thresholds are flagged RESEARCH/CALIBRATION.
- **NO RAIN (valid 0 mm)** is distinguished from **NO DATA (provider failure)**. Failed weather API never auto-declares CRITICAL or LOW, and never triggers automatic SOS.
- **No credentials in the frontend** and **admin-only operations are backend-protected**.
- The backend **never crashes** on external API / email / SMTP failures.

The weather source reuses the project's existing provider: **Open-Meteo** (`https://api.open-meteo.com/v1/forecast`), documented as such in `/api/config`.

## Important scientific limitation

There is no universal soil-moisture or pore-pressure value at which every slope fails. The software therefore uses coordinate-matched prototype geotechnical profiles and a simplified infinite-slope Mohr-Coulomb calculation. The pore-pressure value is an estimate in software mode. A real piezometer/pressure sensor is needed for measured pore pressure.

The ML training file currently uses physically-inspired synthetic data because this repository does not contain a validated labelled NER landslide dataset. Do NOT claim the model is "100% accurate" or operationally validated during the SIH presentation. The defensible claim is that the architecture is ready to ingest real measurements and retrain against real labelled data.

## Run

```cmd
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r backend\requirements.txt
python -m backend.ml.train_model
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Open:

`http://127.0.0.1:8000/`

## MongoDB

Set `MONGODB_URI` in `backend/.env`. The app can still run in temporary memory mode if Atlas is unavailable.

## Admin

Default SIH demo credentials:

- Username: `admin`
- Password: `guardian-demo`

Change them in `backend/.env` before deployment.

## Real email SOS

Copy `.env.example` settings into `backend/.env` and configure SMTP. For Gmail, use an App Password rather than your normal Gmail password.

Required:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=yourgmail@gmail.com
SMTP_PASSWORD=your-app-password
ALERT_FROM_EMAIL=yourgmail@gmail.com
```

The admin console (and the automatic monitor) sends a real email to every **verified**
registered resident whose location/region matches. Unverified registrations are excluded
until they verify their email via the OTP flow.

### Email verification flow

1. Resident registers (starts UNVERIFIED).
2. `/api/auth/send-otp` emails a 6-digit code (hashed at rest; has a 60 s resend
   cooldown and a 5-attempt limit; expires after 10 min).
3. `/api/auth/verify-otp` marks the email verified.
4. Only afterwards does the person receive automatic/manual regional SOS.

When no SMTP credentials are configured the system **simulates** delivery and (for the
SIH demo only) returns the code in the API response so the flow can be demonstrated.

## Region configuration (Sikkim/Assam and friends)

`backend/services/region_config.py` defines 8 regions, each with:

- `site`: soil depth, porosity, infiltration (drainage constant, max saturation rise).
- `thresholds`: per-region screening thresholds for rainfall (24 h / 72 h),
  soil moisture, pore pressure (high/critical) and tilt — all flagged
  **RESEARCH/CALIBRATION**, not officially validated failure limits.

Pore pressure is estimated as `u = γw · hw` from the antecedent rainfall index
(`backend/services/pore_pressure.py`), with the estimate clearly labelled and used only
as a screening input alongside the existing ML assessment.

## Future sensor architecture

```text
Rain gauge ─┐
Soil sensor ├── ESP32 / Gateway ──> POST /api/sensors/data
Tilt/IMU ───┤                           │
Piezometer ─┘                           ▼
                                Sensor normalization
                                        │
Live weather + terrain + history ───────┤
                                        ▼
                             ML probability + FS model
                                        │
                                        ▼
                                  Risk score / level
                                        │
                            Admin → (auto) Email SOS
```

The physical sensors are intentionally not part of the current SIH demo. They are an
integration path, not a dependency. **Tilt is a hardware-only sensor and is never
simulated** in the Live Now workflow.

## API

- `GET /api/health`
- `GET /api/config`
- `GET /api/weather/ner`
- `GET /api/environment/{lat}/{lon}`
- `POST /api/risk/predict`
- `GET /api/risk/latest`
- `GET /api/risk/all`
- `POST /api/sensors/data`
- `GET /api/sensors/latest`
- `POST /api/sos/register` (public)
- `GET /api/sos/registrations` (admin)
- `POST /api/sos/dispatch` (admin, verified-only recipients)
- `POST /api/admin/login`
- `GET /api/admin/session`
- `GET /api/admin/registered-users` (admin)
- `DELETE /api/admin/registered-users/{id-or-email}?confirm=yes` (admin)
- `GET /api/monitor/status`
- `POST /api/monitor/run-now`
- `POST /api/monitor/pause`
- `POST /api/monitor/resume`
- `GET /api/monitor/logs`

### Rainfall → Pore Pressure → Threshold → Risk pipeline

- `GET  /api/weather/live` — live atmospheric/rainfall readings for a location.
- `GET  /api/rainfall/live` — live rainfall (and stores the observation, dedup-protected).
- `GET  /api/rainfall/history` — recent stored rainfall for a location.
- `POST /api/pore-pressure/calculate` — estimate pore pressure from rainfall via the infiltration/head model.
- `POST /api/prediction/live` — full Live Now: live rainfall → estimated pore pressure → region threshold → risk + ML.
- `GET  /api/regions` / `GET /api/regions/{region}` — monitored region configs & thresholds.

### Email OTP verification

- `POST /api/auth/register` — register a resident (starts UNVERIFIED).
- `POST /api/auth/send-otp` — email a one-time code (respects resend cooldown).
- `POST /api/auth/verify-otp` — verify the code; marks the resident `email_verified=true`.

## Automatic monitoring + auto SOS (v2.2)

The prototype now runs a **background automatic monitor** that keeps the live risk
level fresh for all 8 NER locations and **auto-notifies verified residents without an
admin clicking anything**.

How it works:

1. On server startup, the FastAPI app launches a background loop
   (`backend/services/monitor.py`).
2. Every `MONITOR_INTERVAL_MINUTES` (default `15`, configurable) it re-runs the full
   risk pipeline for **every** NER location using live Open-Meteo weather.
3. When any region's risk reaches **HIGH (≥61) or CRITICAL (≥81)**, the engine
   **automatically emails every EMAIL-VERIFIED resident** whose city/area or region
   matches (`auto_dispatch` in `monitor.py`). Unverified residents are excluded.
4. A per-location **cooldown** (`SOS_COOLDOWN_MINUTES`, default `60`) prevents
   spamming the same region on every tick. Every automatic dispatch is written to a
   `notification_log` collection (audit trail) and shown live in the admin console.
5. Manual `POST /api/risk/predict` and `POST /api/prediction/live` calls also trigger
   the same auto-dispatch automatically on HIGH/CRITICAL results.
6. **No data → no false alarm**: if the weather provider is unreachable the result is
   marked `DATA_UNAVAILABLE`/`NO_DATA` and automatic SOS is suppressed. A valid **0 mm**
   reading is stored as `NO_RAIN` and is treated as a real low-rainfall observation.

Config (add to `backend/.env`):

```text
# Optional tuning (defaults shown)
MONITOR_INTERVAL_MINUTES=15
SOS_COOLDOWN_MINUTES=60
OTP_EXPIRY_MINUTES=10
OTP_RESEND_COOLDOWN_SECONDS=60
OTP_MAX_ATTEMPTS=5
OTP_SALT=<long random string>
```

Frontend live views (auto-refreshing):

- **Home** — a Live warning banner polls every 20s and turns red when a region is CRITICAL.
- **Dashboard** — refreshes the latest risk every 30s and shows an AUTO MONITORING badge.
- **Risk Assessment** — a region selector (Sikkim/Assam/…) and a **⚡ Live Now** button that runs the real rainfall→pore-pressure→threshold pipeline (no simulated tilt/rainfall). Tilt is labelled Hardware Sensor Only.
- **Admin console** — auto-refreshes every 30s and shows the regional monitoring table (Region | Rainfall | Pore Pressure | Threshold | Risk | SOS), the automatic-monitoring state, dispatch log, a **▶ Run Now** button, registered-user management (verify status + remove), and the admin-only manual emergency dispatch.
- **Alerts & SOS** — register for alerts, **verify your email with the OTP**, and see the active-warnings feed (refreshes every 20s). Manual dispatch is **admin-only** (via the admin console).

