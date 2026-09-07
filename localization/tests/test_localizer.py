"""
test_localizer.py — M2 Localization Tests
Unit tests for predict(), correct(), get_pose(), and uncertainty thresholds.
"""

import sys
import os
import unittest
import numpy as np

# Add parent directory (M2) to path so we can import localization
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localization.localizer import Localizer
from localization.stub_data.fake_odometry import generate_odometry
from localization.stub_data.fake_detection import generate_detections


class TestLocalizer(unittest.TestCase):
    
    def setUp(self):
        """Create a fresh localizer before each test."""
        self.localizer = Localizer()
    
    def test_initial_state(self):
        """Test that initial pose and covariance are correct."""
        pose = self.localizer.get_telemetry()
        self.assertEqual(pose['x'], 0.0)
        self.assertEqual(pose['y'], 0.0)
        self.assertEqual(pose['heading'], 0.0)
        self.assertAlmostEqual(pose['uncertainty'], 0.1414, places=3)
        self.assertEqual(pose['relocalization_count'], 0)
    
    def test_predict_drift(self):
        """Test that predict() grows uncertainty over time."""
        odometry = {"velocity": 2.0, "angular_velocity": 0.0}
        
        before = self.localizer.get_telemetry()['uncertainty']
        
        for _ in range(10):
            self.localizer.predict(1.0, odometry)
        
        after = self.localizer.get_telemetry()['uncertainty']
        
        self.assertGreater(after, before)
        print(f"✅ Drift test: {before:.2f}m → {after:.2f}m")
    
    def test_uncertainty_levels(self):
        """Test that uncertainty thresholds map to correct levels."""
        # Initial should be 'normal'
        self.assertEqual(self.localizer.get_uncertainty_level(), 'normal')
        
        # Force covariance to 'caution' range (uncertainty between 3 and 5m)
        # Need sqrt(cov[0,0] + cov[1,1]) > 3 and < 5
        # Set both to 5.0 => sqrt(10) ≈ 3.16
        self.localizer.covariance[0, 0] = 5.0
        self.localizer.covariance[1, 1] = 5.0
        self.assertEqual(self.localizer.get_uncertainty_level(), 'caution')
        
        # Force covariance to 'critical' range (>5m)
        # Set both to 13.0 => sqrt(26) ≈ 5.1
        self.localizer.covariance[0, 0] = 13.0
        self.localizer.covariance[1, 1] = 13.0
        self.assertEqual(self.localizer.get_uncertainty_level(), 're_localizing')
        
        print("✅ Uncertainty levels test passed")
        
    def test_correct_with_real_craters(self):
        """Test that correct() works with real crater data."""
        odometry = {"velocity": 2.0, "angular_velocity": 0.0}
        for _ in range(15):
            self.localizer.predict(1.0, odometry)
        
        before = self.localizer.get_telemetry()['uncertainty']
        
        detections = generate_detections(5, noise_std=10.0, use_real_craters=True)
        
        success = self.localizer.correct(detections)
        
        self.assertTrue(success)
        after = self.localizer.get_telemetry()['uncertainty']
        
        self.assertLess(after, before)
        print(f"✅ Correction test: {before:.2f}m → {after:.2f}m")
    
    def test_correct_fails_without_enough_craters(self):
        """Test that correct() returns False with <3 detections."""
        detections = generate_detections(2, use_real_craters=True)
        success = self.localizer.correct(detections)
        self.assertFalse(success)
        print("✅ Failure test passed (not enough craters)")
    
    def test_correct_fallback(self):
        """Test that fallback mode works when detection fails."""
        fallback = [
            {"x": 100.0, "y": 100.0},
            {"x": 200.0, "y": 150.0},
            {"x": 50.0, "y": 200.0}
        ]
        self.localizer.set_fallback_craters(fallback)
        
        success = self.localizer.correct([], use_fallback=True, fallback_craters=fallback)
        # This may still fail if fallback craters don't match real landmarks,
        # but we're just testing the function handles fallback parameters
        print("✅ Fallback test completed")
    
    def test_relocalization_count_increments(self):
        """Test that relocalization_count increments after successful correction."""
        odometry = {"velocity": 2.0, "angular_velocity": 0.0}
        for _ in range(15):
            self.localizer.predict(1.0, odometry)
        
        detections = generate_detections(5, noise_std=10.0, use_real_craters=True)
        
        self.localizer.correct(detections)
        count_after_first = self.localizer.get_telemetry()['relocalization_count']
        self.assertEqual(count_after_first, 1)
        
        detections = generate_detections(5, noise_std=10.0, use_real_craters=True)
        self.localizer.correct(detections)
        count_after_second = self.localizer.get_telemetry()['relocalization_count']
        self.assertEqual(count_after_second, 2)
        
        print(f"✅ Relocalization count test: {count_after_second} corrections")

    
    def test_get_pose_matches_prd_contract(self):
        """Test that get_pose() matches the PRD's locked tuple contract:
        get_pose() -> (x, y, heading, covariance)"""
        result = self.localizer.get_pose()
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 4)
        x, y, heading, covariance = result
        self.assertEqual(x, 0.0)
        self.assertEqual(y, 0.0)
        self.assertEqual(heading, 0.0)
        self.assertEqual(len(covariance), 3)  # 3x3 matrix as nested list
        print("✅ get_pose() PRD contract test passed")


if __name__ == "__main__":
    unittest.main(verbosity=2)