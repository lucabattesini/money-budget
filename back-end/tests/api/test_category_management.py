"""A family adds, renames, regroups and deletes its own categories (TKT-45).

`user` and `other_user` are in different families. The default categories (no family) can be seen but never changed.
"""

import pytest

from schemas.tables import Categories, CategoryGroups, TransactionDB


def _post(client, headers, **body):
    return client.post("/categories", json=body, headers=headers)


def _patch(client, headers, id, **body):
    return client.patch(f"/categories/{id}", json=body, headers=headers)


def _list(client, headers):
    return {c["name"]: c for c in client.get("/categories/", headers=headers).json()["data"]}


def _group(db, name):
    return db.query(CategoryGroups).filter_by(name=name).one()


@pytest.fixture
def own(client, auth_headers):
    """A category of the caller's family."""
    return _post(client, auth_headers, name="Plantas").json()["data"]


# --- the list tells defaults from the family's own -------------------------------------------------------


def test_the_list_marks_the_default_categories(client, auth_headers, own):
    categories = _list(client, auth_headers)

    assert categories["Alimentação"]["is_default"] is True
    assert categories["Plantas"]["is_default"] is False


def test_the_list_is_served_at_the_address_the_web_app_uses_without_a_redirect(client, auth_headers):
    """The web app calls GET /categories (no trailing slash). It once answered 405 once POST /categories existed."""
    response = client.get("/categories", headers=auth_headers)

    assert response.status_code == 200
    assert response.history == []  # not redirected: the Authorization header must survive
    assert any(c["name"] == "Alimentação" for c in response.json()["data"])


def test_every_address_the_web_app_calls_works_exactly_as_written(client, auth_headers, own):
    """Guards against a path that exists for one method only, which turns the others into a 405."""
    category = own["id"]

    calls = [
        client.get("/categories", headers=auth_headers),
        client.get("/categories/", headers=auth_headers),
        client.get("/categories/groups", headers=auth_headers),
        client.post("/categories", json={"name": "Nova"}, headers=auth_headers),
        client.patch(f"/categories/{category}", json={"name": "Outra"}, headers=auth_headers),
        client.delete(f"/categories/{category}", headers=auth_headers),
    ]

    assert [c.status_code for c in calls] == [200, 200, 200, 201, 200, 200]
    assert all(c.history == [] for c in calls)


# --- adding ----------------------------------------------------------------------------------------------


def test_adding_a_category_makes_it_the_familys_own_and_lists_it_with_its_group(client, db, user, auth_headers):
    lazer = _group(db, "Lazer")

    response = _post(client, auth_headers, name="Jogos", group_id=lazer.id)

    assert response.status_code == 201
    created = response.json()["data"]
    assert (created["name"], created["group_id"], created["group_name"], created["family_id"]) == (
        "Jogos",
        lazer.id,
        "Lazer",
        user.family_id,
    )
    assert _list(client, auth_headers)["Jogos"]["id"] == created["id"]


def test_a_category_added_without_a_group_goes_to_outros(client, auth_headers):
    created = _post(client, auth_headers, name="Sem grupo").json()["data"]

    assert created["group_name"] == "Outros"


def test_spaces_around_the_name_are_dropped(client, auth_headers):
    created = _post(client, auth_headers, name="   Cursos online  ").json()["data"]

    assert created["name"] == "Cursos online"


@pytest.mark.parametrize("name", ["", "   ", "\t"])
def test_an_empty_name_is_refused_with_a_clear_message(client, auth_headers, name):
    response = _post(client, auth_headers, name=name)

    assert response.status_code == 422
    assert response.json()["detail"] == "O nome da categoria não pode ficar vazio."


def test_a_name_longer_than_the_database_allows_is_refused(client, auth_headers):
    response = _post(client, auth_headers, name="x" * 101)

    assert response.status_code == 422
    assert "100" in response.json()["detail"]
    assert _post(client, auth_headers, name="x" * 100).status_code == 201


