"""Training history persistence helpers."""

import csv
import json
from datetime import datetime
from pathlib import Path

from utils.io import ensure_dir


class TrainingHistory:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.rows = []

    def append(self, **row):
        enriched = dict(row)
        enriched["timestamp"] = datetime.now().isoformat(timespec="seconds")
        self.rows.append(enriched)

    def save(self):
        ensure_dir(self.output_dir)
        (self.output_dir / "history.json").write_text(json.dumps(self.rows, ensure_ascii=False, indent=2), encoding="utf-8")
        if not self.rows:
            return
        fieldnames = []
        for row in self.rows:
            for key in row.keys():
                if key not in fieldnames:
                    fieldnames.append(key)
        with (self.output_dir / "history.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.rows)
