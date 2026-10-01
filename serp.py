"""Thin SerpApi wrappers: Google Maps, Google (Knowledge Graph), Google News."""
import requests

BASE = "https://serpapi.com/search"


class SerpError(Exception):
    pass


def _get(params: dict, api_key: str) -> dict:
    if not api_key:
        raise SerpError("SERPAPI_API_KEY is missing.")
    r = requests.get(BASE, params={**params, "api_key": api_key, "output": "json"}, timeout=60)
    try:
        data = r.json()
    except ValueError:
        raise SerpError(f"Non-JSON response ({r.status_code})")
    if r.status_code != 200 or data.get("error"):
        raise SerpError(data.get("error", f"HTTP {r.status_code}"))
    return data


def maps_search(shop: str, location: str, api_key: str, ll: str | None = None) -> list[dict]:
    """engine=google_maps -> list of normalised shops."""
    params = {"engine": "google_maps", "type": "search", "q": f"{shop} in {location}", "hl": "en"}
    if ll:  # e.g. "@18.5204,73.8567,14z"
        params["ll"] = ll
    data = _get(params, api_key)
    raw = data.get("local_results") or ([data["place_results"]] if data.get("place_results") else [])
    shops = []
    for p in raw:
        gps = p.get("gps_coordinates") or {}
        shops.append({
            "place_id": p.get("place_id") or p.get("data_id") or p.get("title"),
            "title": p.get("title"),
            "type": p.get("type") or (p.get("types") or ["Shop"])[0],
            "address": p.get("address", ""),
            "rating": p.get("rating"),
            "reviews": p.get("reviews"),
            "phone": p.get("phone"),
            "website": p.get("website"),
            "open_state": p.get("open_state") or p.get("hours", ""),
            "lat": gps.get("latitude"),
            "lon": gps.get("longitude"),
        })
    return shops


def knowledge_graph(query: str, api_key: str) -> dict:
    """engine=google -> knowledge_graph block (may be empty)."""
    data = _get({"engine": "google", "q": query, "hl": "en"}, api_key)
    return data.get("knowledge_graph") or {}


def news_search(query: str, api_key: str, limit: int = 8) -> list[dict]:
    """engine=google_news -> flattened articles."""
    data = _get({"engine": "google_news", "q": query, "hl": "en"}, api_key)
    out = []
    for item in data.get("news_results", []):
        items = item.get("stories") or [item]
        for a in items:
            src = a.get("source") or {}
            out.append({
                "title": a.get("title"),
                "link": a.get("link"),
                "source": src.get("name") if isinstance(src, dict) else src,
                "date": a.get("date"),
                "snippet": a.get("snippet", ""),
            })
    return out[:limit]