# Border Control Screening System — MHA / SSB (SIH 2026)

AI-Based Fake Identity & Document Screening System (PS 26188).
FastAPI backend with 8 pipeline modules + React officer UI.

## All Modules (complete)

| # | Module | File | What it does |
|---|--------|------|--------------|
| 1 | **OCR** | `modules/ocr_module.py` | EasyOCR + Tesseract, field extraction (Aadhaar, passport, etc.) |
| 2 | **Validation** | `modules/validation_module.py` | Checksum (Aadhaar Verhoeff / MRZ), QR match, expiry, regex format |
| 3 | **Tampering** | `modules/tampering_module.py` | ELA + FFT + LBP texture heuristic + EXIF editor fingerprint |
| 4 | **Face** | `modules/face_verification.py` | DeepFace ArcFace match + dlib cross-check + anti-spoof |
| 5 | **Liveness** | `modules/liveness_module.py` | EAR blink, skin texture, rPPG proxy, anti-spoof fusion |
| 6 | **Identity Graph** | `modules/identity_graph_module.py` | Face embedding store — flags same face under different ID |
| 7 | **Risk Engine** | `modules/risk_engine.py` | Hard gates + weighted fusion → GENUINE / SUSPICIOUS / FAKE |
| 8 | **Audit Trail** | `modules/audit_module.py` | SHA-256 hash-chained SQLite log (no raw images stored) |

Orchestration: `main.py` · Adapters: `adapters.py` · UI: `frontend/src/App.jsx`

## Quick start (Windows)

Double-click **`start.bat`** → opens backend (`:8000`) + frontend (`:5173`).

Always use `python -m uvicorn` (not bare `uvicorn`).

## Verify all modules work

```bash
python test_modules.py
```

Check live status: `GET http://localhost:8000/modules/status`

## Manual run

```bash
pip install -r requirements.txt
python -m uvicorn main:app --reload          # terminal 1
cd frontend && npm install && npm run dev    # terminal 2
```

## Demo samples (`samples/`)

| File | Use |
|------|-----|
| `demo_aadhaar.jpg` | National ID / Aadhaar OCR test |
| `demo_passport_with_face.jpg` | Passport + face on document |
| `demo_selfie.jpg` | Matching selfie (upload via **Upload Selfie File**) |

For Aadhaar: select **National ID**, upload your card + selfie of the same person.

## API endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/verify` | POST | Full screening (document + selfie + doc_type) |
| `/health` | GET | Backend alive check |
| `/modules/status` | GET | Per-module health smoke test |
| `/audit-log` | GET | Recent hash-chained audit entries |

## Notes for judges

- **Tampering "CNN"** slot uses an **LBP texture heuristic** (not a trained ResNet) — disclosed honestly in UI.
- **rPPG pulse** on a single selfie frame is a best-effort proxy; video capture improves blink detection.
- **First `/verify` call** may take 30–60s while AI models load.
