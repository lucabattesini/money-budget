"""Other names for the default categories, used to match the categories of an imported file by themselves."""

from collections import defaultdict

from api.utils.category_aliases import ALIASES, alias_keys, match_keys, unaccented
from db.seed import default_categories


def test_every_default_category_has_aliases_and_nothing_else_is_listed():
    """When a default category is added or renamed in the seed, this list has to follow."""
    assert set(ALIASES) == set(default_categories)


def test_no_spelling_stands_for_two_categories():
    owners = defaultdict(set)
    for canonical, others in ALIASES.items():
        for name in [canonical, *others]:
            for key in match_keys(name):
                owners[key].add(canonical)

    assert {key: names for key, names in owners.items() if len(names) > 1} == {}


def test_english_and_portuguese_names_both_find_the_category():
    keys = alias_keys()

    assert keys["groceries"] == "Supermercado"
    assert keys["restaurants & bars"] == "Restaurantes e Bares"
    assert keys["salary"] == "Salário"
    assert keys["mercado"] == "Supermercado"


def test_names_typed_without_accents_find_the_category():
    keys = alias_keys()

    assert (keys["salario"], keys["agua"], keys["educacao"]) == ("Salário", "Água", "Educação")
    assert keys["combustivel"] == "Combustível"


def test_case_and_emoji_do_not_matter():
    assert match_keys("🛒 SUPERMERCADO") == match_keys("supermercado")


def test_an_ambiguous_word_is_not_an_alias():
    """ "Transporte" or "Saúde" could be several categories: the person is asked instead of guessed for."""
    keys = alias_keys()

    assert "transporte" not in keys
    assert "saude" not in keys
    assert "alimentacao" not in keys  # a group, not a category


def test_unaccented_only_removes_the_accents():
    assert unaccented("Água e Luz — Café") == "Agua e Luz — Cafe"
