import pytest
import serp
import tracker
from agents import GraphAgent, AnalystAgent, Orchestrator

SHOPS = [
    {"place_id": "a", "title": "Cafe Alpha", "type": "Coffee shop", "address": "1 Road, Koregaon Park, Pune, India",
     "rating": 4.6, "reviews": 300, "phone": "123", "website": "x.com", "open_state": "Open", "lat": 18.5, "lon": 73.8},
    {"place_id": "b", "title": "Beta Brews", "type": "Coffee shop", "address": "2 Road, Baner, Pune, India",
     "rating": 4.2, "reviews": 900, "phone": None, "website": None, "open_state": "Closed", "lat": 18.6, "lon": 73.9},
]
KGS = {"a": {"title": "Cafe Alpha", "description": "A popular cafe."}}
NEWS = {"a": [{"title": "Alpha opens", "link": "http://l", "source": "TOI", "date": "today", "snippet": ""}]}


class FakeResp:
    def __init__(self, data, status=200):
        self._d, self.status_code = data, status

    def json(self):
        return self._d


@pytest.fixture
def graph():
    return GraphAgent().run(SHOPS, KGS, NEWS)


# ---------- serp.py ----------
def test_maps_search_parses(monkeypatch):
    payload = {"local_results": [{"title": "X", "place_id": "p1", "type": "Cafe", "rating": 4.5, "reviews": 10,
                                  "gps_coordinates": {"latitude": 1.0, "longitude": 2.0}}]}
    monkeypatch.setattr(serp.requests, "get", lambda *a, **k: FakeResp(payload))
    out = serp.maps_search("cafe", "Pune", "KEY")
    assert out[0]["title"] == "X" and out[0]["lat"] == 1.0


def test_missing_key_raises():
    with pytest.raises(serp.SerpError):
        serp.maps_search("cafe", "Pune", "")


def test_api_error_raises(monkeypatch):
    monkeypatch.setattr(serp.requests, "get", lambda *a, **k: FakeResp({"error": "Invalid API key"}, 401))
    with pytest.raises(serp.SerpError):
        serp.knowledge_graph("x", "bad")


def test_news_flattens_stories(monkeypatch):
    payload = {"news_results": [{"stories": [{"title": "S1", "link": "l1", "source": {"name": "A"}, "date": "d"}]},
                                {"title": "S2", "link": "l2", "source": {"name": "B"}, "date": "d"}]}
    monkeypatch.setattr(serp.requests, "get", lambda *a, **k: FakeResp(payload))
    assert [a["title"] for a in serp.news_search("q", "KEY")] == ["S1", "S2"]


# ---------- graph ----------
def test_graph_structure(graph):
    kinds = {d["kind"] for _, d in graph.G.nodes(data=True)}
    assert {"shop", "category", "area", "entity", "news"} <= kinds


def test_retrieve_returns_context(graph):
    ctx = graph.retrieve("Alpha news")
    assert "Cafe Alpha" in ctx and "## Relations" in ctx


# ---------- analyst ----------
def test_best_rating_ranks_first(graph):
    ans, _ = AnalystAgent().run("which has the best rating", graph)
    assert ans.index("Cafe Alpha") < ans.index("Beta Brews")


def test_news_intent(graph):
    ans, _ = AnalystAgent().run("latest news", graph)
    assert "Alpha opens" in ans


def test_named_shop_filters(graph):
    ans, _ = AnalystAgent().run("phone of Alpha", graph)
    assert "Cafe Alpha" in ans and "Beta Brews" not in ans


# ---------- tracker ----------
def test_tracker_detects_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "FILE", tmp_path / "t.json")
    tracker.save_snapshot("k", SHOPS)
    changed = [dict(SHOPS[0], rating=4.0), SHOPS[1]]
    tracker.save_snapshot("k", changed)
    diffs = tracker.diff_last_two("k")
    assert any("rating: 4.6 -> 4.0" in d["change"] for d in diffs)


# ---------- orchestrator ----------
def test_orchestrator_pipeline(monkeypatch):
    monkeypatch.setattr(serp, "maps_search", lambda *a, **k: SHOPS)
    monkeypatch.setattr(serp, "knowledge_graph", lambda *a, **k: {"title": "T", "description": "d"})
    monkeypatch.setattr(serp, "news_search", lambda *a, **k: NEWS["a"])
    shops, kgs, news, g = Orchestrator().build("cafe", "Pune", "KEY", top_n=2)
    assert len(shops) == 2 and g.G.number_of_nodes() > 2
