import pytest

from api.controllers.auth_controller import create_jwt
from schemas.tables import Users


def test_me_returns_the_logged_in_user_and_not_someone_else(client, user, other_user, headers_for):
    mine = client.get("/user/me", headers=headers_for(user)).json()["data"]
    theirs = client.get("/user/me", headers=headers_for(other_user)).json()["data"]

    assert (mine["id"], mine["email"]) == (user.id, user.email)
    assert (theirs["id"], theirs["email"]) == (other_user.id, other_user.email)


def test_me_requires_authentication(client):
    assert client.get("/user/me").status_code == 401


def test_me_for_a_token_of_a_deleted_user_is_not_found(client, db):
    token = create_jwt(999_999)

    response = client.get("/user/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 404


def test_update_phone_is_saved(client, db, user, auth_headers):
    response = client.patch("/user/me/phone", json={"whatsapp_phone": "5511999999999"}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["data"]["whatsapp_phone"] == "5511999999999"
    db.expire_all()
    assert db.get(Users, user.id).whatsapp_phone == "5511999999999"


def test_update_phone_only_changes_the_caller(client, db, user, other_user, auth_headers):
    client.patch("/user/me/phone", json={"whatsapp_phone": "5511999999999"}, headers=auth_headers)

    db.expire_all()
    assert db.get(Users, other_user.id).whatsapp_phone is None


def test_update_phone_requires_authentication(client):
    assert client.patch("/user/me/phone", json={"whatsapp_phone": "1"}).status_code == 401


def test_update_phone_for_a_deleted_user_is_not_found(client):
    token = create_jwt(999_999)

    response = client.patch(
        "/user/me/phone", json={"whatsapp_phone": "5511999999999"}, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404


def test_phone_number_cannot_be_claimed_by_two_users(client, user, other_user, headers_for):
    number = {"whatsapp_phone": "5511999999999"}
    assert client.patch("/user/me/phone", json=number, headers=headers_for(user)).status_code == 200

    response = client.patch("/user/me/phone", json=number, headers=headers_for(other_user))

    assert response.status_code == 409


def test_the_second_user_is_refused_and_the_first_keeps_the_number(client, db, user, other_user, headers_for):
    number = {"whatsapp_phone": "5511999999999"}
    client.patch("/user/me/phone", json=number, headers=headers_for(user))

    client.patch("/user/me/phone", json=number, headers=headers_for(other_user))

    db.expire_all()
    assert db.get(Users, user.id).whatsapp_phone == "5511999999999"
    assert db.get(Users, other_user.id).whatsapp_phone is None


def test_the_same_number_written_differently_is_still_the_same_number(client, db, user, other_user, headers_for):
    client.patch("/user/me/phone", json={"whatsapp_phone": "5511999999999"}, headers=headers_for(user))

    response = client.patch(
        "/user/me/phone", json={"whatsapp_phone": "+55 (11) 99999-9999"}, headers=headers_for(other_user)
    )

    assert response.status_code == 409


def test_a_user_can_save_their_own_number_again(client, user, auth_headers):
    number = {"whatsapp_phone": "5511999999999"}
    client.patch("/user/me/phone", json=number, headers=auth_headers)

    assert client.patch("/user/me/phone", json=number, headers=auth_headers).status_code == 200


def test_the_number_is_stored_as_digits_only(client, db, user, auth_headers):
    client.patch("/user/me/phone", json={"whatsapp_phone": "+55 (11) 99999-9999"}, headers=auth_headers)

    db.expire_all()
    assert db.get(Users, user.id).whatsapp_phone == "5511999999999"


@pytest.mark.parametrize("bad", ["abc", "123", "1" * 16])
def test_something_that_is_not_a_phone_number_is_refused(client, db, user, auth_headers, bad):
    response = client.patch("/user/me/phone", json={"whatsapp_phone": bad}, headers=auth_headers)

    assert response.status_code == 422
    db.expire_all()
    assert db.get(Users, user.id).whatsapp_phone is None
