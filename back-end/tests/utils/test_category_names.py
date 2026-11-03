import pytest

from api.utils.category_names import plain_name, same_name


@pytest.mark.parametrize(
    "name, plain",
    [
        ("🛒 Supermercado", "Supermercado"),
        ("Supermercado", "Supermercado"),
        ("  🛒   Supermercado  ", "Supermercado"),
        ("✈️ Viagem", "Viagem"),  # an emoji followed by a variation selector
        ("🏋️ Exercícios e Esportes", "Exercícios e Esportes"),
        ("🧑‍💻 Trabalho remoto", "Trabalho remoto"),  # several emoji joined with a zero-width joiner
        ("👍🏽 Combinado", "Combinado"),  # with a skin tone
        ("🇧🇷 Brasil", "Brasil"),  # a flag is two symbols
        ("🛒🥦 Feira", "Feira"),  # more than one emoji
        ("Carro 🚗", "Carro 🚗"),  # only what the name STARTS with is decoration
        ("1️⃣ Primeiro", "1️⃣ Primeiro"),  # a digit is a word character, so it stays
        ("€ Euro", "€ Euro"),  # a currency sign is not an emoji
        ("🛒", ""),  # nothing but an emoji
        ("", ""),
        ("   ", ""),
        (None, ""),
    ],
)
def test_the_name_without_the_emoji_it_starts_with(name, plain):
    assert plain_name(name) == plain


@pytest.mark.parametrize(
    "a, b",
    [
        ("🛒 Supermercado", "Supermercado"),
        ("🛒 Supermercado", "🏪 supermercado"),
        (" ALIMENTAÇÃO", "🍽️ Alimentação"),
    ],
)
def test_names_with_the_same_words_are_the_same_whatever_their_emoji_or_case(a, b):
    assert same_name(a, b)


@pytest.mark.parametrize("a, b", [("🛒 Supermercado", "Mercado"), ("Alimentação", "Alimentacao"), ("", "x")])
def test_different_words_are_different_names(a, b):
    assert not same_name(a, b)
