import cv2
import numpy as np

from src.perception.detector import detect_craters


def match_detections(
    ground_truth: list[dict],
    detections: list[dict],
    center_tolerance: float = 10.0,
    radius_tolerance: float = 10.0,
) -> tuple[int, int, int, list[float], list[float]]:
    matched = set()

    true_positives = 0
    false_negatives = 0
    center_errors = []
    radius_errors = []

    for actual in ground_truth:
        best_index = None
        best_distance = float("inf")

        for index, detected in enumerate(detections):
            if index in matched:
                continue

            center_distance = np.hypot(
                detected["x"] - actual["x"],
                detected["y"] - actual["y"],
            )

            radius_error = abs(
                detected["radius"] - actual["radius"]
            )

            if (
                center_distance <= center_tolerance
                and radius_error <= radius_tolerance
                and center_distance < best_distance
            ):
                best_index = index
                best_distance = center_distance

        if best_index is not None:
            matched.add(best_index)
            true_positives += 1

            detected = detections[best_index]

            center_errors.append(best_distance)
            radius_errors.append(
                abs(
                    detected["radius"]
                    - actual["radius"]
                )
            )
        else:
            false_negatives += 1

    false_positives = len(detections) - len(matched)

    return (
        true_positives,
        false_positives,
        false_negatives,
        center_errors,
        radius_errors,
    )


def create_evaluation_depth_map():
    rng = np.random.default_rng(42)

    height = 600
    width = 600

    y, x = np.mgrid[0:height, 0:width]

    terrain = (
        1000.0
        + 0.35 * x
        + 0.20 * y
    )

    roughness = (
        12.0 * np.sin(x / 25.0)
        + 8.0 * np.sin(y / 31.0)
        + 5.0 * np.sin((x + y) / 18.0)
    )

    depth_map = terrain + roughness

    ground_truth = [
        {"x": 150, "y": 180, "radius": 45},
        {"x": 380, "y": 200, "radius": 60},
        {"x": 300, "y": 420, "radius": 35},
        {"x": 100, "y": 100, "radius": 20},
        {"x": 500, "y": 480, "radius": 80},
    ]

    for crater in ground_truth:
        x0 = crater["x"]
        y0 = crater["y"]
        radius = crater["radius"]

        inner_mask = np.zeros(
            (height, width),
            dtype=np.uint8,
        )

        rim_mask = np.zeros(
            (height, width),
            dtype=np.uint8,
        )

        cv2.circle(
            inner_mask,
            (x0, y0),
            radius,
            255,
            -1,
        )

        cv2.circle(
            rim_mask,
            (x0, y0),
            radius,
            255,
            3,
        )

        depth_map[inner_mask > 0] -= 300.0
        depth_map[rim_mask > 0] += 80.0

    noise = rng.normal(
        0,
        25,
        (height, width),
    ).astype(np.float32)

    depth_map += noise

    return depth_map, ground_truth


def test_crater_detection_metrics():
    depth_map, ground_truth = (
        create_evaluation_depth_map()
    )

    detections = detect_craters(depth_map)

    (
        true_positives,
        false_positives,
        false_negatives,
        center_errors,
        radius_errors,
    ) = match_detections(
        ground_truth,
        detections,
    )

    total_detected = len(detections)

    precision = (
        true_positives / total_detected
        if total_detected
        else 0.0
    )

    recall = (
        true_positives / len(ground_truth)
        if ground_truth
        else 0.0
    )

    mean_center_error = (
        np.mean(center_errors)
        if center_errors
        else 0.0
    )

    mean_radius_error = (
        np.mean(radius_errors)
        if radius_errors
        else 0.0
    )

    print()
    print("Crater Detection Evaluation")
    print("----------------------------")
    print(f"Ground truth:       {len(ground_truth)}")
    print(f"Detected:           {total_detected}")
    print(f"True positives:     {true_positives}")
    print(f"False positives:    {false_positives}")
    print(f"False negatives:    {false_negatives}")
    print(f"Precision:          {precision:.3f}")
    print(f"Recall:             {recall:.3f}")
    print(
        f"Mean center error:  "
        f"{mean_center_error:.2f} px"
    )
    print(
        f"Mean radius error:  "
        f"{mean_radius_error:.2f} px"
    )

    assert recall >= 0.80