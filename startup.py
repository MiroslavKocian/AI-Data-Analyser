"""API key resolution and application bootstrap."""

import os

import streamlit as st
from dotenv import load_dotenv

from ai_provider import AIProvider
from state_manager import initialize


def resolve_mistral_api_key() -> str | None:
    """
    Read Mistral API key from the environment or Streamlit secrets.

    Local runs typically use a `.env` file. Streamlit Cloud uses
    `.streamlit/secrets.toml`.
    """
    load_dotenv(override=True)
    env_key = os.getenv("MISTRAL_API_KEY")
    if env_key:
        return env_key
    try:
        return st.secrets.get("MISTRAL_API_KEY")
    except Exception:
        return None


def require_mistral_api_key() -> str:
    """Return the API key or stop the app with a clear message."""
    api_key = resolve_mistral_api_key()
    if not api_key:
        st.error(
            "MISTRAL_API_KEY is missing. Add it to `.env` or "
            "`.streamlit/secrets.toml` (see README).",
        )
        st.stop()
    return api_key


def bootstrap_application() -> AIProvider:
    """Prepare session state and return a configured AI client."""
    initialize()
    return AIProvider(require_mistral_api_key())
