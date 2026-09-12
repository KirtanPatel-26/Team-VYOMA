import numpy as np
import pytest
from app.detection.privacy import PrivacyAnonymizer

def test_privacy_anonymizer_face_blur():
    anonymizer = PrivacyAnonymizer()
    frame = np.full((720, 1280, 3), 120, dtype=np.uint8)
    # Put a distinct pattern in the face region
    frame[50:120, 100:200] = 255

    person_boxes = [(80, 50, 220, 350)]
    anonymized = anonymizer.apply_face_blur(frame, person_boxes)

    assert anonymized is not None
    assert anonymized.shape == frame.shape
    # Face region should be modified/blurred
    assert not np.array_equal(frame[50:120, 100:200], anonymized[50:120, 100:200])

def test_privacy_mode_toggle_and_silhouette():
    anonymizer = PrivacyAnonymizer()
    assert anonymizer.privacy_mode_enabled is False

    anonymizer.toggle_privacy_mode(True)
    assert anonymizer.privacy_mode_enabled is True

    frame = np.full((720, 1280, 3), 150, dtype=np.uint8)
    person_boxes = [(100, 100, 200, 400)]
    out = anonymizer.process_frame(frame, person_boxes)

    assert out is not None
    assert out.shape == frame.shape
    # Background should be dark canvas in privacy silhouette mode
    assert out[10, 10, 0] <= 35
