"""Dashboard, tahlil va hisobotlar filial bo'yicha (v1.9.8); administrator uchun hamma filial birga."""
import csv
import io

import pytest

from tests.test_patients import NEW

pytestmark = pytest.mark.usefixtures("desk")


def _on(h, branch_id):
    return {**h, "X-Branch-Id": branch_id}


@pytest.fixture
def two(client, auth):
    admin = auth("admin")
    b = client.post("/branches", json={"name": "Hisobot filiali"}, headers=admin).json()
    return admin, _on(admin, b["id"]), b["id"]


def test_dashboard_and_reports_follow_branch_and_all_branches(client, auth, two):
    admin, other, _ = two
    main = client.get("/analytics/dashboard", params={"period": "all"}, headers=admin).json()
    empty = client.get("/analytics/dashboard", params={"period": "all"}, headers=other).json()
    assert main["appointments"] > 0 and main["revenue"] > 0 and main["active_doctors"] > 0 and main["total_patients"] > 0
    assert (empty["appointments"], empty["revenue"], empty["expense"], empty["active_doctors"], empty["total_patients"]) == (0, 0, 0, 0, 0)
    assert all(d["new"] == 0 and d["returning"] == 0 for d in empty["patient_flow"]) and all(m["value"] == 0 for m in empty["revenue_chart"])
    both = client.get("/analytics/dashboard", params={"period": "all", "all_branches": True}, headers=other).json()    # faol filial bo'sh, jami asosiy bilan teng
    assert both["appointments"] == main["appointments"] and both["revenue"] == main["revenue"]
    rep_main = client.get("/analytics/reports", params={"period": "all"}, headers=admin).json()
    rep_empty = client.get("/analytics/reports", params={"period": "all"}, headers=other).json()
    assert rep_main["top_doctors"] and rep_empty["top_doctors"] == [] and rep_empty["top_diagnoses"] == []
    assert sum(rep_empty["appointment_statuses"].values()) == 0 and rep_empty["patient_demographics"]["total"] == 0
    assert client.get("/analytics/no-show", headers=other).json()["current"]["total"] == 0
    assert client.get("/ai/insights", headers=other).status_code == 200


def test_all_branches_requires_permission_and_new_branch_data_is_isolated(client, auth, two):
    admin, other, bid = two
    assert client.get("/analytics/dashboard", params={"all_branches": True}, headers=auth("doctor")).status_code == 403
    doc = client.post("/users", headers=admin, json={"name": "Dr. Hisobot", "email": "dr.h@clinic.uz", "password": "password123", "role": "doctor",
                                                      "branch_id": bid}).json()
    pid = client.post("/patients", json={**NEW, "name": "Filial Hisobot Bemor"}, headers=other).json()["id"]
    assert client.post("/appointments", headers=other, json={"patient_id": pid, "doctor": doc["name"], "date": "2030-02-11", "time": "10:00",
                                                             "type": "Konsultatsiya", "override_reason": "test"}).status_code == 201
    here = client.get("/analytics/dashboard", params={"period": "all"}, headers=other).json()
    assert (here["appointments"], here["active_doctors"], here["total_patients"]) == (1, 1, 1)
    main = client.get("/analytics/dashboard", params={"period": "all"}, headers=admin).json()
    total = client.get("/analytics/dashboard", params={"period": "all", "all_branches": True}, headers=admin).json()
    assert total["appointments"] == main["appointments"] + 1 and total["total_patients"] == main["total_patients"] + 1


def test_report_downloads_are_per_branch(client, auth, two):
    admin, other, _ = two
    def rows(h, rid):
        res = client.get(f"/reports/download/{rid}", headers=h)
        assert res.status_code == 200
        return list(csv.reader(io.StringIO(res.text.lstrip("﻿"))))
    assert len(rows(admin, "4")) > 1 and rows(other, "4") == [] and rows(other, "1") == [] and len(rows(admin, "1")) > 1
    assert len(rows(admin, "3")) > 1 and rows(other, "3") == []
    assert len(rows(other, "2")) > 1                                   # bemorlar statistikasi: bemor bazasi umumiy
