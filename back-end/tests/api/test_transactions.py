def _create(client, headers, category_id, label="Almoço", value=2500):
    return client.post(
        "/transactions/create",
        json={"label": label, "value": value, "category_id": category_id},
        headers=headers,
    )


def test_create_then_list(client, auth_headers, category_id):
    assert _create(client, auth_headers, category_id).status_code == 201

    response = client.post("/transactions/", json={}, headers=auth_headers)

    assert response.status_code == 200
    rows = response.json()["data"]
    assert [(r["label"], r["value"]) for r in rows] == [("Almoço", 2500)]


def test_summed_by_category(client, auth_headers, category_id):
    _create(client, auth_headers, category_id, value=1000)
    _create(client, auth_headers, category_id, value=2500)

    response = client.post("/transactions/summed-by-category", json={}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["data"] == [{"category_id": category_id, "total": 3500}]


def test_delete_removes_the_transaction(client, auth_headers, category_id):
    _create(client, auth_headers, category_id)
    created = client.post("/transactions/", json={}, headers=auth_headers).json()["data"][0]

    response = client.delete(f"/transactions/{created['id']}", headers=auth_headers)

    assert response.status_code == 202
    assert client.post("/transactions/", json={}, headers=auth_headers).json()["data"] == []


def test_users_only_see_their_own_transactions(client, other_user, auth_headers, category_id):
    from api.controllers.auth_controller import create_jwt

    _create(client, auth_headers, category_id, label="Mine")
    other_headers = {"Authorization": f"Bearer {create_jwt(other_user.id)}"}

    response = client.post("/transactions/", json={}, headers=other_headers)

    assert response.json()["data"] == []
