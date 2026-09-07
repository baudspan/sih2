"""
fake_odometry.py — M2 Stub Data
Generates synthetic odometry data for testing predict() before M5 exists.
"""

import numpy as np


def generate_odometry(steps=20, dt=1.0, velocity=2.0, turn_rate=0.0):
    """
    Generate a list of odometry readings for testing.

    Args:
        steps: number of steps to simulate
        dt: time step (seconds)
        velocity: constant forward velocity (m/s)
        turn_rate: constant angular velocity (rad/s)

    Returns:
        list of dict: [{"velocity": float, "angular_velocity": float}, ...]
    """
    odometry_list = []
    for _ in range(steps):
        odometry_list.append({
            "velocity": velocity + np.random.normal(0, 0.05),  # add small noise
            "angular_velocity": turn_rate + np.random.normal(0, 0.01)
        })
    return odometry_list


if __name__ == "__main__":
    # Quick test
    odom = generate_odometry(10)
    print(f"Generated {len(odom)} odometry readings")
    print(f"First: {odom[0]}")
    print(f"Last: {odom[-1]}")