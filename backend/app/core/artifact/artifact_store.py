import json
from pathlib import Path

from app.shared.config import settings
from app.shared.logging import get_logger

logger = get_logger(__name__)


def _get_artifact_dir(run_id: str, stage_key: str) -> Path:
    base = Path(settings.ARTIFACT_STORAGE_PATH) / run_id / f"stage_{stage_key}"
    base.mkdir(parents=True, exist_ok=True)
    return base


async def save_artifact_file(run_id: str, stage_key: str, artifact_id: str, artifact_type: str, data: dict) -> str:
    dir_path = _get_artifact_dir(run_id, stage_key)
    file_path = dir_path / f"{artifact_id}_{artifact_type}.json"
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.debug(f"Saved artifact file: {file_path}")
    return str(file_path)


async def load_artifact_file(file_path: str) -> dict:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Artifact file not found: {file_path}")
    content = path.read_text(encoding="utf-8")
    return json.loads(content)
