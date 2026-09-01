"""
main.py — Backend API Orchestrator
------------------------------------
Wires all 6 detection modules + risk fusion + audit trail into one API.

Modules:
  1. OCR          — modules/ocr_module.py
  2. Validation   — modules/validation_module.py
  3. Tampering    — modules/tampering_module.py
  4. Face         — modules/face_verification.py
  5. Liveness     — modules/liveness_module.py
  6. Identity Graph — modules/identity_graph_module.py
  7. Risk Engine  — modules/risk_engine.py
  8. Audit Trail  — modules/audit_module.py

Run with:  python -m uvicorn main:app --reload
"""

import logging
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from modules.ocr_module import process_document
from modules.validation_module import DocumentValidator
from modules.tampering_module import analyze_tampering
from modules.face_verification import verify_face_with_cross_check
from modules.liveness_module import analyze_liveness
from modules.identity_graph_module import check_identity_reuse, get_graph_stats
from modules.risk_engine import run_risk_engine, RiskEngineInput
from modules.audit_module import compute_document_hash, log_verification, get_recent_entries, verify_chain_integrity
from fastapi.middleware.cors import CORSMiddleware
import adapters


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

app = FastAPI(
    title="Smart India Hackathon — Fake Document Detection",
    description="AI-Based Fake Identity & Document Screening System (PS 26188)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/verify")
async def verify(
    document_image: UploadFile = File(...),
    selfie_photo: UploadFile = File(...),
    doc_type: str = Form(...),
):
    with tempfile.TemporaryDirectory() as tmp:
        doc_path = _save_upload(document_image, tmp, "document.jpg")
        selfie_path = _save_upload(selfie_photo, tmp, "selfie.jpg")

        # --- Module 1: OCR ---
        try:
            ocr_raw = process_document(doc_path, doc_type=doc_type)
        except Exception as exc:
            logger.error(f"OCR failed: {exc}")
            return JSONResponse(status_code=422, content={"error": f"OCR failed: {exc}"})

        # If OCR found a 12-digit Aadhaar number, force National ID rules
        # (users often leave "Passport" selected by mistake).
        extracted_id = (ocr_raw.get("fields") or {}).get("ID", "")
        if extracted_id.replace(" ", "").isdigit() and len(extracted_id.replace(" ", "")) == 12:
            if doc_type not in ("national_id", "aadhaar"):
                logger.info("Auto-detected Aadhaar number — switching doc_type to national_id")
                doc_type = "national_id"

        validation_fields = adapters.ocr_fields_to_validation_fields(ocr_raw, doc_type=doc_type)

        # --- Module 2: Validation ---
        validator = DocumentValidator()
        validation_raw = validator.run_all(
            doc_type=doc_type, fields=validation_fields, document_image_path=doc_path
        )

        # --- Module 3: Tampering ---
        try:
            tampering_result = analyze_tampering(doc_path)
        except ValueError as exc:
            logger.error(f"Tampering failed: {exc}")
            return JSONResponse(status_code=422, content={"error": f"Tampering analysis failed: {exc}"})

        # --- Module 4: Face verification ---
        face_bundle = verify_face_with_cross_check(doc_path, selfie_path)

        # --- Module 5: Liveness ---
        antispoof = {
            "is_real": face_bundle["primary"].is_real,
            "antispoofing_score": face_bundle["primary"].antispoofing_score,
        }
        liveness_result = analyze_liveness(selfie_path, antispoof=antispoof)
        liveness_fields = adapters.liveness_result_to_risk_fields(liveness_result)

        # --- Module 6: Identity graph ---
        doc_hash = compute_document_hash(doc_path)
        identity_result = check_identity_reuse(
            selfie_path,
            id_number=validation_fields.get("id_number"),
            name=validation_fields.get("name"),
            document_hash=doc_hash,
        )

        # --- Risk Engine ---
        risk_input = RiskEngineInput(
            document_type=doc_type,
            ocr_confidence=ocr_raw["ocr_confidence"],
            **adapters.validation_result_to_risk_fields(
                validation_raw, doc_type=doc_type, ocr_confidence=ocr_raw["ocr_confidence"]
            ),
            **adapters.tampering_result_to_risk_fields(tampering_result),
            **adapters.face_result_to_risk_fields(face_bundle),
            blink_score=liveness_fields["blink_score"],
            pulse_detected=liveness_fields["pulse_detected"],
            bpm=liveness_fields["bpm"],
            identity_graph_flagged=identity_result.get("flagged", False),
        )
        risk_result = run_risk_engine(risk_input)

        # --- Audit log ---
        audit_entry = _log_audit_safely(
            doc_path, ocr_raw, validation_raw, tampering_result,
            face_bundle, liveness_result, risk_result,
        )

        response = adapters.build_frontend_response(
            ocr_raw, validation_raw, tampering_result, face_bundle,
            liveness_result, risk_result, audit_entry, identity_result,
        )
        return JSONResponse(response)


