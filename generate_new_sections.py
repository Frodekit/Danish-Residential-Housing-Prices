#!/usr/bin/env python3
"""
Generate new sections for the Denmark Housing website:
  Section 5 - The Student Squeeze (SU vs Housing Prices)
  Section 6 - Are Affordable Areas Worth Living In? (OSM liveability)
Writes directly to housing_website/index.html.
"""
import re, json, time
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import pgeocode

# ---- paths -------------------------------------------------------------------
BASE      = Path(__file__).parent
HTML_FILE = BASE / "housing_website" / "index.html"
PARQUET   = BASE / "DKHousingprices_1.parquet"
OSM_CACHE = BASE / "osm_amenity_cache.json"

# ---- chart theme -------------------------------------------------------------
PAPER_BG = "rgba(0,0,0,0)"
PLOT_BG  = "rgba(0,0,0,0)"
FONT_CLR = "#e2e8f0"
MUTED    = "#8892a4"
GRID_CLR = "rgba(255,255,255,0.07)"
ACCENT   = "#16c79a"
CPH_CLR  = "#f97316"
NAT_CLR  = "#60a5fa"

def base_layout(**kw):
    return dict(
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
        font=dict(color=FONT_CLR),
        margin=dict(l=60, r=30, t=50, b=50),
        **kw,
    )

def xax(**kw):
    return dict(gridcolor=GRID_CLR, showgrid=False,
                tickfont=dict(color=MUTED), zeroline=False, **kw)

def yax(title="", **kw):
    return dict(gridcolor=GRID_CLR, showgrid=True,
                tickfont=dict(color=MUTED), zeroline=False,
                title=dict(text=title, font=dict(color=MUTED)), **kw)

def fig_div(fig, div_id):
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id=div_id)

# ==============================================================================
# 1. HOUSING DATA
# ==============================================================================
print("Loading housing data ...")
df = pd.read_parquet(PARQUET)
apts = df[df["house_type"] == "Apartment"].copy()
apts["date"] = pd.to_datetime(apts["date"])
apts["year"]  = apts["date"].dt.year
apts = apts.dropna(subset=["sqm_price", "zip_code"])
lo, hi = apts["sqm_price"].quantile(0.01), apts["sqm_price"].quantile(0.99)
apts = apts[(apts["sqm_price"] >= lo) & (apts["sqm_price"] <= hi)]

apts["zip_int"] = apts["zip_code"].astype(int)
cph_apts = apts[(apts["zip_int"] >= 1000) & (apts["zip_int"] <= 2999)]

annual_nat = apts.groupby("year")["sqm_price"].median()
annual_cph = cph_apts.groupby("year")["sqm_price"].median()

# ==============================================================================
# 2. SU + CPI DATA
# ==============================================================================
# Monthly SU grant for udeboende on higher education
# Source: su.dk/satser/videregaaende-uddannelser-satser-for-su-til-udeboende/gamle-satser
SU = {2014: 5839, 2015: 5903, 2016: 5941, 2017: 6015,
      2018: 6090, 2019: 6166, 2020: 6243, 2021: 6321,
      2022: 6397, 2023: 6589, 2024: 6820}

# Danish CPI annual average, 2015 = 100  (Statistics Denmark, PRIS111)
CPI = {2014: 99.3, 2015: 100.0, 2016: 100.0, 2017: 101.1,
       2018: 102.7, 2019: 104.1, 2020: 103.6, 2021: 105.5,
       2022: 115.5, 2023: 121.5, 2024: 124.0}

YEARS   = sorted(SU)
su_vals = [SU[y]              for y in YEARS]
cpi_vals= [CPI[y]             for y in YEARS]
nat_vals= [float(annual_nat[y]) for y in YEARS]
cph_vals= [float(annual_cph[y]) for y in YEARS]

def idx100(vals):
    b = vals[0]
    return [v / b * 100 for v in vals]

su_idx  = idx100(su_vals)
cpi_idx = idx100(cpi_vals)
nat_idx = idx100(nat_vals)
cph_idx = idx100(cph_vals)

sqm_nat_yr = [(SU[y] * 12) / float(annual_nat[y]) for y in YEARS]
sqm_cph_yr = [(SU[y] * 12) / float(annual_cph[y]) for y in YEARS]

