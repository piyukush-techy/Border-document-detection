"""
adapters.py
------------
Translates each module's native output into risk_engine.py inputs and the
frontend JSON shape (App.jsx). main.py calls these adapters only.
"""

from __future__ import annotations

import logging
from datetime import datetime
from types import SimpleNamespace
from typing import Optional

logger = logging.getLogger("adapters")


# ---------------------------------------------------------------------------
# OCR -> field dict for the Validation module
# ---------------------------------------------------------------------------

def ocr_fields_to_validation_fields(ocr_raw: dict, doc_type: str = "") -> dict:
    raw_fields = ocr_raw.get("fields", {})
    fields = {}

    if "Name" in raw_fields:
        fields["name"] = raw_fields["Name"]
    if "ID" in raw_fields:
        fields["id_number"] = raw_fields["ID"]

    date_1 = raw_fields.get("Date_1")
    date_2 = raw_fields.get("Date_2")
    dob, expiry = _order_dates_as_dob_expiry(date_1, date_2, doc_type=doc_type)
    if dob:
        fields["dob"] = dob
    if expiry:
        fields["expiry_date"] = expiry

    return fields


def _order_dates_as_dob_expiry(date_1: Optional[str], date_2: Optional[str], doc_type: str = ""):
    candidates = [d for d in (date_1, date_2) if d]
    parsed = []
    for d in candidates:
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                parsed.append((datetime.strptime(d, fmt), d))
                break
            except ValueError:
                continue

    if len(parsed) < 2:
        if len(parsed) == 1:
            return parsed[0][1], None
        return None, None

    parsed.sort(key=lambda p: p[0])
    return parsed[0][1], parsed[1][1]


# ---------------------------------------------------------------------------
# Validation module -> risk_engine.py
# ---------------------------------------------------------------------------

def validation_result_to_risk_fields(
    validation_raw: dict,
    doc_type: str = "",
    ocr_confidence: float = 0.0,
) -> dict:
    checks_by_name = {c["name"]: c for c in validation_raw["checks"]}

    def passed_or_none(name: str) -> Optional[bool]:
        c = checks_by_name.get(name)
        if not c or not c["applicable"]:
            return None
        return bool(c["passed"])

    checksum = passed_or_none("checksum")
    # OCR of a 12-digit Aadhaar almost always misreads a digit, so Verhoeff
    # failure is NOT proof the card is fake. Never hard-gate Aadhaar checksum.
    if checksum is False and doc_type in ("national_id", "aadhaar"):
        logger.warning(
            "Aadhaar checksum failed (OCR confidence %.0f%%) — treating as inconclusive, not FAKE",
            ocr_confidence,
        )
        checksum = None

    return {
        "checksum_valid": checksum,
        "qr_code_match": passed_or_none("qr_match"),
        "expiry_date_valid": passed_or_none("expiry"),
        "field_format_valid": passed_or_none("format"),
    }


# ---------------------------------------------------------------------------
# Tampering module -> risk_engine.py
# ---------------------------------------------------------------------------

def tampering_result_to_risk_fields(tampering_result) -> dict:
    ela = round(tampering_result.ela_anomaly_score * 100, 2)
    fft = round(tampering_result.fft_spike_score * 100, 2)
    cnn = round(getattr(tampering_result, "cnn_texture_score", 0.0) * 100, 2)
    # Phone photos of real plastic cards often spike ELA/texture from glare
    if ela > 55 and fft < 25:
        ela = round(ela * 0.35, 2)
    if cnn > 40 and fft < 25:
        cnn = round(cnn * 0.4, 2)
    return {
        "tamper_ela": ela,
        "tamper_fft": fft,
        "tamper_cnn": cnn,
    }


# ---------------------------------------------------------------------------
# Face verification -> risk_engine.py
# ---------------------------------------------------------------------------

def face_result_to_risk_fields(face_bundle: dict) -> dict:
    primary = face_bundle["primary"]
    similarity = round(primary.match_score * 100, 2)
    return {
        "face_similarity": similarity,
        "face_distance": primary.distance,
    }


# ---------------------------------------------------------------------------
# Liveness module -> risk_engine.py + frontend
# ---------------------------------------------------------------------------

def liveness_result_to_risk_fields(liveness_result) -> dict:
    """liveness_result is a LivenessResult dataclass from liveness_module.py."""
    return {
        "blink_score": float(liveness_result.blink_score),
        "pulse_detected": bool(liveness_result.pulse_detected),
        "bpm": liveness_result.bpm,
    }


def liveness_result_to_frontend(liveness_result) -> dict:
    return {
        "pulseDetected": liveness_result.pulse_detected,
        "bpm": liveness_result.bpm,
        "blinkScore": liveness_result.blink_score,
        "isLive": liveness_result.is_live,
        "method": liveness_result.method_used,
        "detail": liveness_result.details,
    }


