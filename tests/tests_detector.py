import cv2
import numpy as np

from src.perception.detector import detect_craters


def create_test_depth_map():
    rng = np.random.default_rng(42)

    height, width = 600, 600

    y, x = np.mgrid[0:height, 0:width]

    # Sloped terrain
    terrain = (
        1000.0
        + 0.35 * x
        + 0.20 * y
    )

    # Natural-looking terrain roughness
    roughness = (
        12.0 * np.sin(x / 25.0)
        + 8.0 * np.sin(y / 31.0)
        + 5.0 * np.sin((x + y) / 18.0)
    )

    depth_map = terrain + roughness

    # --------------------------------------------------
    # REAL CRATERS
    # --------------------------------------------------

    real_craters = [
        (150, 180, 45, 300.0),
        (380, 200, 60, 300.0),
        (300, 420, 35, 300.0),

        # Harder craters
        (100, 100, 20, 180.0),
        (500, 480, 80, 220.0),
    ]

    for x0, y0, radius, depth in real_craters:

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

        depth_map[inner_mask > 0] -= depth
        depth_map[rim_mask > 0] += 80.0

    # --------------------------------------------------
    # FALSE POSITIVE 1: ELONGATED DEPRESSION
    # --------------------------------------------------

    elongated = np.zeros(
        (height, width),
        dtype=np.uint8,
    )

    cv2.ellipse(
        elongated,
        (120, 400),
        (70, 20),
        25,
        0,
        360,
        255,
        -1,
    )

    depth_map[elongated > 0] -= 180.0

    # --------------------------------------------------
    # FALSE POSITIVE 2: IRREGULAR TERRAIN BUMP
    # --------------------------------------------------

    irregular = np.zeros(
        (height, width),
        dtype=np.uint8,
    )

    points = np.array(
        [
            [430, 380],
            [475, 350],
            [510, 370],
            [500, 420],
            [450, 440],
            [420, 410],
        ],
        dtype=np.int32,
    )

    cv2.fillPoly(
        irregular,
        [points],
        255,
    )

    depth_map[irregular > 0] += 160.0

    # --------------------------------------------------
    # FALSE POSITIVE 3: CIRCULAR-ISH SHALLOW FEATURE
    # --------------------------------------------------

    # FALSE POSITIVE 3: SHALLOW CIRCULAR FEATURES

    shallow_features = [
        (470, 130, 42, 30.0),
        (500, 250, 38, 60.0),
        (120, 500, 45, 90.0),
    ]

    for x0, y0, radius, depth in shallow_features:
        shallow_feature = np.zeros(
            (height, width),
            dtype=np.uint8,
        )

        cv2.circle(
            shallow_feature,
            (x0, y0),
            radius,
            255,
            -1,
        )

        depth_map[shallow_feature > 0] -= depth
    # FALSE POSITIVE 4: IRREGULAR SHALLOW DEPRESSION

    irregular_depression = np.zeros(
        (height, width),
        dtype=np.uint8,
    )

    points = np.array(
        [
            [350, 480],
            [390, 455],
            [430, 470],
            [445, 510],
            [410, 535],
            [365, 520],
        ],
        dtype=np.int32,
    )

    cv2.fillPoly(
        irregular_depression,
        [points],
        255,
    )

    depth_map[irregular_depression > 0] -= 120.0

    # FALSE POSITIVE 5: ELONGATED RIDGE

    ridge = np.zeros(
        (height, width),
        dtype=np.uint8,
    )

    cv2.ellipse(
        ridge,
        (200, 320),
        (80, 15),
        -20,
        0,
        360,
        255,
        -1,
    )

    depth_map[ridge > 0] += 100.0
    # --------------------------------------------------
    # SENSOR NOISE
    # --------------------------------------------------

    noise = rng.normal(
        0,
        25,
        (height, width),
    ).astype(np.float32)

    depth_map += noise

    return depth_map

def main():
    depth_map = create_test_depth_map()

    detections = detect_craters(depth_map)

    print("\nDetected craters:")
    for crater in detections:
        print(crater)

    display = cv2.normalize(
        depth_map,
        None,
        0,
        255,
        cv2.NORM_MINMAX,
    ).astype(np.uint8)

    display = cv2.cvtColor(
        display,
        cv2.COLOR_GRAY2BGR,
    )

    for crater in detections:
        x = crater["x"]
        y = crater["y"]
        radius = crater["radius"]

        cv2.circle(
            display,
            (x, y),
            radius,
            (0, 255, 0),
            2,
        )

        cv2.circle(
            display,
            (x, y),
            3,
            (0, 0, 255),
            -1,
        )

    cv2.imwrite(
        "tests/detection_result.png",
        display,
    )

    print("\nSaved: tests/detection_result.png")


if __name__ == "__main__":
    main()