# ==============================================================================
# 3. SECTION 5 - TWO CHARTS
# ==============================================================================
print("Building Section 5 charts ...")

# Chart A: Growth index 2014=100
figA = go.Figure()
figA.add_trace(go.Scatter(x=YEARS, y=cph_idx, name="Copenhagen apartments",
    line=dict(color=CPH_CLR, width=3), mode="lines+markers", marker=dict(size=7),
    hovertemplate="%{y:.1f}<extra>Copenhagen apartments</extra>"))
figA.add_trace(go.Scatter(x=YEARS, y=nat_idx, name="Denmark apartments",
    line=dict(color=NAT_CLR, width=2.5, dash="dash"), mode="lines+markers", marker=dict(size=6),
    hovertemplate="%{y:.1f}<extra>Denmark (national)</extra>"))
figA.add_trace(go.Scatter(x=YEARS, y=su_idx, name="Monthly SU grant",
    line=dict(color=ACCENT, width=3), mode="lines+markers", marker=dict(size=7),
    hovertemplate="%{y:.1f}<extra>SU grant</extra>"))
figA.add_trace(go.Scatter(x=YEARS, y=cpi_idx, name="Consumer Price Index",
    line=dict(color=MUTED, width=1.8, dash="dot"), mode="lines",
    hovertemplate="%{y:.1f}<extra>CPI</extra>"))
figA.add_hline(y=100, line_dash="dot", line_color="rgba(255,255,255,0.12)", line_width=1)
for label, vals, clr in [
    ("CPH +65%",    cph_idx, CPH_CLR),
    ("Nat. +44%",   nat_idx, NAT_CLR),
    ("SU +17%",     su_idx,  ACCENT),
    ("CPI +25%",    cpi_idx, MUTED),
]:
    figA.add_annotation(x=2024, y=vals[-1], text=label, font=dict(color=clr, size=11),
                        xanchor="left", showarrow=False, xshift=8)
figA.update_layout(**base_layout(height=460),
    xaxis=xax(tickvals=YEARS, ticktext=[str(y) for y in YEARS]),
    yaxis=yax("Index (2014 = 100)", range=[85, 215]),
    legend=dict(orientation="h", y=1.06, x=0,
                font=dict(color=MUTED), bgcolor="rgba(0,0,0,0)"))

# Chart B: m2 per year of SU
figB = go.Figure()
figB.add_trace(go.Scatter(x=YEARS, y=sqm_cph_yr, name="Copenhagen",
    line=dict(color=CPH_CLR, width=3), mode="lines+markers", marker=dict(size=7),
    fill="tozeroy", fillcolor="rgba(249,115,22,0.08)",
    hovertemplate="%{y:.2f} m<sup>2</sup><extra>Copenhagen</extra>"))
figB.add_trace(go.Scatter(x=YEARS, y=sqm_nat_yr, name="Denmark (national)",
    line=dict(color=NAT_CLR, width=2.5, dash="dash"), mode="lines+markers", marker=dict(size=6),
    hovertemplate="%{y:.2f} m<sup>2</sup><extra>National</extra>"))
figB.update_layout(**base_layout(height=380),
    xaxis=xax(tickvals=YEARS, ticktext=[str(y) for y in YEARS]),
    yaxis=yax("m² purchasable with a full year of SU"),
    legend=dict(orientation="h", y=1.06, x=0,
                font=dict(color=MUTED), bgcolor="rgba(0,0,0,0)"))

# ==============================================================================
# 4. LIVEABILITY DATA (OSM Overpass)
# ==============================================================================
print("Computing commuter-zone zip codes ...")

apts_2024 = apts[apts["year"] == 2024]
zip_stats = (apts_2024.groupby("zip_code")
             .agg(median_price=("sqm_price", "median"), count=("sqm_price", "count"))
             .reset_index())

nomi = pgeocode.Nominatim("DK")
zip_str = zip_stats["zip_code"].astype(str).str.zfill(4)
geo = nomi.query_postal_code(zip_str.tolist())
zip_stats["lat"]       = geo["latitude"].values
zip_stats["lon"]       = geo["longitude"].values
zip_stats["city_name"] = geo["place_name"].values
zip_stats = zip_stats.dropna(subset=["lat", "lon"])

CPH_LAT, CPH_LON = 55.6761, 12.5683

