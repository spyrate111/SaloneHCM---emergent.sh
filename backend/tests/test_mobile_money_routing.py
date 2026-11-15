"""Offline checks for employee-level routing of SLE mobile-money batches."""
from routers.mobile_money import _route_mobile_money_recipients


def _employee(employee_id, preference="auto", orange="", afri=""):
    return {
        "id": employee_id,
        "first_name": employee_id,
        "last_name": "Staff",
        "mobile_money_provider": preference,
        "orange_money_number": orange,
        "afrimoney_number": afri,
    }


def _slip(employee_id, net=1000):
    return {"employee_id": employee_id, "employee_name": employee_id, "net": net}


def test_auto_routes_single_wallets_and_excludes_bank_paid_staff():
    employees = {
        "orange": _employee("orange", orange="+23276123456"),
        "afri": _employee("afri", afri="+23230123456"),
        "bank": _employee("bank", preference="none", orange="+23276111111"),
    }
    slips = [_slip("orange"), _slip("afri"), _slip("bank")]

    orange_rows, orange_invalid, orange_ambiguous, orange_excluded = _route_mobile_money_recipients(
        slips, employees, "orange_money", "2026-10",
    )
    afri_rows, afri_invalid, afri_ambiguous, afri_excluded = _route_mobile_money_recipients(
        slips, employees, "afrimoney", "2026-10",
    )

    assert [row["employee_id"] for row in orange_rows] == ["orange"]
    assert [row["employee_id"] for row in afri_rows] == ["afri"]
    assert (orange_invalid, orange_ambiguous, orange_excluded) == (0, 0, 2)
    assert (afri_invalid, afri_ambiguous, afri_excluded) == (0, 0, 2)


def test_employee_with_both_wallets_needs_explicit_preference():
    rows, invalid, ambiguous, excluded = _route_mobile_money_recipients(
        [_slip("both")],
        {"both": _employee("both", orange="+23276123456", afri="+23230123456")},
        "orange_money",
        "2026-10",
    )

    assert rows == []
    assert (invalid, ambiguous, excluded) == (0, 1, 0)


def test_explicit_provider_routes_employee_with_both_wallets():
    rows, invalid, ambiguous, excluded = _route_mobile_money_recipients(
        [_slip("both")],
        {"both": _employee("both", preference="afrimoney", orange="+23276123456", afri="+23230123456")},
        "afrimoney",
        "2026-10",
    )

    assert rows[0]["mobile_number"] == "+23230123456"
    assert rows[0]["payment_reference"].startswith("SHCM-202610-")
    assert (invalid, ambiguous, excluded) == (0, 0, 0)


def test_duplicate_slips_and_invalid_selected_wallet_are_rejected():
    duplicate_rows, duplicate_invalid, _, _ = _route_mobile_money_recipients(
        [_slip("one"), _slip("one")],
        {"one": _employee("one", orange="+23276123456")},
        "orange_money",
        "2026-10",
    )
    invalid_rows, invalid_count, _, _ = _route_mobile_money_recipients(
        [_slip("bad"), _slip("tiny", net=0.004)],
        {
            "bad": _employee("bad", preference="orange_money", orange="not-a-number"),
            "tiny": _employee("tiny", orange="+23276123457"),
        },
        "orange_money",
        "2026-10",
    )

    assert len(duplicate_rows) == 1
    assert duplicate_invalid == 1
    assert invalid_rows == []
    assert invalid_count == 2
