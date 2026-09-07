from .path_metrics import compute_path_metrics


def _metric_reason(label, chosen_value, rejected_value, lower_is_better=True):
    difference = rejected_value - chosen_value
    magnitude = abs(difference)

    if difference == 0:
        return (
            f"{label} was equal "
            f"(chosen {chosen_value:.2f}, rejected {rejected_value:.2f})"
        )

    chosen_is_better = difference > 0 if lower_is_better else difference < 0
    direction = "lower" if difference > 0 else "higher"
    preference = "favored" if chosen_is_better else "penalized"

    return (
        f"{label} {direction} by {magnitude:.2f} "
        f"(chosen {chosen_value:.2f}, rejected {rejected_value:.2f}), "
        f"which {preference} Path A"
    )


def generate_contrastive_explanation(
    path_a,
    path_b,
    covariance_a,
    covariance_b
):
    """
    Compare two candidate paths and explain why Path A
    is preferred over Path B.
    """

    metrics_a = compute_path_metrics(path_a, covariance_a)
    metrics_b = compute_path_metrics(path_b, covariance_b)

    reasons = [
        _metric_reason(
            "Slip Risk",
            metrics_a["slip_risk"],
            metrics_b["slip_risk"],
        ),
        _metric_reason(
            "Crater Covariance",
            metrics_a["crater_covariance"],
            metrics_b["crater_covariance"],
        ),
        _metric_reason(
            "Energy Proxy",
            metrics_a["energy_proxy"],
            metrics_b["energy_proxy"],
        ),
    ]

    explanation = "Chose Path A over Path B because: " + ", ".join(reasons)

    return {
        "chosen_path": "A",
        "rejected_path": "B",
        "metrics_a": metrics_a,
        "metrics_b": metrics_b,
        "explanation": explanation,
    }
