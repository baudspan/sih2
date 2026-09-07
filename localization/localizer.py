"""
localizer.py — M2 Localization
EKF prediction (drift simulation) + RANSAC-based crater matching correction.
"""

import numpy as np
import random
from .crater_loader import load_craters


class Localizer:
    def __init__(self):
        # Load real crater landmarks
        self.landmark_db = load_craters()
        
        # Convert landmark list to numpy array for faster computation
        self.landmark_xyz = np.array([[c["x"], c["y"]] for c in self.landmark_db])
        self.landmark_ids = [c["id"] for c in self.landmark_db]
        
        # State: [x, y, heading]
        self.pose = np.array([0.0, 0.0, 0.0])
        
        # Covariance matrix (3x3) — represents uncertainty
        self.covariance = np.eye(3) * 0.01
        
        # Drift parameters
        self.distance_traveled = 0.0
        self.drift_factor = 0.25  # 25% drift per meter (configurable)
        
        # RANSAC parameters
        self.ransac_iterations = 100
        self.ransac_threshold = 50.0  # meters — inlier threshold
        self.min_inliers = 3
        
        # Re-localization tracking
        self.relocalization_count = 0
        self.last_error_before = 0.0
        self.last_error_after = 0.0
        
        # Fallback dummy matches (for demo insurance)
        self.fallback_craters = []
    
    def predict(self, dt, odometry):
        """
        Prediction step: update pose based on odometry, grow covariance.
        
        Args:
            dt: time step (seconds)
            odometry: dict with 'velocity' and 'angular_velocity'
        """
        # Unpack odometry
        v = odometry.get('velocity', 0.0)
        omega = odometry.get('angular_velocity', 0.0)
        
        # Update pose (simple kinematic model)
        heading = self.pose[2]
        self.pose[0] += v * dt * np.cos(heading)
        self.pose[1] += v * dt * np.sin(heading)
        self.pose[2] += omega * dt
        
        # Normalize heading to [-pi, pi]
        self.pose[2] = np.arctan2(np.sin(self.pose[2]), np.cos(self.pose[2]))
        
        # Update distance traveled (for drift injection)
        self.distance_traveled += v * dt
        
        # Grow covariance (linear with distance)
        drift_increment = self.drift_factor * v * dt
        self.covariance[0, 0] += drift_increment
        self.covariance[1, 1] += drift_increment
        self.covariance[2, 2] += drift_increment * 0.1  # heading drifts slower
    
    def correct(self, detected_craters, use_fallback=False, fallback_craters=None):
        """
        Correction step: RANSAC-match detected craters against landmark DB.
        
        Args:
            detected_craters: list of dicts from M3's perception
                e.g., [{"x": 1200.0, "y": 3400.0, "radius": 50.0}, ...]
            use_fallback: bool — if True, use fallback craters (demo insurance)
            fallback_craters: list of dicts with 'x', 'y' for dummy matches
        
        Returns:
            bool: True if correction was applied, False otherwise
        """
        # If no detected craters, try fallback
        if len(detected_craters) < 3:
            if use_fallback and fallback_craters and len(fallback_craters) >= 3:
                print("⚠️ Using fallback craters (detection failed)")
                detected_craters = fallback_craters
            else:
                return False
        
        # Convert detected craters to numpy array
        detected_xyz = np.array([[c["x"], c["y"]] for c in detected_craters])
        
        # ---------- RANSAC Loop ----------
        best_transform = None
        best_inliers = []
        best_inlier_count = 0
        
        for _ in range(self.ransac_iterations):
            # Randomly sample 3 detected craters
            if len(detected_xyz) < 3:
                break
            
            sample_indices = random.sample(range(len(detected_xyz)), 3)
            sample_pts = detected_xyz[sample_indices]
            
            # For each sampled point, find nearest landmark in DB
            landmark_matches = []
            for pt in sample_pts:
                # Compute distances to all landmarks
                distances = np.linalg.norm(self.landmark_xyz - pt, axis=1)
                nearest_idx = np.argmin(distances)
                nearest_dist = distances[nearest_idx]
                
                # Only accept if within reasonable distance (e.g., 500m)
                if nearest_dist < 500.0:
                    landmark_matches.append(self.landmark_xyz[nearest_idx])
                else:
                    break
            
            if len(landmark_matches) < 3:
                continue
            
            # Compute transform (rotation + translation) using Procrustes
            landmark_xyz = np.array(landmark_matches)
            detected_xyz_sampled = np.array(sample_pts)
            
            # Center the points
            centroid_landmark = np.mean(landmark_xyz, axis=0)
            centroid_detected = np.mean(detected_xyz_sampled, axis=0)
            
            landmark_centered = landmark_xyz - centroid_landmark
            detected_centered = detected_xyz_sampled - centroid_detected
            
            # Compute rotation matrix using SVD
            H = landmark_centered.T @ detected_centered
            U, S, Vt = np.linalg.svd(H)
            R = Vt.T @ U.T
            
            # Handle reflection case
            if np.linalg.det(R) < 0:
                Vt[-1, :] *= -1
                R = Vt.T @ U.T
            
            # Translation
            t = centroid_landmark - R @ centroid_detected
            
            # Count inliers
            inliers = []
            for i, pt in enumerate(detected_xyz):
                # Transform detected point into landmark frame
                transformed = R @ pt + t
                # Find nearest landmark
                distances = np.linalg.norm(self.landmark_xyz - transformed, axis=1)
                min_dist = np.min(distances)
                
                if min_dist < self.ransac_threshold:
                    inliers.append(i)
            
            # Keep best transform
            if len(inliers) > best_inlier_count:
                best_inlier_count = len(inliers)
                best_inliers = inliers
                best_transform = (R, t)
        
        # ---------- Apply Best Transform ----------
        if best_transform is None or best_inlier_count < self.min_inliers:
            return False
        
        R, t = best_transform
        
        # Compute the average correction from inliers
        correction_x = t[0]
        correction_y = t[1]
        
        # Extract rotation angle
        correction_heading = np.arctan2(R[1, 0], R[0, 0])
        
        # Store error before correction
        self.last_error_before = np.sqrt(self.covariance[0, 0] + self.covariance[1, 1])
        
        # Apply correction to pose (weighted blend — conservative update)
        blend_factor = min(0.9, len(best_inliers) / 5.0)  # More inliers = stronger correction
        
        self.pose[0] = self.pose[0] * (1 - blend_factor) + correction_x * blend_factor
        self.pose[1] = self.pose[1] * (1 - blend_factor) + correction_y * blend_factor
        
        # Heading correction (handle wrap-around)
        heading_diff = correction_heading - self.pose[2]
        heading_diff = np.arctan2(np.sin(heading_diff), np.cos(heading_diff))
        self.pose[2] += heading_diff * blend_factor
        self.pose[2] = np.arctan2(np.sin(self.pose[2]), np.cos(self.pose[2]))
        
        # Shrink covariance
        shrink_factor = 1.0 - blend_factor * 0.95
        self.covariance = self.covariance * shrink_factor
        
        # Ensure minimum covariance
        min_cov = 0.01
        self.covariance = np.maximum(self.covariance, min_cov)
        
        # Store error after correction
        self.last_error_after = np.sqrt(self.covariance[0, 0] + self.covariance[1, 1])
        
        # Increment re-localization counter
        self.relocalization_count += 1
        
        print(f"✅ Re-localization #{self.relocalization_count}: "
              f"{self.last_error_before:.2f}m → {self.last_error_after:.2f}m "
              f"({len(best_inliers)} inliers)")
        
        return True
    
    def get_pose(self):
        """
        PRD-CONTRACT method (Table 8): get_pose() -> (x, y, heading, covariance)
        Returns a plain tuple, exactly as M5/M4 expect per the locked interface.
        """
        return (
            float(self.pose[0]),
            float(self.pose[1]),
            float(self.pose[2]),
            self.covariance.tolist()
        )

    def get_telemetry(self):
        """
        EXTRA (not in PRD contract) — richer dict for M2's own tests / dashboard
        telemetry panel, which wants uncertainty + relocalization stats too.
        Use get_pose() for anything that must match the PRD contract exactly.
        """
        uncertainty = np.sqrt(self.covariance[0, 0] + self.covariance[1, 1])
        
        return {
            "x": float(self.pose[0]),
            "y": float(self.pose[1]),
            "heading": float(self.pose[2]),
            "covariance": self.covariance.tolist(),
            "uncertainty": float(uncertainty),
            "relocalization_count": self.relocalization_count,
            "last_error_before": float(self.last_error_before),
            "last_error_after": float(self.last_error_after)
        }
    
    def get_uncertainty_level(self):
        """
        Returns the uncertainty level based on the PRD thresholds (Table 11).
        Returns: 'normal', 'caution', or 're_localizing'
        (renamed from 'critical' to match PRD's dashboard badge states:
        NORMAL / CAUTION / RE-LOCALIZING)
        """
        uncertainty = np.sqrt(self.covariance[0, 0] + self.covariance[1, 1])
        
        if uncertainty < 3.0:
            return "normal"
        elif uncertainty < 5.0:
            return "caution"
        else:
            return "re_localizing"
    
    def set_fallback_craters(self, fallback_craters):
        """
        Set fallback craters for demo insurance (called by M5 from JSON config).
        """
        self.fallback_craters = fallback_craters


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# Quick test / simulation
if __name__ == "__main__":
    localizer = Localizer()
    print(f"✅ Loaded {len(localizer.landmark_db)} landmarks")
    print(f"Initial pose: {localizer.get_pose()}")
    
    # Simulate 20 steps of driving (more steps = more drift)
    print("\n🚗 Simulating driving...")
    for step in range(20):
        odometry = {
            "velocity": 2.0,  # 2 m/s
            "angular_velocity": 0.0
        }
        localizer.predict(1.0, odometry)
        if step % 5 == 0 or step == 19:  # Print every 5 steps
            pose = localizer.get_pose()
            print(f"  Step {step+1}: uncertainty={pose['uncertainty']:.2f}m, status={localizer.get_uncertainty_level()}")
    
    # --- FIX: Use REAL crater coordinates from the database ---
    print("\n🔭 Simulating crater detection + re-localization...")
    
    # Get the first 5 real craters from the landmark database
    real_craters = localizer.landmark_db[:5]
    
    # Convert to detected crater format (with some noise)
    detected_craters = []
    for c in real_craters:
        # Add small noise to simulate real detection
        noise_x = np.random.normal(0, 10.0)   # 10m noise
        noise_y = np.random.normal(0, 10.0)
        detected_craters.append({
            "x": c["x"] + noise_x,
            "y": c["y"] + noise_y,
            "radius": c["diameter"] / 2.0,
            "confidence": 0.9
        })
    
    # Show state before correction
    pose_before = localizer.get_pose()
    print(f"  Before correction: uncertainty={pose_before['uncertainty']:.2f}m")
    print(f"  Detected {len(detected_craters)} craters near real landmarks")
    
    # Apply correction
    success = localizer.correct(detected_craters)
    
    if success:
        pose_after = localizer.get_pose()
        print(f"  After correction: uncertainty={pose_after['uncertainty']:.2f}m")
        print(f"  Re-localization count: {pose_after['relocalization_count']}")
        print(f"  Error reduction: {pose_after['last_error_before']:.2f}m → {pose_after['last_error_after']:.2f}m")
        print(f"  ✅ Improvement: {pose_after['last_error_before'] - pose_after['last_error_after']:.2f}m reduction!")
    else:
        print("  ❌ Re-localization failed (not enough matches)")
    
    print("\n✅ Test complete")