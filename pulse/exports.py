"""Excel export that matches exactly what is on screen."""

from __future__ import annotations

import io
from collections.abc import Mapping

import pandas as pd


def to_excel_bytes(sheets: Mapping[str, pd.DataFrame], notes: Mapping[str, str] | None = None) -> bytes:
    """Write one sheet per frame, plus an optional 'About' sheet of filter notes."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xl:
        for name, df in sheets.items():
            df.to_excel(xl, sheet_name=name[:31], index=False)
            ws = xl.sheets[name[:31]]
            for col_cells in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in col_cells)
                ws.column_dimensions[col_cells[0].column_letter].width = min(48, width + 2)
            ws.freeze_panes = "A2"
        if notes:
            pd.DataFrame(list(notes.items()), columns=["Field", "Value"]).to_excel(
                xl, sheet_name="About", index=False
            )
    return buf.getvalue()
