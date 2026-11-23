"""Load SYNTHETIC examples into SQLite."""
from __future__ import annotations

from pathlib import Path

from app import parsers, store

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples"


def load_all() -> None:
    store.init_db()
    files = {
        "rate_sheet": ("SYNTHETIC_rate_sheet.csv", parsers.parse_rate_sheet, store.save_rate_sheet),
        "grid_a": ("SYNTHETIC_grid_a.csv", parsers.parse_grid_a, store.save_grid_a),
        "grid_b": ("SYNTHETIC_grid_b.csv", parsers.parse_grid_b, store.save_grid_b),
        "margins": ("SYNTHETIC_margins.csv", parsers.parse_margins, store.save_margins),
    }
    for _, (fname, parser, saver) in files.items():
        path = EX / fname
        if not path.exists():
            raise FileNotFoundError(f"missing {path}; run scripts/make_synthetic.py")
        data = path.read_bytes()
        result = parser(data, fname)
        if not result.ok:
            raise RuntimeError(f"seed parse failed for {fname}: {result.errors}")
        saver(result.rows, fname)


if __name__ == "__main__":
    load_all()
    print("seeded from", EX)