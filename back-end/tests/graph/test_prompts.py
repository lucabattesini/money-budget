"""What the agents are told about the family's language and currency (the model itself is replaced by a fake)."""

import json

import pytest

import agents.recorder.run as recorder_run
import agents.secretary.run as secretary_run


class FakeModel:
    """Remembers the prompt it was given and answers with whatever the test set up."""

    prompts: list[str] = []
    answer = None

    def __init__(self, *args, **kwargs):
        pass

    def generate_content(self, prompt, **kwargs):
        FakeModel.prompts.append(prompt)
        return FakeModel.answer


class Answer:
    candidates: list = []
    text = json.dumps({"reply": "ok"})


@pytest.fixture
def model(monkeypatch):
    FakeModel.prompts = []
    FakeModel.answer = Answer()
    monkeypatch.setattr(recorder_run.genai, "GenerativeModel", FakeModel)
    return FakeModel


@pytest.mark.parametrize(
    "language, wanted, not_wanted",
    [
        ("pt", ["Portuguese (pt-BR)", '"12,50" is 12.5'], ['"12.50" is 12.5']),
        ("en", ["English", '"1,200" is 1200'], ['"12,50" is 12.5']),
    ],
)
def test_the_recorder_is_told_the_language_to_reply_in_and_how_to_read_numbers(model, language, wanted, not_wanted):
    recorder_run.run_recorder("gastei 12 no mercado", language=language)

    [prompt] = model.prompts
    assert all(text in prompt for text in wanted)
    assert not any(text in prompt for text in not_wanted)


@pytest.mark.parametrize(
    "currency, language, wanted",
    [
        ("BRL", "pt", ["Portuguese (pt-BR)", "reais", "R$"]),
        ("USD", "en", ["English", "US dollars", "US$"]),
        ("CAD", "en", ["Canadian dollars", "CA$"]),
    ],
)
def test_the_secretary_is_told_the_language_and_the_currency(model, currency, language, wanted):
    secretary_run.run_secretary("how much?", "[]", currency=currency, language=language)

    [prompt] = model.prompts
    assert all(text in prompt for text in wanted)


def test_without_a_choice_the_agents_speak_portuguese_about_reais(model):
    secretary_run.run_secretary("quanto?", "[]")

    assert "Portuguese (pt-BR)" in model.prompts[0] and "reais" in model.prompts[0]


def test_when_the_answer_cannot_be_used_the_apology_is_in_the_familys_language(model):
    class Broken:
        text = "not json"

    model.answer = Broken()

    assert secretary_run.run_secretary("x", "[]", language="en").reply.startswith("Sorry")
    assert secretary_run.run_secretary("x", "[]", language="pt").reply.startswith("Desculpe")
