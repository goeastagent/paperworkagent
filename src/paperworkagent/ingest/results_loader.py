from __future__ import annotations

from pathlib import Path

import pandas as pd

from paperworkagent.models import ResultsData


def load_results_file(path: Path) -> ResultsData:
    """Load a single CSV/TSV/XLSX file into a ResultsData summary."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(path)
    elif suffix in (".tsv", ".tab"):
        df = pd.read_csv(path, sep="\t")
    elif suffix in (".xlsx", ".xls"):
        df = pd.read_excel(path)
    else:
        raise ValueError(f"Unsupported file format: {suffix}")

    summary: dict = {}
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            summary[col] = {
                "mean": float(df[col].mean()) if not df[col].isna().all() else None,
                "min": float(df[col].min()) if not df[col].isna().all() else None,
                "max": float(df[col].max()) if not df[col].isna().all() else None,
            }

    return ResultsData(
        filename=path.name,
        columns=list(df.columns),
        row_count=len(df),
        summary=summary,
    )


def load_results_dir(dir_path: Path) -> list[ResultsData]:
    """Load all results files from a directory."""
    results = []
    if not dir_path.exists():
        return results
    for path in sorted(dir_path.iterdir()):
        if path.suffix.lower() in (".csv", ".tsv", ".tab", ".xlsx", ".xls"):
            results.append(load_results_file(path))
    return results
