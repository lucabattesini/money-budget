"""Safety nets: the suite must never reach Gemini or the network."""

import google.generativeai as genai
import pytest
import requests


def test_gemini_calls_are_blocked():
    model = genai.GenerativeModel("gemini-3.5-flash")

    with pytest.raises(RuntimeError, match="blocked in tests"):
        model.generate_content("hello")


def test_outbound_http_is_blocked():
    with pytest.raises(Exception, match="Network access is blocked"):
        requests.get("http://example.com", timeout=1)
