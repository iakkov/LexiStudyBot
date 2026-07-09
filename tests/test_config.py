from lexibot.config import parse_admin_user_ids


def test_parse_admin_user_ids_ignores_empty_items():
    assert parse_admin_user_ids("123, 456,") == {123, 456}


def test_parse_admin_user_ids_allows_empty_value():
    assert parse_admin_user_ids("") == set()
