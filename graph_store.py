"""Knowledge graph (networkx) + graph-based retrieval for GraphRAG."""
import hashlib
import re
import networkx as nx

COLORS = {"shop": "#4CAF50", "category": "#FFC107", "area": "#03A9F4",
          "entity": "#E91E63", "news": "#9C27B0"}


def _hid(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()[:10]


class ShopGraph:
    def __init__(self):
        self.G = nx.DiGraph()

    def _node(self, nid, kind, label, text, **extra):
        self.G.add_node(nid, kind=kind, label=label, text=text, **extra)

    def add_shop(self, s: dict):
        sid = f"shop:{s['place_id']}"
        text = (f"{s['title']} | {s['type']} | {s['address']} | rating {s['rating']} "
                f"({s['reviews']} reviews) | {s['open_state']} | {s['phone'] or ''} | {s['website'] or ''}")
        self._node(sid, "shop", s["title"], text, data=s)
        cat = f"cat:{(s['type'] or 'Shop').lower()}"
        self._node(cat, "category", s["type"] or "Shop", f"category {s['type']}")
        self.G.add_edge(sid, cat, rel="IN_CATEGORY")
        parts = [p.strip() for p in (s["address"] or "").split(",") if p.strip()]
        if len(parts) >= 2:
            area = f"area:{parts[-2].lower()}"
            self._node(area, "area", parts[-2], f"area {parts[-2]}")
            self.G.add_edge(sid, area, rel="LOCATED_IN")
        return sid

    def add_entity(self, shop_id: str, kg: dict):
        if not kg or not kg.get("title"):
            return
        eid = f"entity:{_hid(kg['title'])}"
        facts = "; ".join(f"{k}: {v}" for k, v in kg.items()
                          if isinstance(v, (str, int, float)) and k not in ("kgmid", "knowledge_graph_search_link"))
        self._node(eid, "entity", kg["title"], f"Knowledge Graph: {facts}", data=kg)
        self.G.add_edge(shop_id, eid, rel="HAS_KNOWLEDGE_PROFILE")

    def add_news(self, shop_id: str, articles: list[dict]):
        for a in articles:
            if not a.get("title"):
                continue
            nid = f"news:{_hid(a.get('link') or a['title'])}"
            self._node(nid, "news", a["title"][:60],
                       f"News: {a['title']} ({a.get('source')}, {a.get('date')}) {a.get('snippet','')} {a.get('link','')}",
                       data=a)
            self.G.add_edge(nid, shop_id, rel="MENTIONS")

    # ---------- GraphRAG retrieval ----------
    def retrieve(self, question: str, k_seeds: int = 4, hops: int = 2, max_nodes: int = 60) -> str:
        G = self.G
        if not G.number_of_nodes():
            return ""
        toks = {t for t in re.findall(r"\w+", question.lower()) if len(t) > 2}
        scored = sorted(((sum(t in d["text"].lower() for t in toks), n) for n, d in G.nodes(data=True)),
                        reverse=True)
        seeds = [n for s, n in scored[:k_seeds] if s > 0]
        if not seeds:  # generic question -> use all shops
            seeds = [n for n, d in G.nodes(data=True) if d["kind"] == "shop"][:k_seeds]
        sub, frontier = set(seeds), set(seeds)
        for _ in range(hops):
            nxt = set()
            for n in frontier:
                nxt |= set(G.successors(n)) | set(G.predecessors(n))
            sub |= nxt
            frontier = nxt
            if len(sub) >= max_nodes:
                break
        sub = list(sub)[:max_nodes]
        lines = ["## Nodes"] + [f"- [{G.nodes[n]['kind']}] {G.nodes[n]['text']}" for n in sub]
        lines += ["## Relations"] + [f"- {G.nodes[u]['label']} --{d['rel']}--> {G.nodes[v]['label']}"
                                     for u, v, d in G.edges(data=True) if u in sub and v in sub]
        return "\n".join(lines)

    def to_html(self, height="620px") -> str:
        from pyvis.network import Network
        net = Network(height=height, width="100%", directed=True, bgcolor="#0e1117", font_color="white")
        for n, d in self.G.nodes(data=True):
            net.add_node(n, label=d["label"][:28], title=d["text"], color=COLORS[d["kind"]],
                         size=26 if d["kind"] == "shop" else 16)
        for u, v, d in self.G.edges(data=True):
            net.add_edge(u, v, title=d["rel"], color="#888")
        net.toggle_physics(True)
        return net.generate_html()
