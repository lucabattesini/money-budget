"""Identifiers are random UUIDs, not counting numbers (TKT-74)."""

from uuid import UUID

import pytest

from tests.conftest import MISSING_ID


def test_a_new_transaction_gets_a_uuid_that_does_not_reveal_how_many_exist(client, auth_headers, category_ids):
    for label in ("a", "b", "c"):
        response = client.post(
            "/transactions/create",
            json={"label": label, "value": 100, "category_id": category_ids["Sem categoria"]},
            headers=auth_headers,
        )
        assert response.status_code == 201, response.text
    ids = [t["id"] for t in client.post("/transactions/", json={}, headers=auth_headers).json()["data"]]

    assert [UUID(i).version for i in ids] == [4, 4, 4]  # random, not counting
    assert len(set(ids)) == 3


@pytest.mark.parametrize(
    "method, path",
    [
        ("delete", "/transactions/42"),
        ("put", "/transactions/42"),
        ("get", "/exports/42"),
        ("get", "/imports/42"),
        ("delete", "/categories/42"),
        ("delete", "/merchants/42"),
        ("delete", "/families/invites/42"),
    ],
)
def test_a_counting_number_is_not_an_id_any_more(client, auth_headers, method, path):
    response = getattr(client, method)(path, headers=auth_headers, **({"json": {}} if method == "put" else {}))

    assert response.status_code == 422  # a clear refusal, never a server error


def test_a_well_formed_id_nobody_has_is_not_found_and_so_is_another_familys(
    client, auth_headers, headers_for, other_user, make_transaction, category_ids
):
    theirs = make_transaction(other_user, category_ids["Sem categoria"], "theirs", 100)

    assert client.delete(f"/transactions/{MISSING_ID}", headers=auth_headers).status_code == 404
    assert client.delete(f"/transactions/{theirs.id}", headers=auth_headers).status_code == 404  # same answer
    assert client.delete(f"/transactions/{theirs.id}", headers=headers_for(other_user)).status_code == 202


def test_the_ids_in_a_body_must_be_uuids_too(client, auth_headers):
    response = client.post(
        "/transactions/create", json={"label": "x", "value": 100, "category_id": 7}, headers=auth_headers
    )

    assert response.status_code == 422
