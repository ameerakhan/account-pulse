"""pandas-version-safe numeric coercion.

``pd.to_numeric(s, errors="ignore")`` was deprecated in pandas 2.2 and removed
in pandas 3. Code that relied on it breaks the first time an unpinned
environment resolves to pandas 3. This helper reproduces the old contract
explicitly: convert a column only when *every* non-null value parses,
otherwise leave it untouched.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


def to_numeric_if_clean(s: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s):
        return s
    converted = pd.to_numeric(s, errors="coerce")
    # Any value that was present but failed to parse means "leave it alone".
    if (converted.isna() & s.notna()).any():
        return s
    return converted


def coerce_frame(df: pd.DataFrame, columns: Iterable[str] | None = None) -> pd.DataFrame:
    cols = list(columns) if columns is not None else list(df.columns)
    out = df.copy()
    for col in cols:
        out[col] = to_numeric_if_clean(out[col])
    return out