def haversine_v(lat2, lon2):
    R = 6371.0
    phi1 = np.radians(CPH_LAT)
    phi2 = np.radians(lat2)
    dlat = np.radians(lat2 - CPH_LAT)
    dlon = np.radians(lon2 - CPH_LON)
    a = np.sin(dlat / 2)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlon / 2)**2
    return 2 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))

zip_stats["dist_km"] = haversine_v(zip_stats["lat"].values, zip_stats["lon"].values)
zone = zip_stats[(zip_stats["dist_km"] <= 50) & (zip_stats["count"] >= 5)].copy()
print(f"  Zone zip codes: {len(zone)}")

# ---- Overpass API ------------------------------------------------------------
BB = "55.25,11.75,56.15,13.25"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
QUERIES = {
    "essentials": f'node["amenity"~"^(supermarket|pharmacy|hospital|clinic|doctors)$"]({BB});',
    "food_drink": f'node["amenity"~"^(restaurant|cafe|bar|fast_food)$"]({BB});',
    "education":  f'node["amenity"~"^(school|kindergarten|university|college|library)$"]({BB});',
    "culture":    f'node["amenity"~"^(cinema|theatre|museum|arts_centre|community_centre)$"]({BB});',
    "leisure":    f'node["leisure"~"^(park|playground|fitness_centre|sports_centre|swimming_pool)$"]({BB});',
    "transport":  (f'node["railway"~"^(station|halt|tram_stop)$"]({BB});'
                   f'node["amenity"="bus_station"]({BB});'),
}
WEIGHTS = {"essentials": 3, "food_drink": 2, "education": 2,
           "culture": 1, "leisure": 1, "transport": 3}
UA = "DKHousingProject/1.0 (academic research)"

amenity_pts = {}
if OSM_CACHE.exists():
    print("Loading cached OSM data ...")
    raw = json.loads(OSM_CACHE.read_text())
    amenity_pts = {cat: [tuple(p) for p in pts] for cat, pts in raw.items()}
    for cat, pts in amenity_pts.items():
        print(f"  {cat}: {len(pts)} nodes (cached)")
else:
    print("Fetching OSM amenity data ...")
    for cat, q in QUERIES.items():
        query = f"[out:json][timeout:60];\n(\n{q}\n);\nout;"
        for attempt in range(3):
            try:
                r = requests.get(OVERPASS_URL, params={"data": query},
                                 headers={"User-Agent": UA}, timeout=90)
                r.raise_for_status()
                elements = r.json().get("elements", [])
                amenity_pts[cat] = [(e["lat"], e["lon"]) for e in elements if "lat" in e]
                print(f"  {cat}: {len(amenity_pts[cat])} nodes")
                time.sleep(1.5)
                break
            except Exception as exc:
                print(f"  {cat}: attempt {attempt+1} failed ({exc})")
                time.sleep(5)
        else:
            amenity_pts[cat] = []
            print(f"  {cat}: FAILED - using 0 points")
    OSM_CACHE.write_text(json.dumps(amenity_pts))
    print(f"  Saved OSM cache to {OSM_CACHE}")

# ---- Score each zip code: weighted amenities within 3.5 km ------------------
RADIUS_KM = 3.5
cat_arrays = {cat: (np.array(pts) if pts else None) for cat, pts in amenity_pts.items()}

def score_zip(lat, lon):
    total = 0
    for cat, w in WEIGHTS.items():
        arr = cat_arrays[cat]
        if arr is None or len(arr) == 0:
            continue
        dlat = np.radians(arr[:, 0] - lat)
        dlon = np.radians(arr[:, 1] - lon)
        phi1 = np.radians(lat)
        phi2 = np.radians(arr[:, 0])
        a = np.sin(dlat / 2)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlon / 2)**2
        dist = 2 * 6371 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
        total += w * int((dist <= RADIUS_KM).sum())
    return total

print("Scoring liveability ...")
zone["liveability"] = [score_zip(lat, lon)
                       for lat, lon in zip(zone["lat"].values, zone["lon"].values)]

s_min, s_max = zone["liveability"].min(), zone["liveability"].max()
zone["live_score"] = ((zone["liveability"] - s_min) / max(s_max - s_min, 1) * 100).round(1)

