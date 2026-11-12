from uuid import UUID

from api.utils.budget_order import GROUP_ORDER
from schemas.tables import Categories, CategoryGroups
from tests.conftest import MISSING_ID


def test_lists_exactly_the_default_categories(client, auth_headers):
    response = client.get("/categories/", headers=auth_headers)

    assert response.status_code == 200
    names = sorted(c["name"] for c in response.json()["data"])
    assert names == [
        "Aluguel",
        "Educação",
        "Restaurantes e Bares",
        "Sem categoria",
        "Supermercado",
        "Transporte público",
    ]


def test_each_category_has_an_id_and_name(client, auth_headers):
    category = client.get("/categories/", headers=auth_headers).json()["data"][0]

    assert set(category) >= {"id", "name"}
    assert UUID(category["id"])  # an id is a UUID written as text


def test_listing_requires_login(client):
    assert client.get("/categories/").status_code in (401, 403)


def test_a_family_sees_its_own_categories_but_never_another_familys(
    client, db, user, other_user, auth_headers, headers_for
):
    db.add_all(
        [
            Categories(name="Pets da família", family_id=user.family_id),
            Categories(name="Plantas do outro", family_id=other_user.family_id),
        ]
    )
    db.commit()

    mine = {c["name"] for c in client.get("/categories/", headers=auth_headers).json()["data"]}
    theirs = {c["name"] for c in client.get("/categories/", headers=headers_for(other_user)).json()["data"]}

    assert "Pets da família" in mine and "Plantas do outro" not in mine
    assert "Plantas do outro" in theirs and "Pets da família" not in theirs
    assert "Sem categoria" in mine and "Sem categoria" in theirs  # the defaults are shared


# --- groups (TKT-44) -----------------------------------------------------------------------------------


def _groups(client, headers):
    response = client.get("/categories/groups", headers=headers)
    assert response.status_code == 200
    return response.json()["data"]


def test_each_category_comes_with_its_group(client, auth_headers):
    categories = {c["name"]: c for c in client.get("/categories/", headers=auth_headers).json()["data"]}
    group_ids = {g["name"]: g["id"] for g in _groups(client, auth_headers)}

    assert {name: c["group_name"] for name, c in categories.items()} == {
        "Restaurantes e Bares": "Alimentação",
        "Supermercado": "Alimentação",
        "Aluguel": "Moradia",
        "Transporte público": "Auto e Transporte",
        "Sem categoria": "Outros",
        "Educação": "Educação",
    }
    assert all(c["group_id"] == group_ids[c["group_name"]] for c in categories.values())


def test_each_category_says_where_its_group_comes_in_the_lists(client, auth_headers):
    categories = client.get("/categories/", headers=auth_headers).json()["data"]
    order = [g["name"] for g in _groups(client, auth_headers)]  # the groups in the order they are shown

    by_position = {c["group_position"]: c["group_name"] for c in categories}

    assert [by_position[position] for position in sorted(by_position)] == [
        name for name in order if name in by_position.values()
    ]
    assert len(by_position) == len({c["group_name"] for c in categories})  # one position per group


def test_the_groups_are_the_same_fixed_set_for_every_family_in_a_stable_order(
    client, auth_headers, other_user, headers_for
):
    mine = _groups(client, auth_headers)

    assert mine == _groups(client, headers_for(other_user))
    assert [g["name"] for g in mine] == GROUP_ORDER  # in order of priority (migration 0023)


def test_listing_the_groups_requires_login(client):
    assert client.get("/categories/groups").status_code in (401, 403)


def test_a_category_made_without_a_group_goes_to_outros(client, db, user, auth_headers):
    db.add(Categories(name="Plantas", family_id=user.family_id))
    db.commit()

    created = {c["name"]: c for c in client.get("/categories/", headers=auth_headers).json()["data"]}["Plantas"]

    assert created["group_name"] == "Outros"


def test_a_category_made_with_a_group_keeps_it(client, db, user, auth_headers):
    viagem = db.query(CategoryGroups).filter_by(name="Viagem e Estilo de Vida").one()
    db.add(Categories(name="Jogos", family_id=user.family_id, group_id=viagem.id))
    db.commit()

    created = {c["name"]: c for c in client.get("/categories/", headers=auth_headers).json()["data"]}["Jogos"]

    assert (created["group_id"], created["group_name"]) == (str(viagem.id), "Viagem e Estilo de Vida")


def test_a_category_cannot_be_saved_with_a_group_that_does_not_exist(db, user):
    import pytest
    from sqlalchemy.exc import IntegrityError

    db.add(Categories(name="Fantasma", family_id=user.family_id, group_id=MISSING_ID))

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_groups_cannot_share_a_name(db):
    import pytest
    from sqlalchemy.exc import IntegrityError

    db.add(CategoryGroups(name="Moradia", position=99))

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_a_category_without_a_group_gets_a_clear_error_when_the_outros_group_is_missing(db, user, monkeypatch):
    import pytest

    from schemas import tables

    monkeypatch.setattr(tables, "FALLBACK_GROUP", "Grupo que não existe")
    db.add(Categories(name="Sem grupo", family_id=user.family_id))

    with pytest.raises(Exception, match="db.upgrade") as error:
        db.commit()
    db.rollback()
    assert "does not exist" in str(error.value)


# --- the order of the groups is data (position) --------------------------------------------------------


def test_the_groups_follow_their_position_not_the_order_they_were_created_in(client, db, auth_headers):
    first = db.query(CategoryGroups).filter_by(name="Outros").one()
    first.position = 0  # moved to the top by the data alone
    db.commit()

    names = [g["name"] for g in _groups(client, auth_headers)]

    assert names[0] == "Outros"
    assert names[1] == "Receitas"


def test_the_budget_page_lists_the_groups_in_the_same_order_as_the_categories_page(client, db, auth_headers):
    last = db.query(CategoryGroups).filter_by(name="Alimentação").one()
    last.position = 500
    db.commit()

    categories_page = [g["name"] for g in _groups(client, auth_headers)]
    budget_page = [
        g["name"]
        for g in client.get("/budgets", params={"month": "2026-11"}, headers=auth_headers).json()["data"]["groups"]
    ]

    assert categories_page[-1] == "Alimentação"
    assert budget_page == [name for name in categories_page if name in budget_page]
    assert budget_page[-1] == "Alimentação"
