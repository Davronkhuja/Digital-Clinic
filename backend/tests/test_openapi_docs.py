"""Ochiq API hujjati: OpenAPI sxemasi to'liq va himoya sxemasi e'lon qilingan."""
from app import __version__


def test_openapi_is_documented(client):
    spec = client.get("/openapi.json").json()
    assert spec["info"]["version"] == __version__
    desc = spec["info"]["description"]
    for word in ("Authorization: Bearer", "X-Branch-Id", "/exports/{dataset}", "/reports/analytics/{kind}"):
        assert word in desc
    assert spec["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    ops = [(p, m, o) for p, item in spec["paths"].items() for m, o in item.items()]
    assert len(ops) > 150
    assert all(o.get("summary") and o.get("tags") for _, _, o in ops)
    for path in ("/auth/login", "/exports/{dataset}", "/insurance/registry", "/reports/analytics/{kind}", "/emr/{record_id}/ai-summary"):
        assert path in spec["paths"], path
    assert client.get("/docs").status_code == 200