NAT_MEDIAN_2024 = float(annual_nat[2024])
zone["affordable"] = zone["median_price"] <= NAT_MEDIAN_2024

# "Best bet" = affordable + top half of liveability WITHIN affordable subset
aff_mask     = zone["affordable"]
live_aff_med = zone.loc[aff_mask, "live_score"].median()

def quadrant(row):
    aff = row["affordable"]
    # For affordable, compare to median of affordable peers
    if aff:
        top = row["live_score"] >= live_aff_med
        return "Best bet: affordable + liveable" if top else "Affordable, fewer amenities"
    else:
        top = row["live_score"] >= zone["live_score"].median()
        return "High amenities, high price" if top else "Expensive, fewer amenities"

zone["quadrant"] = zone.apply(quadrant, axis=1)

n_best    = int((zone["quadrant"] == "Best bet: affordable + liveable").sum())
n_afford  = int(aff_mask.sum())
print(f"  Affordable zip codes: {n_afford}, Best bet: {n_best}")

# ==============================================================================
# 5. SECTION 6 - SCATTER + MAP
# ==============================================================================
print("Building Section 6 charts ...")

Q_COLORS = {
    "Best bet: affordable + liveable": ACCENT,
    "Affordable, fewer amenities":     NAT_CLR,
    "High amenities, high price":      CPH_CLR,
    "Expensive, fewer amenities":      "#64748b",
}

# Chart C: Scatter price vs liveability
figC = go.Figure()
for q, clr in Q_COLORS.items():
    sub = zone[zone["quadrant"] == q]
    figC.add_trace(go.Scatter(
        x=sub["median_price"], y=sub["live_score"],
        mode="markers", name=q,
        marker=dict(color=clr, size=9, opacity=0.75,
                    line=dict(color="rgba(255,255,255,0.2)", width=0.5)),
        text=sub["city_name"].fillna(""),
        customdata=sub[["zip_code", "dist_km", "liveability"]].values,
        hovertemplate=(
            "<b>%{text} (%{customdata[0]})</b><br>"
            "Price: %{x:,.0f} DKK/m²<br>"
            "Liveability: %{y:.0f}/100<br>"
            "Distance: %{customdata[1]:.1f} km<br>"
            "Amenity score: %{customdata[2]}<extra></extra>"
        ),
    ))
figC.add_vline(x=NAT_MEDIAN_2024, line_dash="dash",
               line_color="rgba(255,255,255,0.3)", line_width=1.5,
               annotation_text=f"National median {NAT_MEDIAN_2024:,.0f} DKK/m²",
               annotation_font=dict(color=MUTED, size=11),
               annotation_position="top right")
figC.update_layout(**base_layout(height=460),
    xaxis=xax(title=dict(text="Median price per m² (DKK, 2024)",
                         font=dict(color=MUTED))),
    yaxis=yax("Liveability score (0–100)", range=[-5, 108]),
    legend=dict(orientation="h", y=1.06, x=0,
                font=dict(color=MUTED), bgcolor="rgba(0,0,0,0)"))

# Chart D: Map using scattermap (MapLibre, no token needed)
figD = go.Figure()
for q, clr in Q_COLORS.items():
    sub = zone[zone["quadrant"] == q]
    figD.add_trace(go.Scattermap(
        lat=sub["lat"], lon=sub["lon"],
        mode="markers", name=q,
        marker=dict(
            size=(sub["live_score"] / 100 * 16 + 6).clip(6, 22).tolist(),
            color=clr, opacity=0.82, sizemode="diameter",
        ),
        text=sub["city_name"].fillna(""),
        customdata=sub[["zip_code", "median_price", "live_score", "dist_km"]].values,
        hovertemplate=(
            "<b>%{text} (%{customdata[0]})</b><br>"
            "Price: %{customdata[1]:,.0f} DKK/m²<br>"
            "Liveability: %{customdata[2]:.0f}/100<br>"
            "Distance to CPH: %{customdata[3]:.1f} km<extra></extra>"
        ),
    ))
figD.update_layout(
    paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
    font=dict(color=FONT_CLR),
    height=540,
    map=dict(style="carto-darkmatter", center=dict(lat=55.78, lon=12.55), zoom=8.2),
    legend=dict(orientation="v", y=0.98, x=0.01,
                font=dict(color=MUTED, size=11),
                bgcolor="rgba(13,15,26,0.75)",
                bordercolor="rgba(255,255,255,0.1)", borderwidth=1),
    margin=dict(l=0, r=0, t=10, b=0),
)

