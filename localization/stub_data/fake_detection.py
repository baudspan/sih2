"""
fake_detection.py — M2 Stub Data
Generates synthetic crater detections for testing correct() before M3 exists.
"""

import numpy as np
import sys
import os

# Add parent directory to path to import localizer
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ..crater_loader import load_craters


def generate_detections(num_craters=5, noise_std=10.0, use_real_craters=True):
    """
    Generate synthetic crater detections for testing.

    Args:
        num_craters: number of craters to generate
        noise_std: standard deviation of noise to add (meters)
        use_real_craters: if True, use real crater positions from DB

    Returns:
        list of dict: [{"x": float, "y": float, "radius": float, "confidence": float}, ...]
    """
    if use_real_craters:
        # Load real craters from DB
        craters = load_craters()
        if len(craters) < num_craters:
            num_craters = len(craters)
        
        # Select random craters
        indices = np.random.choice(len(craters), num_craters, replace=False)
        selected = [craters[i] for i in indices]
        
        detections = []
        for c in selected:
            noise_x = np.random.normal(0, noise_std)
            noise_y = np.random.normal(0, noise_std)
            detections.append({
                "x": c["x"] + noise_x,
                "y": c["y"] + noise_y,
                "radius": c["diameter"] / 2.0 + np.random.normal(0, 5.0),
                "confidence": np.random.uniform(0.7, 0.95)
            })
        return detections
    else:
        # Fallback: generate random craters (for testing failure cases)
        detections = []
        for _ in range(num_craters):
            detections.append({
                "x": np.random.uniform(-1000, 1000),
                "y": np.random.uniform(-1000, 1000),
                "radius": np.random.uniform(10, 100),
                "confidence": np.random.uniform(0.5, 0.9)
            })
        return detections


if __name__ == "__main__":
    # Quick test
    detections = generate_detections(5, use_real_craters=True)
    print(f"Generated {len(detections)} crater detections:")
    for i, d in enumerate(detections):
        print(f"  [{i+1}] x={d['x']:.2f}m, y={d['y']:.2f}m, radius={d['radius']:.2f}m, conf={d['confidence']:.2f}")