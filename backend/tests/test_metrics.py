import numpy as np

from app.pipeline.metrics import expected_calibration_error


def test_ece_bounds() -> None:
    y_true = np.array([0, 0, 1, 1])
    y_prob = np.array([0.1, 0.2, 0.8, 0.9])
    ece = expected_calibration_error(y_true, y_prob, bins=5)
    assert 0 <= ece <= 1