def _save_upload(upload: UploadFile, tmp_dir: str, filename: str) -> str:
    dest = Path(tmp_dir) / filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(upload.file, f)
    return str(dest)


def _log_audit_safely(doc_path, ocr_raw, validation_raw, tampering_result, face_bundle, liveness_result, risk_result) -> dict:
    frontend_score = round((1 - risk_result.score) * 100)
    verdict = "GENUINE" if frontend_score >= 75 else "SUSPICIOUS" if frontend_score >= 45 else "FAKE"

    try:
        doc_hash = compute_document_hash(doc_path)
        ocr_view, validation_view, tampering_view, face_view = adapters.build_audit_view(
            ocr_raw, validation_raw, tampering_result, face_bundle, liveness_result
        )
        log_verification(
            document_hash=doc_hash,
            ocr=ocr_view, validation=validation_view,
            tampering=tampering_view, face=face_view,
            risk_score=frontend_score, verdict=verdict,
        )
        recent = get_recent_entries(limit=1)
        entry = recent[0] if recent else {}
        return {
            "logId": f"LOG-{entry.get('entry_hash', '000000')[:6].upper()}",
            "timestamp": entry.get("timestamp", ""),
            "docHash": doc_hash,
            "prevHash": entry.get("prev_hash"),
            "currHash": entry.get("entry_hash"),
            "verdict": verdict,
        }
    except Exception as exc:
        logger.error(f"Audit logging failed (non-fatal): {exc}")
        return {
            "logId": "LOG-ERROR",
            "timestamp": "",
            "docHash": None,
            "prevHash": None,
            "currHash": None,
            "verdict": verdict,
        }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/modules/status")
async def modules_status():
    """Health check for every pipeline module."""
    status = {}

    # Module 1 — OCR
    try:
        from modules.ocr_module import _get_reader
        _get_reader()
        status["ocr"] = {"ok": True, "engine": "EasyOCR + Tesseract"}
    except Exception as exc:
        status["ocr"] = {"ok": False, "error": str(exc)}

    # Module 2 — Validation
    try:
        DocumentValidator()
        status["validation"] = {"ok": True, "checks": ["checksum", "qr_match", "expiry", "format"]}
    except Exception as exc:
        status["validation"] = {"ok": False, "error": str(exc)}

    # Module 3 — Tampering
    try:
        from modules.tampering_module import analyze_tampering
        status["tampering"] = {"ok": True, "signals": ["ELA", "FFT", "LBP_texture", "EXIF"]}
    except Exception as exc:
        status["tampering"] = {"ok": False, "error": str(exc)}

    # Module 4 — Face
    try:
        from modules.face_verification import MODEL_NAME, DETECTOR_BACKEND
        status["face"] = {"ok": True, "model": MODEL_NAME, "detector": DETECTOR_BACKEND}
    except Exception as exc:
        status["face"] = {"ok": False, "error": str(exc)}

    # Module 5 — Liveness
    try:
        from modules.liveness_module import analyze_liveness
        status["liveness"] = {"ok": True, "methods": ["EAR", "texture", "rPPG_proxy", "anti_spoof"]}
    except Exception as exc:
        status["liveness"] = {"ok": False, "error": str(exc)}

    # Module 6 — Identity graph
    try:
        stats = get_graph_stats()
        status["identity_graph"] = {"ok": True, **stats}
    except Exception as exc:
        status["identity_graph"] = {"ok": False, "error": str(exc)}

    # Module 7 — Risk engine
    try:
        from modules.risk_engine import run_risk_engine, RiskEngineInput
        smoke = run_risk_engine(RiskEngineInput(document_type="passport", ocr_confidence=90, face_similarity=80, blink_score=80))
        status["risk_engine"] = {"ok": True, "smoke_band": smoke.band.value}
    except Exception as exc:
        status["risk_engine"] = {"ok": False, "error": str(exc)}

    # Module 8 — Audit
    try:
        valid, broken = verify_chain_integrity()
        status["audit"] = {"ok": True, "chain_valid": valid, "broken_row": broken}
    except Exception as exc:
        status["audit"] = {"ok": False, "error": str(exc)}

    all_ok = all(m.get("ok") for m in status.values())
    return {"all_ok": all_ok, "modules": status}


@app.get("/audit-log")
async def audit_log(limit: int = 20):
    return get_recent_entries(limit=limit)
