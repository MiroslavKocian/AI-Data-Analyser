"""Mock Streamlit before application modules import."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Ensure project root is importable (matches pytest pythonpath; helps IDEs).
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

mock_st = MagicMock()
mock_st.session_state = MagicMock()
sys.modules["streamlit"] = mock_st