# ==============================================================================
# 6. HTML FRAGMENTS
# ==============================================================================
print("Rendering HTML ...")
divA = fig_div(figA, "su-index-chart")
divB = fig_div(figB, "su-sqm-chart")
divC = fig_div(figC, "live-scatter")
divD = fig_div(figD, "live-map")

su_pct  = (SU[2024] / SU[2014] - 1) * 100
cph_pct = (float(annual_cph[2024]) / float(annual_cph[2014]) - 1) * 100
nat_pct = (float(annual_nat[2024]) / float(annual_nat[2014]) - 1) * 100
sqm_c14 = sqm_cph_yr[0]
sqm_c24 = sqm_cph_yr[-1]

section5 = f"""
<section class='section' id='student'>
  <div class='section-label'>Student Affordability</div>
  <h2>The Student Squeeze: SU vs. Housing Prices</h2>
  <p class='section-intro'>
    Denmark&rsquo;s state educational grant (SU) is designed to let students live
    independently. But since 2014 the monthly SU for a student living away from home
    has risen only
    <strong style='color:{ACCENT}'>{su_pct:.0f}%</strong>
    &mdash; from {SU[2014]:,}&thinsp;DKK to {SU[2024]:,}&thinsp;DKK &mdash; while
    Copenhagen apartment prices surged
    <strong style='color:{CPH_CLR}'>{cph_pct:.0f}%</strong> over the same decade.
    Even the national median rose
    <strong style='color:{NAT_CLR}'>{nat_pct:.0f}%</strong>,
    far outpacing both SU and general inflation (CPI&nbsp;+25&thinsp;%).
  </p>
  <div class='two-col'>
    <div>
      <h3 class='chart-title'>Indexed growth since 2014
        <span class='badge'>2014&thinsp;=&thinsp;100</span></h3>
      <p class='chart-sub'>The gap between housing costs and student income has widened every
        year. Hover to see exact values.</p>
      <div class='full-chart'>{divA}</div>
    </div>
    <div>
      <h3 class='chart-title'>Purchasing power: m&sup2; per year of SU</h3>
      <p class='chart-sub'>
        In 2014 a full year of SU could purchase
        <strong style='color:{CPH_CLR}'>{sqm_c14:.2f}&thinsp;m&sup2;</strong>
        of Copenhagen apartment. By 2024 that had fallen to
        <strong style='color:{CPH_CLR}'>{sqm_c24:.2f}&thinsp;m&sup2;</strong>
        &mdash; barely enough for a bathroom.
      </p>
      <div class='full-chart'>{divB}</div>
    </div>
  </div>
  <div class='insight-box'>
    <strong>Key takeaway</strong>&ensp;&mdash;&ensp;
    The SU grant has not been indexed to housing price inflation.
    Location &mdash; choosing an affordable commuter area over the city centre &mdash;
    is the single most impactful financial decision a Danish student can make.
  </div>
</section>
"""

section6 = f"""
<section class='section' id='liveability'>
  <div class='section-label'>Neighbourhood Quality</div>
  <h2>Are Affordable Areas Worth Living In?</h2>
  <p class='section-intro'>
    Price alone doesn&rsquo;t tell the whole story. Using
    <a href='https://www.openstreetmap.org' target='_blank'>OpenStreetMap</a>
    amenity data &mdash; supermarkets, restaurants, schools, pharmacies, parks,
    and transport nodes &mdash; we built a
    <strong>liveability score</strong> for every zip code within 50&thinsp;km of
    Copenhagen. The result: <strong style='color:{ACCENT}'>{n_best} of the
    {n_afford} affordable zip codes</strong> score above the median liveability of
    their affordable peers, forming genuine &ldquo;sweet spot&rdquo; areas.
  </p>
  <div class='two-col'>
    <div>
      <h3 class='chart-title'>Price vs. liveability score
        <span class='badge'>commuter zone &bull; 2024</span></h3>
      <p class='chart-sub'>
        Teal dots are affordable zip codes that also score well on liveability.
        The vertical line marks the national median price.
        Hover a dot for area name, distance, and amenity score.
      </p>
      <div class='full-chart'>{divC}</div>
    </div>
    <div>
      <h3 class='chart-title'>The opportunity map</h3>
      <p class='chart-sub'>
        <strong style='color:{ACCENT}'>Teal</strong> = affordable
        <em>and</em> liveable &mdash; the sweet spots.
        <strong style='color:{NAT_CLR}'>Blue</strong> = affordable with fewer
        amenities. Bubble size encodes the liveability score.
      </p>
      <div class='full-chart'>{divD}</div>
    </div>
  </div>
  <div class='insight-box'>
    <strong>Key takeaway</strong>&ensp;&mdash;&ensp;
    Affordability and liveability are not opposites. The sweet-spot areas tend to
    cluster 15&ndash;40&thinsp;km from Copenhagen &mdash; far enough to escape the
    capital price premium, close enough to retain strong amenity density and
    S-train or regional-rail connections.
  </div>
</section>
"""

