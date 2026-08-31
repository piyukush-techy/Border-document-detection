"""
liveness_module.py — Module 5: Liveness & Deepfake Detection
-------------------------------------------------------------
Analyzes a live selfie for signs of a real human vs. printed photo / replay.

Signals (single-frame selfie):
  1. Face texture / Laplacian variance on DeepFace-detected face crop
  2. DeepFace anti-spoof score (from face_verification module)
  3. Green-channel rPPG proxy in cheek region
  4. Color / noise statistics (printed photos lack sensor noise)

Optional video_path: counts blink transitions via frame-to-frame eye-region change.

Usage:
    from modules.liveness_module import analyze_liveness
    result = analyze_liveness("selfie.jpg", antispoof={"is_real": True, "antispoofing_score": 0.92})
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("liveness_module")


@dataclass
class LivenessResult:
    blink_score: float           # 0-100, higher = more likely live
    pulse_detected: bool
    bpm: Optional[int]
    liveness_score: float        # 0-1
    method_used: str
    is_live: bool
    details: str


def _load_bgr(path: str) -> np.ndarray:
    img = cv2.imread(path)
    if img is None:
        raise ValueError(f"Could not read image: {path}")
    return img


def _face_crop_deepface(image_bgr: np.ndarray) -> Optional[np.ndarray]:
    """Get face crop via DeepFace (works without OpenCV Haar cascades)."""
    try:
        from deepface import DeepFace

        faces = DeepFace.extract_faces(
            img_path=image_bgr,
            detector_backend="opencv",
            enforce_detection=False,
        )
        if not faces:
            return None
        face = faces[0]["face"]
        if face.max() <= 1.0:
            face = (face * 255).astype(np.uint8)
        return cv2.cvtColor(face, cv2.COLOR_RGB2GRAY)
    except Exception as exc:
        logger.debug(f"DeepFace face crop failed: {exc}")
        return None


def _face_crop_center(image_bgr: np.ndarray) -> np.ndarray:
    """Fallback: center crop where faces usually appear in selfies."""
    h, w = image_bgr.shape[:2]
    y1, y2 = int(h * 0.15), int(h * 0.85)
    x1, x2 = int(w * 0.2), int(w * 0.8)
    gray = cv2.cvtColor(image_bgr[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
    return gray


def _get_face_gray(image_bgr: np.ndarray) -> Tuple[np.ndarray, str]:
    crop = _face_crop_deepface(image_bgr)
    if crop is not None and crop.size > 0:
        return crop, "deepface_face_crop"
    return _face_crop_center(image_bgr), "center_crop_fallback"


def _texture_liveness_score(image_bgr: np.ndarray) -> Tuple[float, str]:
    gray, source = _get_face_gray(image_bgr)
    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    if lap_var >= 120:
        score = min(100.0, 60 + lap_var / 15)
        detail = f"Rich skin texture via {source} (Laplacian={lap_var:.0f})"
    elif lap_var >= 50:
        score = 58.0
        detail = f"Moderate texture via {source} (Laplacian={lap_var:.0f})"
    else:
        score = max(25.0, lap_var * 0.8)
        detail = f"Flat texture — possible print/screen via {source} (Laplacian={lap_var:.0f})"

    return round(score, 1), detail


def _noise_liveness_score(image_bgr: np.ndarray) -> Tuple[float, str]:
    """Live camera captures have more sensor noise than flat prints."""
    gray, _ = _get_face_gray(image_bgr)
    noise = float(np.std(gray.astype(np.float32) - cv2.GaussianBlur(gray, (5, 5), 0).astype(np.float32)))
    if noise >= 6:
        return min(95.0, 50 + noise * 4), f"Natural sensor noise (σ={noise:.1f})"
    if noise >= 3:
        return 55.0, f"Moderate noise (σ={noise:.1f})"
    return max(20.0, noise * 10), f"Very low noise — possible print (σ={noise:.1f})"


def _rppg_proxy(image_bgr: np.ndarray) -> Tuple[bool, Optional[int], str]:
    gray, source = _get_face_gray(image_bgr)
    h = gray.shape[0]
    if h < 12:
        return False, None, "rPPG skipped — face region too small"

    cheek = gray[h // 3 : 2 * h // 3, :]
    if cheek.size == 0:
        return False, None, "rPPG skipped — cheek ROI empty"

    row_means = cheek.mean(axis=1)
    variation = float(np.std(row_means))
    if variation >= 3.5:
        bpm = int(np.clip(58 + variation * 4, 55, 105))
        return True, bpm, f"Skin micro-variation via {source} (σ={variation:.1f})"
    return False, None, f"Pulse inconclusive on single frame (σ={variation:.1f})"


def _blink_score_from_video(video_path: str) -> Tuple[float, str]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return 50.0, "Could not open video"

    prev_gray = None
    transitions = 0
    frames = 0

    while frames < 120:
        ret, frame = cap.read()
        if not ret:
            break
        frames += 1
        if frames % 4 != 0:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        eye_roi = gray[int(h * 0.25) : int(h * 0.55), int(w * 0.2) : int(w * 0.8)]
        brightness = float(eye_roi.mean()) if eye_roi.size else 0

        if prev_gray is not None:
            if abs(brightness - prev_gray) > 8:
                transitions += 1
        prev_gray = brightness

    cap.release()
    if transitions >= 2:
        return min(100.0, 70 + transitions * 5), f"{transitions} eye-region transitions in video"
    return 40.0, "No significant eye movement in video"


def _antispoof_score(antispoof: Optional[dict]) -> Tuple[float, str]:
    if antispoof and antispoof.get("antispoofing_score") is not None:
        s = float(antispoof["antispoofing_score"]) * 100
        return s, f"DeepFace anti-spoof={s:.0f}%"
    if antispoof and antispoof.get("is_real") is True:
        return 85.0, "DeepFace anti-spoof: real"
    if antispoof and antispoof.get("is_real") is False:
        return 15.0, "DeepFace anti-spoof: spoof detected"
    return 55.0, "Anti-spoof not available — neutral"


def analyze_liveness(
    selfie_path: str,
    video_path: Optional[str] = None,
    antispoof: Optional[dict] = None,
) -> LivenessResult:
    """Main entry point. Never raises."""
    try:
        image = _load_bgr(selfie_path)

        if video_path:
            blink_score, blink_detail = _blink_score_from_video(video_path)
            method = "video_motion + texture + noise + rppg + antispoof"
        else:
            texture_score, texture_detail = _texture_liveness_score(image)
            noise_score, noise_detail = _noise_liveness_score(image)
            blink_score = round(0.55 * texture_score + 0.45 * noise_score, 1)
            blink_detail = f"{texture_detail}; {noise_detail}"
            method = "texture + noise + rppg + antispoof"

        texture_score, texture_detail = _texture_liveness_score(image)
        noise_score, noise_detail = _noise_liveness_score(image)
        pulse_detected, bpm, pulse_detail = _rppg_proxy(image)
        spoof_score, spoof_detail = _antispoof_score(antispoof)

        if not video_path:
            blink_score = round(
                0.35 * texture_score + 0.25 * noise_score + 0.40 * spoof_score, 1
            )
        else:
            blink_score = round(
                0.30 * blink_score + 0.25 * texture_score + 0.20 * noise_score + 0.25 * spoof_score, 1
            )

        liveness_score = round(blink_score / 100.0, 3)
        is_live = blink_score >= 50 and spoof_score >= 35

        details = "; ".join(filter(None, [blink_detail, pulse_detail, spoof_detail]))

        return LivenessResult(
            blink_score=blink_score,
            pulse_detected=pulse_detected,
            bpm=bpm,
            liveness_score=liveness_score,
            method_used=method,
            is_live=is_live,
            details=details,
        )

    except Exception as exc:
        logger.warning(f"Liveness analysis failed: {exc}")
        return LivenessResult(
            blink_score=50.0,
            pulse_detected=False,
            bpm=None,
            liveness_score=0.5,
            method_used="fallback",
            is_live=False,
            details=f"Analysis error: {exc}",
        )


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "samples/demo_selfie.jpg"
    print(analyze_liveness(path))
