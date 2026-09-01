"""Load the committed VDO tariff snapshot.

Owned by: Phase 2. Rates come from data/corpus/tariffs.json; see SOURCES.md.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from voltdesk.synthetic.spec import GeneratorConfig

_REPO_ROOT = Path(__file__).resolve().parents[2]


def load_tariffs(config: GeneratorConfig) -> list[dict[str, Any]]:
    path = Path(config.tariff_source_path)
    if not path.is_absolute():
        path = _REPO_ROOT / path
    payload = json.loads(path.read_text(encoding="utf-8"))
    tariffs = payload["tariffs"]
    if not isinstance(tariffs, list) or not tariffs:
        raise ValueError(f"no tariffs in {path}")
    return tariffs