def test_a_group_that_does_not_exist_is_refused_and_nothing_is_saved(client, auth_headers):
    response = _post(client, auth_headers, name="Fantasma", group_id=999_999)

    assert response.status_code == 422
    assert "Fantasma" not in _list(client, auth_headers)


@pytest.mark.parametrize("name", ["plantas", "  PLANTAS ", "Plantas"])
def test_a_name_already_used_in_the_family_is_refused_ignoring_case_and_spaces(client, auth_headers, own, name):
    response = _post(client, auth_headers, name=name)

    assert response.status_code == 409
    assert response.json()["detail"] == "Já existe uma categoria com esse nome."
    assert [c for c in _list(client, auth_headers) if c.strip().lower() == "plantas"] == ["Plantas"]


@pytest.mark.parametrize("name", ["alimentação", " ALIMENTAÇÃO ", "Outros"])
def test_a_name_that_clashes_with_a_default_category_is_refused(client, auth_headers, name):
    response = _post(client, auth_headers, name=name)

    assert response.status_code == 409


def test_another_family_may_use_the_same_name_and_gets_its_own_category(
    client, auth_headers, own, other_user, headers_for
):
    response = _post(client, headers_for(other_user), name="Plantas")

    assert response.status_code == 201
    theirs = response.json()["data"]
    assert theirs["id"] != own["id"] and theirs["family_id"] == other_user.family_id
    assert _list(client, auth_headers)["Plantas"]["id"] == own["id"]  # each family sees only its own


def test_adding_requires_login(client):
    assert client.post("/categories", json={"name": "x"}).status_code in (401, 403)


# --- renaming and regrouping -----------------------------------------------------------------------------


def test_a_category_can_be_renamed_and_keeps_its_group_and_its_transactions(
    client, db, user, auth_headers, own, make_transaction
):
    row = make_transaction(user, own["id"], label="Vaso")

    response = _patch(client, auth_headers, own["id"], name="Jardim")

    assert response.status_code == 200
    data = response.json()["data"]
    assert (data["id"], data["name"], data["group_name"]) == (own["id"], "Jardim", own["group_name"])
    db.expire_all()
    assert db.get(TransactionDB, row.id).category_id == own["id"]  # the same category, so the transaction follows


def test_a_category_can_change_group_without_changing_name(client, db, auth_headers, own):
    lazer = _group(db, "Lazer")

    data = _patch(client, auth_headers, own["id"], group_id=lazer.id).json()["data"]

    assert (data["name"], data["group_id"], data["group_name"]) == ("Plantas", lazer.id, "Lazer")


def test_name_and_group_can_change_together(client, db, auth_headers, own):
    casa = _group(db, "Casa")

    data = _patch(client, auth_headers, own["id"], name="Jardim", group_id=casa.id).json()["data"]

    assert (data["name"], data["group_name"]) == ("Jardim", "Casa")


def test_changing_only_the_case_of_its_own_name_is_allowed(client, auth_headers, own):
    response = _patch(client, auth_headers, own["id"], name="PLANTAS")

    assert response.status_code == 200
    assert response.json()["data"]["name"] == "PLANTAS"


def test_renaming_onto_another_category_of_the_family_or_a_default_is_refused(client, auth_headers, own):
    _post(client, auth_headers, name="Jardim")

    assert _patch(client, auth_headers, own["id"], name=" jardim ").status_code == 409
    assert _patch(client, auth_headers, own["id"], name="Alimentação").status_code == 409
    assert _list(client, auth_headers)["Plantas"]["id"] == own["id"]  # unchanged


@pytest.mark.parametrize("body", [{}, {"name": "  "}, {"name": ""}, {"group_id": 999_999}])
def test_a_bad_change_is_refused_and_leaves_the_category_as_it_was(client, auth_headers, own, body):
    response = _patch(client, auth_headers, own["id"], **body)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)  # a message people can read
    assert _list(client, auth_headers)["Plantas"]["group_id"] == own["group_id"]


