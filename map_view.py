"""Attractive interactive shop map (folium) rendered inside Streamlit via components.html."""
import html
import folium
from folium.plugins import Fullscreen, MiniMap, LocateControl


def _color(rating):
    if rating is None:
        return "#9E9E9E"
    return "#2E7D32" if rating >= 4.5 else "#F9A825" if rating >= 4.0 else "#E53935"


def _stars(rating):
    if rating is None:
        return "No rating"
    full = int(round(rating))
    return "★" * full + "☆" * (5 - full) + f" {rating}"


def _pin(rating, n):
    c = _color(rating)
    label = f"{rating}" if rating is not None else "–"
    return folium.DivIcon(
        icon_size=(44, 52), icon_anchor=(22, 52),
        html=f"""
        <div style="position:relative;width:44px;height:52px;">
          <div style="background:{c};color:#fff;width:40px;height:40px;border-radius:50% 50% 50% 0;
                      transform:rotate(-45deg);border:3px solid #fff;box-shadow:0 3px 8px rgba(0,0,0,.45);
                      position:absolute;top:0;left:2px;"></div>
          <div style="position:absolute;top:8px;left:2px;width:40px;text-align:center;color:#fff;
                      font:700 13px/1 Arial;">{label}</div>
          <div style="position:absolute;top:-6px;right:-2px;background:#1E1E1E;color:#fff;border-radius:10px;
                      font:700 10px/1 Arial;padding:3px 5px;">{n}</div>
        </div>""")


def _popup(s):
    g = f"https://www.google.com/maps/search/?api=1&query={s['lat']},{s['lon']}"
    web = f'<a href="{html.escape(s["website"])}" target="_blank">🌐 Website</a> &nbsp;' if s.get("website") else ""
    phone = f"📞 {html.escape(str(s['phone']))}<br>" if s.get("phone") else ""
    status = f"🕒 {html.escape(str(s['open_state']))}<br>" if s.get("open_state") else ""
    return f"""
    <div style="font-family:Arial;width:240px;">
      <div style="font-size:15px;font-weight:700;color:#1a1a1a;">{html.escape(str(s['title']))}</div>
      <div style="color:#666;font-size:12px;margin-bottom:4px;">{html.escape(str(s.get('type') or ''))}</div>
      <div style="color:#F9A825;font-size:14px;">{_stars(s.get('rating'))}
        <span style="color:#888;font-size:12px;">({s.get('reviews') or 0} reviews)</span></div>
      <div style="font-size:12px;margin:6px 0;color:#333;">📍 {html.escape(str(s.get('address') or ''))}<br>{phone}{status}</div>
      {web}<a href="{g}" target="_blank">🗺️ Open in Google Maps</a>
    </div>"""


LEGEND = """
<div style="position:fixed;bottom:28px;left:12px;z-index:9999;background:rgba(255,255,255,.95);padding:10px 12px;
            border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,.3);font:12px Arial;color:#222;">
  <b>Rating</b><br>
  <span style="color:#2E7D32;">●</span> 4.5+ &nbsp;<span style="color:#F9A825;">●</span> 4.0–4.4
  &nbsp;<span style="color:#E53935;">●</span> &lt; 4.0 &nbsp;<span style="color:#9E9E9E;">●</span> none
</div>"""


def build_map(shops: list[dict], height: int = 620) -> str:
    pts = [s for s in shops if s.get("lat") is not None and s.get("lon") is not None]
    if not pts:
        return "<p style='font-family:Arial'>No coordinates available.</p>"

    m = folium.Map(location=[pts[0]["lat"], pts[0]["lon"]], zoom_start=13, tiles=None,
                   control_scale=True, height=height)
    folium.TileLayer("CartoDB positron", name="Light").add_to(m)
    folium.TileLayer("CartoDB dark_matter", name="Dark").add_to(m)
    folium.TileLayer("OpenStreetMap", name="Streets").add_to(m)
    folium.TileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name="Satellite").add_to(m)

    layer = folium.FeatureGroup(name="Shops", show=True).add_to(m)
    for i, s in enumerate(pts, 1):
        folium.Marker([s["lat"], s["lon"]], icon=_pin(s.get("rating"), i),
                      popup=folium.Popup(_popup(s), max_width=280),
                      tooltip=f"{i}. {s['title']} — {s.get('rating') or 'n/a'}★").add_to(layer)

    m.fit_bounds([[s["lat"], s["lon"]] for s in pts], padding=(40, 40), max_zoom=16)
    folium.LayerControl(collapsed=True).add_to(m)
    Fullscreen().add_to(m)
    MiniMap(toggle_display=True, position="bottomright").add_to(m)
    LocateControl().add_to(m)
    m.get_root().html.add_child(folium.Element(LEGEND))
    return m.get_root().render()
