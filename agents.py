"""Multi-agent pipeline: Maps -> (Knowledge || News) in parallel -> Graph -> Analyst (graph-based Q&A)."""
from concurrent.futures import ThreadPoolExecutor
import serp
from graph_store import ShopGraph


class MapsAgent:
    name = "MapsAgent"

    def run(self, shop, location, key, ll=None):
        return serp.maps_search(shop, location, key, ll)


class KnowledgeAgent:
    name = "KnowledgeAgent"

    def run(self, shop_title, location, key):
        try:
            return serp.knowledge_graph(f"{shop_title} {location}", key)
        except serp.SerpError:
            return {}


class NewsAgent:
    name = "NewsAgent"

    def run(self, shop_title, key, limit=5):
        try:
            return serp.news_search(shop_title, key, limit)
        except serp.SerpError:
            return []


class GraphAgent:
    name = "GraphAgent"

    def run(self, shops, kgs, news):
        g = ShopGraph()
        for s in shops:
            sid = g.add_shop(s)
            g.add_entity(sid, kgs.get(s["place_id"]))
            g.add_news(sid, news.get(s["place_id"], []))
        return g


class AnalystAgent:
    """Answers questions by traversing the knowledge graph (GraphRAG, no LLM needed)."""
    name = "AnalystAgent"

    @staticmethod
    def _has(q, words):
        return any(w in q for w in words)

    def run(self, question, graph: ShopGraph):
        ctx = graph.retrieve(question)
        if not ctx:
            return "No graph data yet. Run a search first.", ctx
        G, q = graph.G, question.lower()

        shops = [(n, d["data"]) for n, d in G.nodes(data=True) if d["kind"] == "shop"]
        named = [(n, s) for n, s in shops if any(w in q for w in (s["title"] or "").lower().split() if len(w) > 3)]
        targets = named or shops

        def news_of(n):
            return [G.nodes[p]["data"] for p in G.predecessors(n) if G.nodes[p]["kind"] == "news"]

        def kg_of(n):
            return next((G.nodes[x]["data"] for x in G.successors(n) if G.nodes[x]["kind"] == "entity"), {})

        def rank(items):
            return sorted(items, key=lambda t: ((t[1].get("rating") or 0), (t[1].get("reviews") or 0)), reverse=True)

        out = []
        if self._has(q, ["best", "top", "highest", "compare", " vs ", "versus", "rating", "popular", "rank"]):
            out.append("### Ranking by rating, then review count")
            out.append("| # | Shop | Rating | Reviews | Area/Address | News |")
            out.append("|---|---|---|---|---|---|")
            for i, (n, s) in enumerate(rank(targets), 1):
                out.append(f"| {i} | {s['title']} | {s.get('rating')} | {s.get('reviews')} | {s.get('address')} | {len(news_of(n))} |")
        elif self._has(q, ["news", "latest", "recent", "article", "headline"]):
            out.append("### Latest news per shop")
            for n, s in targets:
                arts = news_of(n)
                out.append(f"**{s['title']}**" + ("" if arts else " - no news found"))
                out += [f"- [{a['title']}]({a['link']}) - *{a['source']}*, {a['date']}" for a in arts]
        elif self._has(q, ["phone", "call", "contact", "website", "site", "number"]):
            out.append("### Contact details")
            for n, s in targets:
                out.append(f"- **{s['title']}** - phone: {s.get('phone') or 'n/a'} - website: {s.get('website') or 'n/a'}")
        elif self._has(q, ["open", "hours", "closed", "closing", "timing"]):
            out.append("### Opening status")
            out += [f"- **{s['title']}**: {s.get('open_state') or 'not listed'}" for n, s in targets]
        elif self._has(q, ["where", "address", "location", "area", "near", "locat"]):
            out.append("### Locations")
            for n, s in targets:
                areas = [G.nodes[x]["label"] for x in G.successors(n) if G.nodes[x]["kind"] == "area"]
                out.append(f"- **{s['title']}** - {s.get('address')} ({', '.join(areas) or 'area n/a'}) - "
                           f"coords: {s.get('lat')}, {s.get('lon')}")
        else:
            out.append("### Shop profiles from the knowledge graph")
            for n, s in targets:
                kg = kg_of(n)
                desc = kg.get("description") or "No Knowledge Graph description."
                out.append(f"**{s['title']}** ({s.get('type')}) - rating {s.get('rating')} from {s.get('reviews')} reviews")
                out.append(f"- {s.get('address')}")
                out.append(f"- Knowledge Graph: {desc}")
                out.append(f"- {len(news_of(n))} news article(s) linked")
        return "\n".join(out), ctx


class Orchestrator:
    def __init__(self):
        self.maps, self.kg, self.news = MapsAgent(), KnowledgeAgent(), NewsAgent()
        self.graph_agent, self.analyst = GraphAgent(), AnalystAgent()

    def build(self, shop, location, key, top_n=6, ll=None, log=lambda m: None):
        log(f"{self.maps.name}: searching Google Maps...")
        shops = self.maps.run(shop, location, key, ll)[:top_n]
        kgs, news = {}, {}
        log(f"{self.kg.name} + {self.news.name}: enriching {len(shops)} shops in parallel...")
        with ThreadPoolExecutor(max_workers=6) as ex:
            kf = {s["place_id"]: ex.submit(self.kg.run, s["title"], location, key) for s in shops}
            nf = {s["place_id"]: ex.submit(self.news.run, s["title"], key) for s in shops}
            kgs = {k: f.result() for k, f in kf.items()}
            news = {k: f.result() for k, f in nf.items()}
        log(f"{self.graph_agent.name}: building knowledge graph...")
        graph = self.graph_agent.run(shops, kgs, news)
        return shops, kgs, news, graph
