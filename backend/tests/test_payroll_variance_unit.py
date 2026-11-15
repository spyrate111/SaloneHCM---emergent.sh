"""Offline unit tests for payroll variance and anomaly-review helpers."""

from routers.payroll_variance import _detect_anomalies, _resurrected_anomalies


def _run(period, employee_ids):
    return {
        "period": period,
        "slips": [{"employee_id": employee_id} for employee_id in employee_ids],
    }


def _employee(hire_date, status="active"):
    return {
        "hire_date": hire_date,
        "status": status,
        "first_name": "Aminata",
        "last_name": "Kamara",
        "nassit_no": "",
        "tin": "",
    }


def test_resurrected_flags_long_tenured_employee_absent_from_two_latest_periods():
    current = {
        "emp-1": {"employee_name": "Aminata Kamara", "net": 5200},
    }
    history = [
        _run("2026-09", ["emp-2"]),
        _run("2026-08", ["emp-2"]),
    ]

    anomalies = _resurrected_anomalies(
        current,
        history,
        {"emp-1": _employee("2020-01-01")},
    )

    assert len(anomalies) == 1
    assert anomalies[0]["kind"] == "resurrected"
    assert anomalies[0]["employee_id"] == "emp-1"
    assert anomalies[0]["periods_absent"] == ["2026-09", "2026-08"]


def test_resurrected_does_not_flag_recent_hire_or_terminated_employee():
    current = {
        "recent": {"employee_name": "Recent hire", "net": 1000},
        "terminated": {"employee_name": "Former staff", "net": 1000},
    }
    history = [
        _run("2026-09", ["another"]),
        _run("2026-08", ["another"]),
    ]
    employees = {
        "recent": _employee("2026-08-15"),
        "terminated": _employee("2020-01-01", status="terminated"),
    }

    assert _resurrected_anomalies(current, history, employees) == []


def test_resurrected_requires_two_distinct_populated_periods():
    current = {"emp-1": {"employee_name": "Aminata Kamara", "net": 5200}}
    employee_index = {"emp-1": _employee("2020-01-01")}

    assert _resurrected_anomalies(
        current,
        [_run("2026-09", ["emp-2"]), _run("2026-08", [])],
        employee_index,
    ) == []
    assert _resurrected_anomalies(
        current,
        [_run("2026-09", ["emp-2"]), _run("2026-09", ["emp-2"])],
        employee_index,
    ) == []


def test_detector_emits_resurrected_signal_without_duplicate_late_starter():
    current_slips = [
        {
            "employee_id": "emp-1",
            "employee_name": "Aminata Kamara",
            "gross": 6000,
            "net": 5200,
        },
    ]
    history = [
        _run("2026-09", ["emp-2"]),
        _run("2026-08", ["emp-2"]),
    ]

    anomalies = _detect_anomalies(
        current_slips,
        [],
        {"emp-1": _employee("2020-01-01")},
        "2026-10",
        history,
    )
    kinds = [item["kind"] for item in anomalies]

    assert kinds.count("resurrected") == 1
    assert "new_starter" not in kinds
