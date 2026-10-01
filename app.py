import os
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

import serp
import tracker
from map_view import build_map
from agents import Orchestrator

load_dotenv()
st.set_page_config(page_title="Shop Tracker GraphRAG", page_icon="🛍️", layout="wide")
st.title("🛍️ Shop Tracker — Multi-Agent GraphRAG")
st.caption("Google Maps + Knowledge Graph + Google News (SerpApi) → knowledge graph → graph Q&A")

with st.sidebar:
    st.header("Settings")
    serp_key = st.text_input("SerpApi key", os.getenv("SERPAPI_API_KEY", ""), type="password")
    shop = st.text_input("Shop / category", "coffee shop")
    location = st.text_input("Location", "Pune, India")
    ll = st.text_input("Optional map centre (@lat,lng,zoom)", "")
    top_n = st.slider("Shops to enrich", 2, 10, 6)
    go = st.button("🔎 Search & build graph", type="primary", use_container_width=True)

S = st.session_state
S.setdefault("chat", [])

if go:
    if not serp_key:
        st.error("Enter your SerpApi key.")
    else:
        try:
            with st.status("Agents working...", expanded=True) as status:
                S.shops, S.kgs, S.news, S.graph = Orchestrator().build(
                    shop, location, serp_key, top_n, ll or None, log=st.write)
                S.key = f"{shop}|{location}"
                tracker.save_snapshot(S.key, S.shops)
                S.chat = []
                status.update(label="Graph ready", state="complete")
        except serp.SerpError as e:
            st.error(f"SerpApi error: {e}")

if "graph" not in S:
    st.info("Set your keys and click **Search & build graph**.")
    st.stop()

t_shops, t_kg, t_news, t_graph, t_track, t_chat = st.tabs(
    ["📍 Shops & Map", "🧠 Knowledge Graph API", "📰 News", "🕸️ Graph", "📈 Tracking", "💬 Ask (GraphRAG)"])

with t_shops:
    df = pd.DataFrame(S.shops)
    st.dataframe(df.drop(columns=["place_id"]), use_container_width=True)
    components.html(build_map(S.shops), height=640)

with t_kg:
    for s in S.shops:
        kg = S.kgs.get(s["place_id"])
        with st.expander(f"{s['title']} — {'profile found' if kg else 'no profile'}"):
            st.json(kg) if kg else st.write("No Knowledge Graph panel returned.")

with t_news:
    for s in S.shops:
        arts = S.news.get(s["place_id"], [])
        st.subheader(s["title"])
        if not arts:
            st.caption("No recent news.")
        for a in arts:
            st.markdown(f"- [{a['title']}]({a['link']}) — *{a['source']}*, {a['date']}")

with t_graph:
    G = S.graph.G
    st.write(f"**{G.number_of_nodes()}** nodes · **{G.number_of_edges()}** edges "
             "(green=shop, yellow=category, blue=area, pink=KG entity, purple=news)")
    components.html(S.graph.to_html(), height=650, scrolling=True)

with t_track:
    st.write("Each search saves a snapshot. Re-run later to detect changes.")
    changes = tracker.diff_last_two(S.key)
    if changes:
        st.dataframe(pd.DataFrame(changes), use_container_width=True)
    else:
        st.caption("Need at least two snapshots for this query to show changes.")
    hist = tracker.history(S.key)
    st.caption(f"{len(hist)} snapshot(s) stored in data/tracking.json")
    rows = [{"time": h["ts"], **{s["title"]: s["rating"] for s in h["shops"]}} for h in hist]
    if rows:
        st.line_chart(pd.DataFrame(rows).set_index("time"))

with t_chat:
    from agents import AnalystAgent
    for m in S.chat:
        st.chat_message(m["role"]).write(m["content"])
    q = st.chat_input("Try: best rating | latest news | phone numbers | opening hours | address")
    if q:
        st.chat_message("user").write(q)
        with st.spinner("Retrieving subgraph & reasoning..."):
            ans, ctx = AnalystAgent().run(q, S.graph)
        st.chat_message("assistant").write(ans)
        with st.expander("Retrieved graph context"):
            st.code(ctx)
        S.chat += [{"role": "user", "content": q}, {"role": "assistant", "content": ans}]
