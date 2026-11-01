def test_lists_exactly_the_seeded_categories(client):
    response = client.get("/categories/")

    assert response.status_code == 200
    names = sorted(c["name"] for c in response.json()["data"])
    assert names == ["Alimentação", "Aluguel", "Outros", "Supermercado", "Transporte"]


def test_each_category_has_an_id_and_name(client):
    category = client.get("/categories/").json()["data"][0]

    assert set(category) >= {"id", "name"}
    assert isinstance(category["id"], int)
