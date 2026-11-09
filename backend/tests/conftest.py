import pytest
from fastapi.testclient import TestClient

from api.factory import create_app
from content import Catalog


@pytest.fixture(scope="session")
def catalog():
    return Catalog()


@pytest.fixture()
def client(tmp_path):
    app = create_app(store_path=tmp_path / "store.json", offline=True)
    with TestClient(app) as c:
        c.svc = app.state.svc
        yield c


def answer_as(student_gap, catalog, probe):
    """Choose the right option unless the concept is the gap or depends on it."""
    c = probe["conceptId"]
    knows = not (c == student_gap or student_gap in catalog.graph.ancestors(c))
    full = catalog.probes[probe["probeId"]]
    return full["correctIndex"] if knows else (full["correctIndex"] + 1) % len(full["options"])
