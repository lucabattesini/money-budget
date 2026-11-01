import google.generativeai as genai
import pytest


def test_real_gemini_calls_are_blocked():
    model = genai.GenerativeModel("gemini-3.5-flash")

    with pytest.raises(RuntimeError, match="blocked in tests"):
        model.generate_content("hello")
