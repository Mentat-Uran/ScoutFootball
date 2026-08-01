"""CSV export safety helpers.

Guard against spreadsheet formula injection when exporting user-facing
CSV files.  Cells whose first character is a formula trigger (=, +, -,
@, tab, CR) are prefixed with a single quote so that spreadsheet
applications treat them as text rather than executable formulas.

This mirrors the frontend ``csvCell()`` implementation in
``frontend/app.js`` and satisfies the AGENTS.md requirement that CSV
exports must guard against spreadsheet formula injection.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from typing import Any

# Characters that trigger formula interpretation in spreadsheet
# applications (Excel, LibreOffice, Google Sheets).  A leading single
# quote forces text mode in all major spreadsheets.
_DANGEROUS_PREFIXES = frozenset(("=", "+", "-", "@", "\t", "\r"))


def sanitize_csv_cell(value: Any) -> str:
    """Return a CSV-safe string representation of ``value``.

    If the string representation starts with a formula trigger
    character, a single quote is prepended to prevent spreadsheet
    formula injection.  The value is returned as a plain string (not
    CSV-quoted); callers should pass it through ``csv.writer`` which
    handles quoting.
    """
    text = "" if value is None else str(value)
    if text and text[0] in _DANGEROUS_PREFIXES:
        return "'" + text
    return text


def sanitize_csv_row(row: Iterable[Any]) -> list[str]:
    """Apply :func:`sanitize_csv_cell` to every cell in a row."""
    return [sanitize_csv_cell(cell) for cell in row]


def write_csv(rows: Iterable[Iterable[Any]], header: Iterable[str] | None = None) -> str:
    """Write rows to a CSV string with formula-injection protection.

    Parameters
    ----------
    rows
        Iterable of row iterables.  Each row's cells are sanitized
        before writing.
    header
        Optional header row.  Also sanitized (headers are less likely
        to contain formula triggers, but we sanitize for consistency).
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    if header is not None:
        writer.writerow(sanitize_csv_row(header))
    for row in rows:
        writer.writerow(sanitize_csv_row(row))
    return buf.getvalue()


def dataframe_to_csv(frame: Any, *, index: bool = False) -> str:
    """Convert a pandas DataFrame to a CSV string with formula-injection
    protection.

    This is a drop-in replacement for ``DataFrame.to_csv(index=False)``
    that sanitizes every cell before writing.
    """
    import pandas as pd  # local import to avoid hard dependency at module import

    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"expected pandas.DataFrame, got {type(frame).__name__}")

    rows = frame.itertuples(index=index, name=None)
    header = list(frame.columns) if not index else ["", *frame.columns]
    return write_csv(rows, header=header)
