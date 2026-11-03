from datetime import timedelta

import pytest

from app.services.periods import clinic_today, pct_change, previous_window, window
from tests.conftest import seed_essentials_only


def d(days_ago: int) -> str:
    return (clinic_today() - timedelta(days=days_ago)).isoformat()


@pytest.fixture
def empty(client):
    """Faqat boshlang'ich ma'lumotlar (filial, rollar) va bitta administrator: demo ma'lumotlarsiz."""
    seed_essentials_only()
    from tests.conftest import login_admin_only

    return {"Authorization": f"Bearer {login_admin_only(client)}"}


def tx(client, h, kind, amount, days_ago):
    res = client.post("/finance/transactions", headers=h, json={
        "type": kind, "amount": amount, "description": "t", "category": "Lab", "date": d(days_ago)})
    assert res.status_code == 201, res.text


def patient(client, h, name, age=30, gender="male"):
    res = client.post("/patients", headers=h, json={"name": name, "phone": "+998 90 000 0000", "age": age, "gender": gender})
    assert res.status_code == 201, res.text
    return res.json()


def test_pure_helpers():
    today = clinic_today()
    assert window("week", today) == (today - timedelta(days=6), today)
    assert window("all", today) == (None, today)
    assert previous_window("month", today) == (today - timedelta(days=59), today - timedelta(days=30))
    assert previous_window("all", today) is None
    assert pct_change(150, 100) == 50.0 and pct_change(50, 100) == -50.0
    assert pct_change(10, 0) is None


def test_empty_database_gives_zeros_not_errors(client, empty):
    dash = client.get("/analytics/dashboard", headers=empty).json()
    assert dash["total_patients"] == 0 and dash["revenue"] == 0 and dash["appointments"] == 0
    assert dash["changes"] == {"revenue": None, "appointments": None, "new_patients": None}
    assert len(dash["revenue_chart"]) == 6 and all(p["value"] == 0 for p in dash["revenue_chart"])
    assert len(dash["patient_flow"]) == 7
    rep = client.get("/analytics/reports", headers=empty).json()
    assert rep["top_diagnoses"] == [] and rep["top_doctors"] == [] and rep["departments"] == []
    assert rep["patient_demographics"]["total"] == 0
    assert client.get("/ai/insights", headers=empty).json() == {"insights": []}


def test_dashboard_numbers_come_from_the_database(client, empty):
    tx(client, empty, "income", 1000, 2)       # joriy 30 kun
    tx(client, empty, "income", 500, 10)       # joriy 30 kun
    tx(client, empty, "expense", 300, 3)
    tx(client, empty, "income", 750, 40)       # oldingi 30 kun (31..60 kun oldin)
    tx(client, empty, "income", 9999, 200)     # davrdan tashqarida
    patient(client, empty, "Birinchi Bemor")
    patient(client, empty, "Ikkinchi Bemor")

    month = client.get("/analytics/dashboard", params={"period": "month"}, headers=empty).json()
    assert month["revenue"] == 1500 and month["expense"] == 300
    assert month["changes"]["revenue"] == 100.0       # 1500 vs 750
    assert month["total_patients"] == 2 and month["new_patients"] == 2
    assert month["changes"]["new_patients"] is None    # oldingi davrda yangi bemor yo'q

    week = client.get("/analytics/dashboard", params={"period": "week"}, headers=empty).json()
    assert week["revenue"] == 1000
    allp = client.get("/analytics/dashboard", params={"period": "all"}, headers=empty).json()
    assert allp["revenue"] == 1000 + 500 + 750 + 9999 and allp["changes"]["revenue"] is None
    assert len(month["revenue_chart"]) == 6


def test_revenue_chart_sums_match_transactions(client, empty):
    for days in (1, 35, 70):
        tx(client, empty, "income", 100 * days, days)
    chart = client.get("/analytics/dashboard", headers=empty).json()["revenue_chart"]
    assert sum(p["value"] for p in chart) == 100 * (1 + 35 + 70)
    assert [p["month"] for p in chart] == sorted(p["month"] for p in chart)


def test_finance_summary_matches_dashboard_windows(client, empty):
    tx(client, empty, "income", 1000, 2)
    tx(client, empty, "expense", 400, 20)
    tx(client, empty, "income", 300, 100)
    for period, income in (("week", 1000), ("month", 1000), ("year", 1300), ("all", 1300)):
        s = client.get("/finance/summary", params={"period": period}, headers=empty).json()
        dash = client.get("/analytics/dashboard", params={"period": period}, headers=empty).json()
        assert s["total_income"] == income == dash["revenue"], period
    month = client.get("/finance/summary", params={"period": "month"}, headers=empty).json()
    assert month["total_expense"] == 400 and month["net_profit"] == 600 and month["transactions_count"] == 2


def test_reports_diagnoses_doctors_and_demographics(client, empty):
    young = patient(client, empty, "Yosh Bemor", age=10, gender="female")
    adult = patient(client, empty, "Katta Bemor", age=40, gender="male")
    patient(client, empty, "Qari Bemor", age=75, gender="male")
    for diag, who in (("Gipertenziya", adult), ("Gipertenziya", young), ("ARVI", adult)):
        res = client.post("/emr", headers=empty, json={
            "patient_id": who["id"], "doctor": "Administrator", "diagnosis": diag, "prescription": "-", "visit_date": d(1)})
        assert res.status_code == 422  # shifokor yo'q (admin shifokor emas): to'g'ri rad etiladi

    rep = client.get("/analytics/reports", headers=empty).json()
    demo = rep["patient_demographics"]
    assert demo["total"] == 3 and demo["gender"] == {"male": 2, "female": 1, "other": 0}
    groups = {g["label"]: g["count"] for g in demo["age_groups"]}
    assert groups == {"0-17": 1, "18-35": 0, "36-55": 1, "56-70": 0, "70+": 1}
    assert sum(g["pct"] for g in demo["age_groups"]) == pytest.approx(100, abs=0.2)


def test_reports_with_demo_data_are_consistent(client, auth):
    h = auth("admin")
    rep = client.get("/analytics/reports", params={"period": "all"}, headers=h).json()
    statuses = rep["appointment_statuses"]
    assert sum(statuses.values()) == len(client.get("/appointments", headers=h).json())
    assert sum(x["count"] for x in rep["departments"]) == sum(statuses.values())
    assert rep["top_diagnoses"] and rep["top_doctors"][0]["patients"] >= 1
    dash = client.get("/analytics/dashboard", params={"period": "all"}, headers=h).json()
    assert dash["total_patients"] == len(client.get("/patients", params={"limit": 100}, headers=h).json())
    assert dash["active_doctors"] == 3
    assert dash["revenue"] == client.get("/finance/summary", params={"period": "all"}, headers=h).json()["total_income"]


def test_insights_are_computed_not_hardcoded(client, auth):
    messages = " ".join(i["message"] for i in client.get("/ai/insights", headers=auth("admin")).json()["insights"])
    assert "%" in messages and "23%" not in messages  # eski qattiq yozilgan matn yo'q


def test_invalid_period_is_422(client, auth):
    assert client.get("/analytics/dashboard", params={"period": "decade"}, headers=auth("admin")).status_code == 422
    assert client.get("/finance/summary", params={"period": "decade"}, headers=auth("admin")).status_code == 422
