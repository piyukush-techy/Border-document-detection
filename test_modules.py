#!/usr/bin/env python3
"""
test_modules.py — Run a smoke test on every pipeline module.
Usage:  python test_modules.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

PASS = 0
FAIL = 0


def check(name: str, fn):
    global PASS, FAIL
    try:
        fn()
        print(f"  [PASS] {name}")
        PASS += 1
    except Exception as exc:
        print(f"  [FAIL] {name}: {exc}")
        FAIL += 1


def main():
    doc = ROOT / "samples" / "demo_aadhaar.jpg"
    doc_face = ROOT / "samples" / "demo_passport_with_face.jpg"
    selfie = ROOT / "samples" / "demo_selfie.jpg"

    if not doc.exists():
        print("Run from project root. samples/ folder missing — create samples first.")
        sys.exit(1)

    print("\n=== Module 1: OCR ===")

    def test_ocr():
        from modules.ocr_module import process_document
        r = process_document(str(doc), doc_type="national_id")
        assert "fields" in r and "ocr_confidence" in r

    check("process_document", test_ocr)

    print("\n=== Module 2: Validation ===")

    def test_validation():
        import adapters
        from modules.ocr_module import process_document
        from modules.validation_module import DocumentValidator
        ocr = process_document(str(doc), doc_type="national_id")
        fields = adapters.ocr_fields_to_validation_fields(ocr, "national_id")
        result = DocumentValidator().run_all("national_id", fields, str(doc))
        assert "checks" in result and result["checks_run"] >= 0

    check("DocumentValidator.run_all", test_validation)

    print("\n=== Module 3: Tampering ===")

    def test_tampering():
        from modules.tampering_module import analyze_tampering
        r = analyze_tampering(str(doc))
        assert 0 <= r.tampering_score <= 100
        assert hasattr(r, "cnn_texture_score")

    check("analyze_tampering", test_tampering)

    print("\n=== Module 4: Face Verification ===")

    def test_face():
        if not doc_face.exists() or not selfie.exists():
            raise FileNotFoundError("face demo samples missing")
        from modules.face_verification import verify_face_with_cross_check
        r = verify_face_with_cross_check(str(doc_face), str(selfie))
        assert "primary" in r

    check("verify_face_with_cross_check", test_face)

    print("\n=== Module 5: Liveness ===")

    def test_liveness():
        if not selfie.exists():
            raise FileNotFoundError("selfie sample missing")
        from modules.liveness_module import analyze_liveness
        r = analyze_liveness(str(selfie))
        assert 0 <= r.blink_score <= 100
        assert r.method_used

    check("analyze_liveness", test_liveness)

    print("\n=== Module 6: Identity Graph ===")

    def test_identity():
        if not selfie.exists():
            raise FileNotFoundError("selfie sample missing")
        from modules.identity_graph_module import check_identity_reuse, get_graph_stats
        r = check_identity_reuse(str(selfie), id_number="TEST123", name="TEST USER")
        assert "flagged" in r
        stats = get_graph_stats()
        assert "nodes" in stats

    check("check_identity_reuse", test_identity)

    print("\n=== Module 7: Risk Engine ===")

    def test_risk():
        from modules.risk_engine import run_risk_engine, RiskEngineInput, RiskBand
        r = run_risk_engine(RiskEngineInput(
            document_type="national_id", ocr_confidence=85,
            checksum_valid=True, field_format_valid=True,
            tamper_ela=10, tamper_fft=8, tamper_cnn=5,
            face_similarity=75, blink_score=70, pulse_detected=False,
        ))
        assert r.band in (RiskBand.GREEN, RiskBand.YELLOW, RiskBand.RED)

    check("run_risk_engine", test_risk)

    print("\n=== Module 8: Audit Trail ===")

    def test_audit():
        from modules.audit_module import compute_document_hash, log_verification, verify_chain_integrity
        from types import SimpleNamespace
        h = compute_document_hash(str(doc))
        assert len(h) == 64
        dummy = SimpleNamespace(score=90, state="OK", detail="test")
        log_verification(h, dummy, dummy, dummy, dummy, 90, "GENUINE")
        valid, _ = verify_chain_integrity()
        assert valid is True

    check("audit chain", test_audit)

    print("\n=== Adapters + Full Pipeline ===")

    def test_adapters():
        import adapters as ad
        from modules.ocr_module import process_document
        from modules.validation_module import DocumentValidator
        from modules.tampering_module import analyze_tampering
        from modules.liveness_module import analyze_liveness
        from modules.risk_engine import run_risk_engine, RiskEngineInput

        ocr = process_document(str(doc), doc_type="national_id")
        vf = ad.ocr_fields_to_validation_fields(ocr, "national_id")
        val = DocumentValidator().run_all("national_id", vf, str(doc))
        tam = analyze_tampering(str(doc))
        liv = analyze_liveness(str(selfie))
        risk = run_risk_engine(RiskEngineInput(
            document_type="national_id",
            ocr_confidence=ocr["ocr_confidence"],
            **ad.validation_result_to_risk_fields(val, "national_id", ocr["ocr_confidence"]),
            **ad.tampering_result_to_risk_fields(tam),
            face_similarity=70, blink_score=liv.blink_score,
            pulse_detected=liv.pulse_detected, bpm=liv.bpm,
        ))
        assert risk.score is not None

    check("full adapter pipeline", test_adapters)

    print(f"\n{'='*40}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    print(f"{'='*40}\n")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
