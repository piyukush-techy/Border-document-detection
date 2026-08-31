"""
Shared data models for the pipeline.
Every module returns one of these so main.py can combine them without
caring about each module's internals.

Note: Some modules define their own result types locally to remain self-contained.
This file serves as documentation and optional validation when needed.
"""

from pydantic import BaseModel
from typing import Optional


class OCRResult(BaseModel):
    fields: dict            # e.g. {"name": "...", "dob": "...", "id_number": "..."}
    avg_confidence: float   # 0-1, averaged across fields


class ValidationResult(BaseModel):
    checksum_ok: bool
    qr_matches_text: bool
    format_ok: bool
    not_expired: bool
    score: float            # 0-1, rolled up from the 4 checks above


class TamperingResult(BaseModel):
    ela_score: float        # 0-1, higher = more suspicious
    fft_spike_score: float  # 0-1, higher = more suspicious (structured/grid-like)
    tampering_score: float  # 0-1 combined, higher = more suspicious


class LivenessResult(BaseModel):
    blink_score: float           # 0-100, higher = more likely live
    pulse_detected: bool
    bpm: Optional[int]
    liveness_score: float        # 0-1
    method_used: str
    is_live: bool
    details: str


class RiskVerdict(BaseModel):
    risk_score: float        # 0-100
    verdict: str              # GENUINE / SUSPICIOUS / FAKE
    breakdown: dict           # per-module contribution, for the officer UI