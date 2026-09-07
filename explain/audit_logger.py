import json
from datetime import datetime
from pathlib import Path


LOG_FILE = Path(__file__).resolve().parent / "decision_log.json"


def log_decision(
    chosen_path,
    rejected_path,
    metrics_a,
    metrics_b,
    explanation
):
    """
    Save one path-selection decision to a persistent JSON log.
    """

    decision = {
        "timestamp": datetime.now().isoformat(),
        "chosen_path": chosen_path,
        "rejected_path": rejected_path,
        "metrics": {
            "chosen": metrics_a,
            "rejected": metrics_b,
        },
        "explanation": explanation,
    }

    existing_logs = []

    if LOG_FILE.exists():
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as file:
                existing_logs = json.load(file)

            if not isinstance(existing_logs, list):
                existing_logs = []

        except (json.JSONDecodeError, OSError):
            existing_logs = []

    existing_logs.append(decision)

    with open(LOG_FILE, "w", encoding="utf-8") as file:
        json.dump(existing_logs, file, indent=2)


def read_log():
    """
    Read all stored path-selection decisions.
    """

    if not LOG_FILE.exists():
        return []

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as file:
            return json.load(file)

    except (json.JSONDecodeError, OSError):
        return []