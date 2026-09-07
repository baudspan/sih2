import cv2
import numpy as np


def detect_craters(depth_map: np.ndarray) -> list[dict]:
    if not isinstance(depth_map, np.ndarray):
        raise TypeError("depth_map must be a NumPy array")

    if depth_map.ndim != 2:
        raise ValueError("depth_map must be a 2D array")

    if depth_map.size == 0:
        return []

    depth = depth_map.astype(np.float32)

    normalized = cv2.normalize(
        depth,
        None,
        0,
        255,
        cv2.NORM_MINMAX,
    ).astype(np.uint8)

    blurred = cv2.GaussianBlur(
        normalized,
        (9, 9),
        2,
    )

    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=12,
        param1=100,
        param2=18,
        minRadius=2,
        maxRadius=20,
    )

    if circles is None:
        return []

    detections = []

    for circle in np.round(circles[0]).astype(int):
        x, y, radius = circle

        if (
            x - radius < 0
            or y - radius < 0
            or x + radius >= depth.shape[1]
            or y + radius >= depth.shape[0]
        ):
            continue

        confidence = _calculate_confidence(
            depth,
            x,
            y,
            radius,
        )

        if confidence < 0.30:
            continue

        detections.append(
            {
                "x": int(x),
                "y": int(y),
                "radius": int(radius),
                "confidence": round(float(confidence), 3),
            }
        )

    detections.sort(
        key=lambda crater: crater["confidence"],
        reverse=True,
    )

    return detections


def _calculate_confidence(
    depth: np.ndarray,
    x: int,
    y: int,
    radius: int,
) -> float:
    inner_mask = np.zeros(
        depth.shape,
        dtype=np.uint8,
    )

    rim_mask = np.zeros(
        depth.shape,
        dtype=np.uint8,
    )

    outer_mask = np.zeros(
        depth.shape,
        dtype=np.uint8,
    )

    inner_radius = max(
        2,
        int(radius * 0.55),
    )

    rim_inner_radius = max(
        inner_radius + 1,
        int(radius * 0.85),
    )

    rim_outer_radius = max(
        rim_inner_radius + 1,
        int(radius * 1.05),
    )

    outer_radius = max(
        rim_outer_radius + 2,
        int(radius * 1.50),
    )

    cv2.circle(
        inner_mask,
        (x, y),
        inner_radius,
        255,
        -1,
    )

    cv2.circle(
        rim_mask,
        (x, y),
        rim_outer_radius,
        255,
        -1,
    )

    cv2.circle(
        rim_mask,
        (x, y),
        rim_inner_radius,
        0,
        -1,
    )

    cv2.circle(
        outer_mask,
        (x, y),
        outer_radius,
        255,
        -1,
    )

    cv2.circle(
        outer_mask,
        (x, y),
        rim_outer_radius,
        0,
        -1,
    )

    inner_mean = cv2.mean(
        depth,
        mask=inner_mask,
    )[0]

    rim_mean = cv2.mean(
        depth,
        mask=rim_mask,
    )[0]

    outer_mean = cv2.mean(
        depth,
        mask=outer_mask,
    )[0]

    if outer_mean <= inner_mean:
        depression_score = 0.0
    else:
        depression_strength = (
            outer_mean - inner_mean
        )

        depression_score = min(
            1.0,
            depression_strength / 300.0,
        )

    expected_rim_level = (
        inner_mean + outer_mean
    ) / 2.0

    rim_strength = (
        rim_mean - expected_rim_level
    )

    if rim_strength <= 0:
        rim_score = 0.0
    else:
        rim_score = min(
            1.0,
            rim_strength / 100.0,
        )

    contrast_strength = abs(
        outer_mean - inner_mean
    )

    contrast_score = min(
        1.0,
        contrast_strength / 300.0,
    )

    confidence = (
        0.55 * depression_score
        + 0.30 * rim_score
        + 0.15 * contrast_score
    )

    return float(confidence)