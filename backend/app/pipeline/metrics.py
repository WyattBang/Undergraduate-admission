from __future__ import annotations

import numpy as np
from sklearn.metrics import brier_score_loss, roc_auc_score


def expected_calibration_error(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    bins: int = 10,
) -> float:
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)

    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0

    for idx in range(bins):
        left = edges[idx]
        right = edges[idx + 1]
        in_bin = (y_prob >= left) & (y_prob < right if idx < bins - 1 else y_prob <= right)
        if in_bin.sum() == 0:
            continue
        avg_conf = float(y_prob[in_bin].mean())
        avg_acc = float(y_true[in_bin].mean())
        ece += abs(avg_acc - avg_conf) * float(in_bin.mean())
    return float(ece)


def summarize_binary_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> dict[str, float]:
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)

    auc = 0.5
    if len(np.unique(y_true)) > 1:
        auc = float(roc_auc_score(y_true, y_prob))

    brier = float(brier_score_loss(y_true, y_prob))
    ece = expected_calibration_error(y_true, y_prob, bins=10)
    return {"auc": auc, "brier": brier, "ece": ece}
