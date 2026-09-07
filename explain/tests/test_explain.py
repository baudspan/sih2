from datetime import datetime

import numpy as np
import pytest
import rasterio
from rasterio.errors import RasterioIOError
from rasterio.transform import from_origin

from explain.audit_logger import log_decision, read_log
from explain.generate_explanation import generate_contrastive_explanation
from explain.path_metrics import compute_path_metrics


def create_test_raster(path, values):
    """Create a small temporary raster for testing."""

    height, width = values.shape

    transform = from_origin(0, height, 1, 1)

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="float32",
        transform=transform,
    ) as dst:
        dst.write(values.astype("float32"), 1)


@pytest.fixture
def test_terrain(tmp_path, monkeypatch):
    slope_file = tmp_path / "slope.tif"
    roughness_file = tmp_path / "roughness.tif"

    slope_values = np.ones((10, 10), dtype=np.float32) * 5
    roughness_values = np.ones((10, 10), dtype=np.float32) * 2

    create_test_raster(slope_file, slope_values)
    create_test_raster(roughness_file, roughness_values)

    import explain.path_metrics as path_metrics

    monkeypatch.setattr(path_metrics, "SLOPE_PATH", slope_file)
    monkeypatch.setattr(path_metrics, "ROUGHNESS_PATH", roughness_file)

    return slope_file, roughness_file


def test_compute_path_metrics_uses_rasters_and_covariance(test_terrain):
    path = [(0.5, 9.5), (1.5, 9.5), (2.5, 9.5)]

    covariance = [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 0.1],
    ]

    metrics = compute_path_metrics(path, covariance)

    assert set(metrics) == {
        "slip_risk",
        "crater_covariance",
        "energy_proxy",
    }
    assert metrics["slip_risk"] == pytest.approx(7.0)
    assert metrics["crater_covariance"] == pytest.approx(np.sqrt(2.0))
    assert metrics["energy_proxy"] == pytest.approx(2.1)
    assert all(value >= 0 for value in metrics.values())


def test_compute_path_metrics_accepts_m2_localization_payload(test_terrain):
    path = [(0.5, 9.5), (1.5, 9.5)]
    localization = {
        "x": 1.0,
        "y": 2.0,
        "heading": 0.5,
        "covariance": [
            [4.0, 0.0, 0.0],
            [0.0, 9.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        "uncertainty": 0.25,
        "relocalization_count": 2,
        "last_error_before": 1.2,
        "last_error_after": 0.4,
    }

    metrics = compute_path_metrics(path, localization)

    assert metrics["crater_covariance"] == pytest.approx(np.sqrt(13.0))


def test_generate_contrastive_explanation_is_deterministic(test_terrain):
    path_a = [(0.5, 9.5), (1.5, 9.5), (2.5, 9.5)]
    path_b = [(0.5, 9.5), (2.5, 9.5), (4.5, 9.5)]

    covariance_a = np.eye(3).tolist()
    covariance_b = (np.eye(3) * 2).tolist()

    result = generate_contrastive_explanation(
        path_a,
        path_b,
        covariance_a,
        covariance_b,
    )
    repeated_result = generate_contrastive_explanation(
        path_a,
        path_b,
        covariance_a,
        covariance_b,
    )

    assert result == repeated_result
    assert result["chosen_path"] == "A"
    assert result["rejected_path"] == "B"
    assert "explanation" in result
    assert "Chose Path A over Path B" in result["explanation"]
    assert "Slip Risk was equal (chosen 7.00, rejected 7.00)" in result["explanation"]
    assert "Crater Covariance lower by 0.59" in result["explanation"]
    assert "Energy Proxy lower by 2.10" in result["explanation"]

    changed_result = generate_contrastive_explanation(
        path_a,
        path_b,
        covariance_a,
        (np.eye(3) * 5).tolist(),
    )

    assert changed_result["explanation"] != result["explanation"]
    assert "Crater Covariance lower by 1.75" in changed_result["explanation"]


def test_audit_logger_writes_and_reads_decisions(tmp_path, monkeypatch):
    import explain.audit_logger as audit_logger

    log_file = tmp_path / "decision_log.json"
    monkeypatch.setattr(audit_logger, "LOG_FILE", log_file)

    metrics_a = {
        "slip_risk": 7.0,
        "crater_covariance": 1.41,
        "energy_proxy": 2.1,
    }
    metrics_b = {
        "slip_risk": 7.0,
        "crater_covariance": 2.0,
        "energy_proxy": 4.2,
    }
    explanation = "Chose Path A over Path B because metrics were lower."

    log_decision("A", "B", metrics_a, metrics_b, explanation)
    logs = read_log()

    assert len(logs) == 1
    decision = logs[0]
    assert datetime.fromisoformat(decision["timestamp"])
    assert decision["chosen_path"] == "A"
    assert decision["rejected_path"] == "B"
    assert decision["metrics"] == {
        "chosen": metrics_a,
        "rejected": metrics_b,
    }
    assert decision["explanation"] == explanation


def test_missing_raster_raises_clear_error(tmp_path, monkeypatch):
    import explain.path_metrics as path_metrics

    monkeypatch.setattr(path_metrics, "SLOPE_PATH", tmp_path / "missing_slope.tif")
    monkeypatch.setattr(
        path_metrics,
        "ROUGHNESS_PATH",
        tmp_path / "missing_roughness.tif",
    )

    with pytest.raises(RasterioIOError):
        compute_path_metrics([(0.5, 9.5), (1.5, 9.5)], np.eye(3).tolist())