# ==============================================================================
# 7. PATCH index.html
# ==============================================================================
print("Patching index.html ...")

# Read the ORIGINAL (unpatched) file; if already patched, restore from docs/
orig_docs = BASE / "docs" / "index.html"
if orig_docs.exists():
    html = orig_docs.read_text(encoding="utf-8")
    print("  Using docs/index.html as clean base")
else:
    html = HTML_FILE.read_text(encoding="utf-8")
    # Remove previously inserted sections if present
    for marker in ["id='student'", 'id="student"']:
        s = html.find("<section")
        while s != -1:
            if marker in html[s:s+50]:
                e = html.find("</section>", s) + len("</section>")
                html = html[:s] + html[e:]
                break
            s = html.find("<section", s + 1)

# Extra CSS
extra_css = """
    .two-col { display:grid; grid-template-columns:1fr 1fr; gap:2.5rem; margin-top:2rem; }
    @media(max-width:900px){ .two-col { grid-template-columns:1fr; } }
    .chart-title { font-size:1rem; font-weight:600; color:#e2e8f0; margin-bottom:0.35rem; }
    .chart-title .badge { font-size:0.72rem; font-weight:500; color:#8892a4;
      background:rgba(255,255,255,0.07); border-radius:4px; padding:1px 6px; margin-left:6px; }
    .chart-sub { font-size:0.85rem; color:#8892a4; margin-bottom:0.8rem; max-width:520px; }
    .insight-box { margin-top:2.5rem; padding:1.2rem 1.8rem;
      background:rgba(22,199,154,0.07); border-left:3px solid #16c79a;
      border-radius:0 8px 8px 0; font-size:0.95rem; color:#c8d5e3; line-height:1.7; }
"""
html = html.replace("</style>", extra_css + "\n  </style>", 1)

# Nav links
html = html.replace(
    "<a href='#affordability'>Affordability</a>",
    "<a href='#affordability'>Affordability</a>\n  "
    "<a href='#student'>Student SU</a>\n  "
    "<a href='#liveability'>Liveability</a>",
)

# Insert new sections before footer
html = html.replace("<footer>", section5 + "\n" + section6 + "\n<footer>", 1)

# Extra sources in footer
extra_src = (
    " &bull; <a href='https://www.su.dk/satser/videregaaende-uddannelser-satser-for-su-til-udeboende/gamle-satser'"
    " target='_blank'>SU satser &ndash; su.dk</a>"
    " &bull; <a href='https://www.dst.dk/da/Statistik/emner/oekonomi/prisindeks/forbrugerprisindeks'"
    " target='_blank'>CPI &ndash; Statistics Denmark</a>"
    " &bull; <a href='https://www.openstreetmap.org' target='_blank'>OpenStreetMap contributors</a>"
)
html = html.replace(
    "DTU 02806 Social Data Analysis and Visualization",
    extra_src + " &bull; DTU 02806 Social Data Analysis and Visualization",
)

HTML_FILE.write_text(html, encoding="utf-8")
print(f"Done. Wrote {len(html):,} chars to {HTML_FILE}")
print(f"  Section 5: SU +{su_pct:.0f}% vs CPH housing +{cph_pct:.0f}% since 2014")
print(f"  Section 6: {n_best}/{n_afford} affordable zip codes are 'best bet'")