def test_a_default_category_cannot_be_renamed_or_regrouped(client, db, auth_headers):
    default = _list(client, auth_headers)["Alimentação"]

    renamed = _patch(client, auth_headers, default["id"], name="Comida")
    regrouped = _patch(client, auth_headers, default["id"], group_id=_group(db, "Lazer").id)
    missing = _patch(client, auth_headers, 999_999, name="x")

    assert (renamed.status_code, regrouped.status_code) == (404, 404)
    assert renamed.json() == missing.json()  # indistinguishable from a category that does not exist
    unchanged = _list(client, auth_headers)["Alimentação"]
    assert (unchanged["name"], unchanged["group_name"]) == ("Alimentação", "Alimentação")


def test_another_familys_category_cannot_be_changed_and_answers_like_a_missing_one(
    client, db, auth_headers, own, other_user, headers_for
):
    stranger = headers_for(other_user)

    renamed = _patch(client, stranger, own["id"], name="Roubada")
    missing = _patch(client, stranger, 999_999, name="Roubada")

    assert renamed.status_code == 404 and renamed.json() == missing.json()
    assert _list(client, auth_headers)["Plantas"]["id"] == own["id"]


# --- deleting --------------------------------------------------------------------------------------------


def test_an_unused_category_can_be_deleted_and_its_name_used_again(client, auth_headers, own):
    response = client.delete(f"/categories/{own['id']}", headers=auth_headers)

    assert response.status_code == 200
    assert "Plantas" not in _list(client, auth_headers)
    assert _post(client, auth_headers, name="Plantas").status_code == 201


@pytest.mark.parametrize("count, message", [(1, "usada por 1 transação."), (3, "usada por 3 transações.")])
def test_a_category_in_use_is_not_deleted_and_the_message_says_how_many_transactions_use_it(
    client, db, user, auth_headers, own, make_transaction, count, message
):
    rows = [make_transaction(user, own["id"], label=f"t{i}") for i in range(count)]
    make_transaction(user, _list(client, auth_headers)["Outros"]["id"], label="other category")

    response = client.delete(f"/categories/{own['id']}", headers=auth_headers)

    assert response.status_code == 409
    assert message in response.json()["detail"]
    assert "Plantas" in _list(client, auth_headers)
    db.expire_all()
    assert all(db.get(TransactionDB, row.id).category_id == own["id"] for row in rows)  # nothing was touched


def test_a_category_can_be_deleted_once_its_transactions_are_gone(
    client, db, user, auth_headers, own, make_transaction
):
    row = make_transaction(user, own["id"])
    assert client.delete(f"/categories/{own['id']}", headers=auth_headers).status_code == 409

    client.delete(f"/transactions/{row.id}", headers=auth_headers)

    assert client.delete(f"/categories/{own['id']}", headers=auth_headers).status_code == 200


def test_a_default_category_cannot_be_deleted_even_when_unused(client, db, auth_headers):
    default = _list(client, auth_headers)["Aluguel"]

    response = client.delete(f"/categories/{default['id']}", headers=auth_headers)
    missing = client.delete("/categories/999999", headers=auth_headers)

    assert response.status_code == 404 and response.json() == missing.json()
    assert "Aluguel" in _list(client, auth_headers)
    assert db.query(Categories).filter_by(id=default["id"]).count() == 1


def test_another_familys_category_cannot_be_deleted(client, db, auth_headers, own, other_user, headers_for):
    response = client.delete(f"/categories/{own['id']}", headers=headers_for(other_user))

    assert response.status_code == 404
    assert "Plantas" in _list(client, auth_headers)


def test_changing_and_deleting_require_login(client, own):
    assert client.patch(f"/categories/{own['id']}", json={"name": "x"}).status_code in (401, 403)
    assert client.delete(f"/categories/{own['id']}").status_code in (401, 403)


