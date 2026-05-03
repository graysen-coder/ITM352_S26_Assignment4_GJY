"""
Run history + charts (placeholder until gameplay is finalized).
"""

from __future__ import annotations

from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()


def _project_root() -> Path:
    return Path(__file__).resolve().parent


def default_runs_csv_path() -> Path:
    env = os.environ.get("RUNS_CSV_PATH")
    if env:
        p = Path(env)
        if not p.is_absolute():
            p = _project_root() / p
        return p
    return _project_root() / "data" / "runs.csv"


def load_history(csv_path: Path | None = None):
    import pandas as pd

    path = csv_path or default_runs_csv_path()
    if not path.is_file():
        return pd.DataFrame()
    return pd.read_csv(path)


def analyze_run_history(df):
    """Return summary dicts for templates / charts once runs exist."""
    if df is None or df.empty:
        return {"message": "No run history yet."}
    return {"row_count": int(len(df))}


def generate_chart(df, out_path: Path | None = None) -> Path | None:
    """Write a chart image when run data exists; otherwise return None."""
    if df is None or df.empty:
        return None
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path = out_path or (_project_root() / "data" / "runs_placeholder.png")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.text(0.5, 0.5, "Add runs.csv columns\nthen chart real metrics.", ha="center", va="center")
    ax.axis("off")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path
