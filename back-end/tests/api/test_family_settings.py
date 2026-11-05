"""The currency and the language are settings of the family (TKT-25): everyone in it sees the same ones."""

import pytest

from schemas.tables import Families, Users


@pytest.fixture
def partner(make_user, user):
    class _Family:
        id = user.family_id

    return make_user("Partner", family=_Family, role="member")


def _settings(client, headers):
    data = client.get("/families/me", headers=headers).json()["data"]
    return data["currency"], data["language"]


def _change(client, headers, **body):
    return client.patch("/families/me/settings", headers=headers, json=body)


def test_a_family_starts_with_reais_and_portuguese(client, auth_headers):
    assert _settings(client, auth_headers) == ("BRL", "pt")


def test_the_family_can_change_both_and_the_answer_shows_the_new_values(client, auth_headers):
    response = _change(client, auth_headers, currency="USD", language="en")

    assert response.status_code == 200
    assert (response.json()["data"]["currency"], response.json()["data"]["language"]) == ("USD", "en")
    assert _settings(client, auth_headers) == ("USD", "en")


def test_canadian_dollars_are_offered(client, auth_headers):
    assert _change(client, auth_headers, currency="CAD").status_code == 200

    assert _settings(client, auth_headers) == ("CAD", "pt")


def test_a_field_left_out_keeps_its_value(client, auth_headers):
    _change(client, auth_headers, currency="EUR", language="en")

    _change(client, auth_headers, language="pt")
    assert _settings(client, auth_headers) == ("EUR", "pt")

    _change(client, auth_headers, currency="GBP")
    assert _settings(client, auth_headers) == ("GBP", "pt")


def test_every_member_sees_the_change_and_any_member_can_make_it(client, auth_headers, partner, headers_for):
    # A member (not an owner) changes it...
    assert _change(client, headers_for(partner), language="en").status_code == 200

    # ...and the owner sees it
    assert _settings(client, auth_headers)[1] == "en"


def test_one_family_never_changes_the_settings_of_another(client, auth_headers, other_user, headers_for):
    _change(client, auth_headers, currency="USD", language="en")

    assert _settings(client, headers_for(other_user)) == ("BRL", "pt")


@pytest.mark.parametrize(
    "body", [{"currency": "JPY"}, {"language": "fr"}, {"currency": "brl"}, {"currency": None, "language": 5}]
)
def test_a_currency_or_language_that_is_not_offered_is_refused_and_nothing_changes(client, auth_headers, body):
    assert _change(client, auth_headers, **body).status_code == 422

    assert _settings(client, auth_headers) == ("BRL", "pt")


def test_changing_the_settings_requires_login(client):
    assert client.patch("/families/me/settings", json={"language": "en"}).status_code in (401, 403)


def test_the_settings_are_kept_in_the_database_for_the_family(client, db, user, auth_headers):
    _change(client, auth_headers, currency="EUR", language="en")

    db.expire_all()
    family = db.get(Families, user.family_id)
    assert (family.currency, family.language) == ("EUR", "en")


def test_someone_who_joins_a_family_sees_its_settings(client, db, user, other_user, auth_headers, headers_for):
    """The settings belong to the family: a person moving to another one gets that one's, not their old ones."""
    _change(client, auth_headers, currency="USD", language="en")
    db.query(Users).filter_by(id=other_user.id).update({"family_id": user.family_id})
    db.commit()

    assert _settings(client, headers_for(other_user)) == ("USD", "en")


# --- timezone (TKT-65) ---------------------------------------------------------------------------------------------


def _timezone(client, headers):
    return client.get("/families/me", headers=headers).json()["data"]["timezone"]


def test_a_family_starts_on_brasilia_time(client, auth_headers):
    assert _timezone(client, auth_headers) == "America/Sao_Paulo"


def test_the_family_can_change_its_timezone_and_the_other_settings_stay(client, auth_headers):
    _change(client, auth_headers, currency="USD")

    response = _change(client, auth_headers, timezone="America/Toronto")

    assert response.status_code == 200
    assert response.json()["data"]["timezone"] == "America/Toronto"
    assert _settings(client, auth_headers) == ("USD", "pt")


def test_changing_only_the_currency_keeps_the_timezone(client, auth_headers):
    _change(client, auth_headers, timezone="Europe/London")

    _change(client, auth_headers, currency="GBP")

    assert _timezone(client, auth_headers) == "Europe/London"


@pytest.mark.parametrize("zone", ["Mars/Olympus", "america/sao_paulo", "", "GMT+3"])
def test_a_timezone_that_is_not_offered_is_refused_and_nothing_changes(client, auth_headers, zone):
    assert _change(client, auth_headers, timezone=zone).status_code == 422

    assert _timezone(client, auth_headers) == "America/Sao_Paulo"


def test_one_family_never_changes_the_timezone_of_another(client, auth_headers, other_user, headers_for):
    _change(client, auth_headers, timezone="UTC")

    assert _timezone(client, headers_for(other_user)) == "America/Sao_Paulo"
