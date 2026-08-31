"""
Modules package for the AI-Based Fake Identity & Document Screening System.

This package contains 8 independent modules that work together to detect fake documents:
1. OCR Module - Text extraction using EasyOCR and Tesseract
2. Validation Module - Document validation (checksums, QR codes, expiry, format)
3. Tampering Module - Image tampering detection (ELA, FFT, LBP texture, EXIF)
4. Face Verification Module - Face matching using DeepFace and dlib
5. Liveness Module - Liveness detection (blink, texture, rPPG, anti-spoof)
6. Identity Graph Module - Cross-document identity reuse detection
7. Risk Engine - Risk scoring and fusion logic
8. Audit Module - Hash-chained audit trail logging
"""

from .ocr_module import process_document
from .validation_module import DocumentValidator
from .tampering_module import analyze_tampering
from .face_verification import verify_face_with_cross_check
from .liveness_module import analyze_liveness
from .identity_graph_module import check_identity_reuse, get_graph_stats
from .risk_engine import run_risk_engine, RiskEngineInput
from .audit_module import compute_document_hash, log_verification, get_recent_entries, verify_chain_integrity

__all__ = [
    'process_document',
    'DocumentValidator',
    'analyze_tampering',
    'verify_face_with_cross_check',
    'analyze_liveness',
    'check_identity_reuse',
    'get_graph_stats',
    'run_risk_engine',
    'RiskEngineInput',
    'compute_document_hash',
    'log_verification',
    'get_recent_entries',
    'verify_chain_integrity',
]