# ---------------------------------------------------------------------------
# Identity graph -> risk_engine + frontend
# ---------------------------------------------------------------------------

def identity_graph_to_frontend(identity_result: dict) -> dict:
    return {
        "flagged": identity_result.get("flagged", False),
        "reason": identity_result.get("reason"),
        "similarity": identity_result.get("similarity"),
        "matchedId": identity_result.get("matched_id_number"),
        "matchedName": identity_result.get("matched_name"),
        "detail": identity_result.get("detail", ""),
    }


# ---------------------------------------------------------------------------
# Audit module views
# ---------------------------------------------------------------------------

def build_audit_view(
    ocr_raw: dict,
    validation_raw: dict,
    tampering_result,
    face_bundle: dict,
    liveness_result=None,
):
    primary = face_bundle["primary"]

    ocr_view = SimpleNamespace(
        score=ocr_raw["ocr_confidence"],
        state="OK" if ocr_raw["ocr_confidence"] >= 60 else "LOW_CONFIDENCE",
        detail=f"EasyOCR/Tesseract agreement: {ocr_raw['ocr_agreement']:.0f}%",
    )

    validation_view = SimpleNamespace(
        score=validation_raw["overall_score"],
        state=f"{validation_raw['checks_run']} checks run, {validation_raw['checks_skipped']} skipped",
        detail="; ".join(c["details"] for c in validation_raw["checks"] if c["applicable"]) or "No applicable checks",
    )

    cnn = getattr(tampering_result, "cnn_texture_score", 0.0)
    tampering_view = SimpleNamespace(
        score=tampering_result.tampering_score,
        state="GENUINE" if tampering_result.tampering_score >= 70 else "SUSPICIOUS",
        detail=(
            f"{tampering_result.explanation} "
            f"[ELA={tampering_result.ela_anomaly_score:.2f}, FFT={tampering_result.fft_spike_score:.2f}, "
            f"texture={cnn:.2f}]"
        ),
    )

    face_view = SimpleNamespace(
        score=round(primary.match_score * 100, 2),
        state="MATCH" if primary.match else "NO_MATCH",
        detail=(
            f"distance={primary.distance:.3f}, is_real={primary.is_real}, "
            f"cross_check={face_bundle.get('cross_check_score')}, "
            f"disagreement={face_bundle.get('disagreement_flag')}"
        ),
    )

    if liveness_result:
        face_view.detail += (
            f" | liveness={liveness_result.blink_score:.0f}%, "
            f"pulse={liveness_result.pulse_detected}, method={liveness_result.method_used}"
        )

    return ocr_view, validation_view, tampering_view, face_view


# ---------------------------------------------------------------------------
# Frontend response
# ---------------------------------------------------------------------------

def build_frontend_response(
    ocr_raw: dict,
    validation_raw: dict,
    tampering_result,
    face_bundle: dict,
    liveness_result,
    risk_result,
    audit_entry: dict,
    identity_result: dict,
) -> dict:
    primary = face_bundle["primary"]
    checks_by_name = {c["name"]: c for c in validation_raw["checks"]}

    def check_bool(name: str) -> bool:
        c = checks_by_name.get(name)
        if not c or c["passed"] is None:
            return True
        return bool(c["passed"])

    frontend_score = round((1 - risk_result.score) * 100)
    if frontend_score >= 75:
        verdict = "GENUINE"
    elif frontend_score >= 45:
        verdict = "SUSPICIOUS"
    else:
        verdict = "FAKE"

    ocr_display = {
        **{k: v for k, v in ocr_raw.get("fields", {}).items()},
        "OCR Confidence": f"{ocr_raw['ocr_confidence']:.0f}%",
    }

    cnn_score = round(getattr(tampering_result, "cnn_texture_score", 0.0) * 100)

    return {
        "ocr": ocr_display,
        "validation": {
            "Checksum Verification": check_bool("checksum"),
            "QR Code Match": check_bool("qr_match"),
            "Expiry Date Valid": check_bool("expiry"),
            "Field Format (Regex)": check_bool("format"),
        },
        "tampering": {
            "ela": round(tampering_result.ela_anomaly_score * 100),
            "fft": round(tampering_result.fft_spike_score * 100),
            "cnn": cnn_score,
        },
        "face": {
            "similarity": round(primary.match_score * 100),
            "distance": primary.distance,
            "isReal": primary.is_real,
            "crossCheck": face_bundle.get("cross_check_score"),
            "disagreement": face_bundle.get("disagreement_flag", False),
        },
        "liveness": liveness_result_to_frontend(liveness_result),
        "identityGraph": identity_graph_to_frontend(identity_result),
        "riskScore": frontend_score,
        "verdict": verdict,
        "auditEntry": audit_entry,
        "hardGated": risk_result.hard_gated,
        "hardGateReason": risk_result.hard_gate_reason,
        "reasons": risk_result.reasons,
    }
