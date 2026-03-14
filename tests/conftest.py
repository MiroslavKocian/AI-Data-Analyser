"""
tests/conftest.py
Mocks streamlit before main.py is imported so tests run
without triggering the Streamlit runtime.
"""
from unittest.mock import MagicMock
import sys

mock_st = MagicMock()
mock_st.session_state = MagicMock()
sys.modules['streamlit'] = mock_st