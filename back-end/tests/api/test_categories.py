from schemas.tables import Categories


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
