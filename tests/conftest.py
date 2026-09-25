"""Mock Streamlit before application modules import."""

import sys
from unittest.mock import MagicMock

mock_st = MagicMock()
mock_st.session_state = MagicMock()
sys.modules["streamlit"] = mock_st
