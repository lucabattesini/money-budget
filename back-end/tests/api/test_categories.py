def test_lists_categories(client):
    response = client.get("/categories/")

    assert response.status_code == 200
    names = {c["name"] for c in response.json()["data"]}
    assert {"Alimentação", "Transporte", "Outros"} <= names
