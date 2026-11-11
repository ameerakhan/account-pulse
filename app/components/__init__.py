"""UI helpers shared by the Streamlit pages."""

import sys
from pathlib import Path

# Make the `pulse` package importable when run via `streamlit run app/Home.py`
# without an editable install.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
