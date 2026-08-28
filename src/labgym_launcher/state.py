import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from labgym_launcher.constants import STATE_FILENAME, STATE_VERSION

LOGGER = logging.getLogger("labgym_launcher")


def state_path(data_dir: Path) -> Path:
    return data_dir / STATE_FILENAME


def load_state(data_dir: Path) -> Dict[str, Any]:
    path = state_path(data_dir)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.info("could not read launcher state: %s", exc)
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def save_state(data_dir: Path, payload: Dict[str, Any]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    record = dict(payload)
    record["version"] = STATE_VERSION
    record["updated_at"] = datetime.now(timezone.utc).isoformat()
    path = state_path(data_dir)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    LOGGER.info("wrote launcher state to %s", path)


def state_value(payload: Dict[str, Any], key: str) -> Optional[str]:
    value = payload.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None