# --- emoji in the name -------------------------------------------------------------------------------------


def test_a_name_may_start_with_an_emoji_and_is_kept_as_typed(client, auth_headers):
    created = _post(client, auth_headers, name="  🌱 Plantas ").json()["data"]

    assert created["name"] == "🌱 Plantas"
    assert "🌱 Plantas" in _list(client, auth_headers)


@pytest.mark.parametrize("name", ["🛒", "🛒 ", "🧑\u200d💻"])
def test_a_name_with_only_an_emoji_is_refused(client, auth_headers, name):
    response = _post(client, auth_headers, name=name)

    assert response.status_code == 422
    assert response.json()["detail"] == "O nome da categoria não pode ficar vazio."


@pytest.mark.parametrize("name", ["Plantas", "🌿 plantas", "  🌱   PLANTAS "])
def test_the_emoji_does_not_make_a_name_different_for_the_duplicate_check(client, auth_headers, name):
    _post(client, auth_headers, name="🌱 Plantas")

    assert _post(client, auth_headers, name=name).status_code == 409


def test_a_name_cannot_clash_with_a_default_category_that_has_an_emoji(client, db, auth_headers):
    group = db.query(CategoryGroups).filter_by(name="Alimentação").one()
    db.add(Categories(name="🛒 Mercado do bairro", group_id=group.id))
    db.commit()

    assert _post(client, auth_headers, name="mercado do bairro").status_code == 409
    assert _post(client, auth_headers, name="🏪 Mercado do bairro").status_code == 409


def test_renaming_can_add_change_or_drop_the_emoji_without_clashing_with_itself(client, auth_headers, own):
    for new_name in ["🌱 Plantas", "🪴 Plantas", "Plantas"]:
        response = _patch(client, auth_headers, own["id"], name=new_name)

        assert response.status_code == 200
        assert response.json()["data"]["name"] == new_name


@pytest.mark.parametrize(
    "name",
    ["Alimentação\u200b", "Alimenta\u200bção", "Alimentac\u0327a\u0303o", "  alimentação  ", "🍴 ALIMENTAÇÃO"],
)
def test_a_look_alike_of_a_default_name_is_refused(client, auth_headers, name):
    """ "Alimentação" is a default in the test database. Invisible characters, accents written in two parts and
    emoji must not get a second category that looks identical."""
    assert _post(client, auth_headers, name=name).status_code == 409


@pytest.mark.parametrize("name", ["\u200b", "🛒\u200b", "\u200d"])
def test_a_name_with_nothing_visible_is_refused_as_empty(client, auth_headers, name):
    response = _post(client, auth_headers, name=name)

    assert response.status_code == 422
    assert response.json()["detail"] == "O nome da categoria não pode ficar vazio."


def test_a_category_that_a_transaction_takes_while_it_is_being_deleted_is_in_use_not_a_server_error(
    client, user, auth_headers, own, monkeypatch
):
    """The count said 0, then a transaction took the category before the delete: the database refuses the delete."""
    from api.controllers import categories_controller
    from schemas.tables import TransactionDB

    real = categories_controller.count_transactions_using
    calls = []

    def stale_then_real(session, category_id):
        calls.append(category_id)
        if len(calls) == 1:
            # What another request did between the count and the delete, in the same transaction here
            session.add(
                TransactionDB(family_id=user.family_id, user_id=user.id, label="late", value=1, category_id=category_id)
            )
            session.flush()
            return 0
        return real(session, category_id)

    monkeypatch.setattr(categories_controller, "count_transactions_using", stale_then_real)

    response = client.delete(f"/categories/{own['id']}", headers=auth_headers)

    assert response.status_code == 409
    assert "Mude a categoria" in response.json()["detail"]
    assert "Plantas" in _list(client, auth_headers)
