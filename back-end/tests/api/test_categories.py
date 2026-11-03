from schemas.tables import Categories, CategoryGroups


def test_lists_exactly_the_default_categories(client, auth_headers):
    response = client.get("/categories/", headers=auth_headers)

    assert response.status_code == 200
    names = sorted(c["name"] for c in response.json()["data"])
    assert names == ["Alimentação", "Aluguel", "Outros", "Supermercado", "Transporte"]


def test_each_category_has_an_id_and_name(client, auth_headers):
    category = client.get("/categories/", headers=auth_headers).json()["data"][0]

    assert set(category) >= {"id", "name"}
    assert isinstance(category["id"], int)


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
    assert "Outros" in mine and "Outros" in theirs  # the defaults are shared


# --- groups (TKT-44) -----------------------------------------------------------------------------------


def _groups(client, headers):
    response = client.get("/categories/groups", headers=headers)
    assert response.status_code == 200
    return response.json()["data"]


def test_each_category_comes_with_its_group(client, auth_headers):
    categories = {c["name"]: c for c in client.get("/categories/", headers=auth_headers).json()["data"]}
    group_ids = {g["name"]: g["id"] for g in _groups(client, auth_headers)}

    assert {name: c["group_name"] for name, c in categories.items()} == {
        "Alimentação": "Alimentação",
        "Supermercado": "Alimentação",
        "Aluguel": "Casa",
        "Transporte": "Transporte",
        "Outros": "Outros",
    }
    assert all(c["group_id"] == group_ids[c["group_name"]] for c in categories.values())


def test_the_groups_are_the_same_fixed_set_for_every_family_in_a_stable_order(
    client, auth_headers, other_user, headers_for
):
    mine = _groups(client, auth_headers)

    assert mine == _groups(client, headers_for(other_user))
    assert [g["name"] for g in mine] == [
        "Casa",
        "Alimentação",
        "Transporte",
        "Saúde e bem-estar",
        "Lazer",
        "Educação",
        "Compras e presentes",
        "Finanças",
        "Receitas",
        "Transferências",
        "Investimentos",
        "Outros",
    ]


def test_listing_the_groups_requires_login(client):
    assert client.get("/categories/groups").status_code in (401, 403)


def test_a_category_made_without_a_group_goes_to_outros(client, db, user, auth_headers):
    db.add(Categories(name="Plantas", family_id=user.family_id))
    db.commit()

    created = {c["name"]: c for c in client.get("/categories/", headers=auth_headers).json()["data"]}["Plantas"]

    assert created["group_name"] == "Outros"


def test_a_category_made_with_a_group_keeps_it(client, db, user, auth_headers):
    lazer = db.query(CategoryGroups).filter_by(name="Lazer").one()
    db.add(Categories(name="Jogos", family_id=user.family_id, group_id=lazer.id))
    db.commit()

    created = {c["name"]: c for c in client.get("/categories/", headers=auth_headers).json()["data"]}["Jogos"]

    assert (created["group_id"], created["group_name"]) == (lazer.id, "Lazer")


def test_a_category_cannot_be_saved_with_a_group_that_does_not_exist(db, user):
    import pytest
    from sqlalchemy.exc import IntegrityError

    db.add(Categories(name="Fantasma", family_id=user.family_id, group_id=999_999))

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_groups_cannot_share_a_name(db):
    import pytest
    from sqlalchemy.exc import IntegrityError

    db.add(CategoryGroups(name="Casa"))

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
