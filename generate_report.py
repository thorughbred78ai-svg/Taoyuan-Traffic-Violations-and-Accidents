#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Taoyuan Traffic Report Generator v4.0
- Free GIS basemaps (no API key required)
- Year switching: all years / single year
"""

import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from folium.plugins import MarkerCluster
from datetime import datetime
import os
import sys
import traceback
import random

os.makedirs("docs", exist_ok=True)
os.makedirs("docs/charts", exist_ok=True)
os.makedirs("docs/maps", exist_ok=True)

API_TIMEOUT = 60
API_RETRY = 3
API_BASE = "https://opendata.tycg.gov.tw/api/v1/rest"

VIOLATION_DATASET_ID = "08b2987e-01e5-458d-a8c1-cd4b540a0105"
ACCIDENT_DATASET_IDS = [
    "08d560b5-7cf2-4909-8a02-da39c74d8b09",
    "db5055c9-9f2e-4546-8e58-e413dfbbcdeb",
    "f4c49615-1120-4fd5-8ada-e9a77b1c784e",
]

TAOYUAN_AREAS = {
    "Taoyuan": [24.989, 121.313],
    "Zhongli": [24.965, 121.221],
    "Pingzhen": [24.947, 121.206],
    "Bade": [24.930, 121.290],
    "Yangmei": [24.907, 121.146],
    "Luzhu": [25.045, 121.290],
    "Daxi": [24.883, 121.288],
    "Longtan": [24.864, 121.211],
    "Guishan": [25.022, 121.400],
    "Dayuan": [25.066, 121.197],
    "Guanyin": [25.036, 121.133],
    "Xinwu": [24.974, 121.106],
    "Fuxing": [24.817, 121.375],
}

VIOLATION_LAWS = ["Speeding", "Red Light", "Illegal Parking", "No Seatbelt", "Phone Use", "Wrong Way", "Lane Change", "Pedestrian ROW"] * 2
VIOLATION_FACTS = ["Excessive Speed", "Running Red Light", "Parking Violation", "Distracted Driving", "Failure to Yield", "Illegal U-Turn"] * 3
ACCIDENT_TYPES = ["Intersection", "Rear-End", "Side Impact", "Pedestrian", "Bicycle", "Single Vehicle"] * 2


def api_get(url, params=None, timeout=API_TIMEOUT):
    for attempt in range(1, API_RETRY + 1):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"      API error (attempt {attempt}/{API_RETRY}): {e}")
            if attempt == API_RETRY:
                return None
    return None


def fetch_datastore_direct(resource_id, limit=100000):
    url = f"{API_BASE}/datastore/{resource_id}"
    params = {"format": "json", "limit": limit}
    print(f"    Fetching: {url}")
    data = api_get(url, params=params, timeout=API_TIMEOUT)
    if not data:
        return []
    result = data.get("result", {})
    records = result.get("records") or result.get("results") or []
    return records


def fetch_dataset(dataset_id, name=""):
    print(f"\n[{name}] Dataset ID: {dataset_id}")
    meta_url = f"{API_BASE}/dataset/{dataset_id}"
    print(f"  Fetching metadata: {meta_url}")
    meta = api_get(meta_url, timeout=30)

    all_records = []
    resource_ids = []

    if meta and "result" in meta:
        result = meta["result"]
        resources = result.get("resources") or result.get("resource") or []
        if isinstance(resources, list):
            for r in resources:
                rid = r.get("id") or r.get("resource_id") or r.get("_id")
                if rid:
                    resource_ids.append((rid, r.get("name", "")))
        print(f"  Found {len(resource_ids)} resources")
    else:
        print(f"  [Warning] Cannot get metadata, trying direct access")
        resource_ids = [(dataset_id, "direct")]

    for rid, rname in resource_ids:
        print(f"    Fetching resource: {rname or rid}")
        records = fetch_datastore_direct(rid, limit=100000)
        if records:
            print(f"    Success: {len(records)} records")
            for rec in records:
                rec["_source"] = rname
            all_records.extend(records)
        else:
            print(f"    Failed or no data")

    df = pd.DataFrame(all_records)
    print(f"  Total: {df.shape[0]} rows x {df.shape[1]} cols")
    if not df.empty:
        print(f"  Columns: {list(df.columns)}")
    return df


def sample_violations(n=5000):
    print(f"\n[Fallback] Generating sample violation data: {n} records")
    areas = list(TAOYUAN_AREAS.keys())
    years = list(range(109, 115))
    data = []
    for _ in range(n):
        area = random.choice(areas)
        lat, lon = TAOYUAN_AREAS[area]
        data.append({
            "year": random.choice(years),
            "month": random.randint(1, 12),
            "time": f"{random.randint(0,23):02d}:{random.randint(0,59):02d}",
            "law": random.choice(VIOLATION_LAWS),
            "fact": random.choice(VIOLATION_FACTS),
            "CountyCode": "68",
            "AreaName": area,
            "AreaCode": "",
            "Road": random.choice(["Zhongshan Rd", "Zhongzheng Rd", "Fuxing Rd", "Wenhua Rd"]),
            "latitude": round(lat + random.uniform(-0.05, 0.05), 6),
            "longitude": round(lon + random.uniform(-0.05, 0.05), 6),
        })
    return pd.DataFrame(data)


def sample_accidents(n=3000):
    print(f"\n[Fallback] Generating sample accident data: {n} records")
    areas = list(TAOYUAN_AREAS.keys())
    years = list(range(108, 115))
    data = []
    for _ in range(n):
        area = random.choice(areas)
        count = random.randint(1, 50)
        data.append({
            "year": random.choice(years),
            "accident_type": random.choice(ACCIDENT_TYPES),
            "city": "Taoyuan",
            "district": area,
            "age_group": random.choice(["18-24","25-39","40-64","65+"]),
            "vehicle_type": random.choice(["Car","Scooter","Bicycle","Truck","Pedestrian"]),
            "case_count": count,
            "deaths": random.randint(0, min(3, count//10)),
            "injuries": random.randint(0, count*3),
        })
    return pd.DataFrame(data)


def find_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def add_free_basemaps(m):
    """Add multiple free basemaps that do not require API keys."""
    folium.TileLayer(
        tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        name="OpenStreetMap",
        overlay=False,
        control=True,
    ).add_to(m)

    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        name="CartoDB Positron",
        overlay=False,
        control=True,
    ).add_to(m)

    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        name="CartoDB Dark",
        overlay=False,
        control=True,
    ).add_to(m)

    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles &copy; Esri",
        name="Esri Satellite",
        overlay=False,
        control=True,
    ).add_to(m)

    return m


def analyze_violations():
    print("\n" + "=" * 60)
    print("[Violation Data]")
    print("=" * 60)

    df = fetch_dataset(VIOLATION_DATASET_ID, "Violations")
    is_sample = False
    if df.empty:
        print("  [Warning] API failed, using sample data")
        df = sample_violations(5000)
        is_sample = True

    yc = find_col(df, ["year","Year","YEAR"])
    lc = find_col(df, ["law","Law","LAW"])
    fc = find_col(df, ["fact","Fact","FACT"])
    ac = find_col(df, ["AreaName","areaName","area","AREA"])
    lac = find_col(df, ["latitude","Latitude","LATITUDE","lat","Lat"])
    loc = find_col(df, ["longitude","Longitude","LONGITUDE","lon","Lng"])
    rc = find_col(df, ["Road","road","ROAD"])

    print(f"  Columns: year={yc}, law={lc}, fact={fc}, area={ac}, lat={lac}, lon={loc}")

    years = []
    if yc and yc in df.columns:
        years = sorted(df[yc].dropna().unique())
        years = [int(y) if str(y).isdigit() else y for y in years]
        years = sorted(years)
    print(f"  Years: {years}")

    return {
        "df": df, "is_sample": is_sample, "years": years,
        "yc": yc, "lc": lc, "fc": fc, "ac": ac, "lac": lac, "loc": loc, "rc": rc,
        "year_counts": df[yc].value_counts().sort_index() if yc else pd.Series(dtype=int),
        "law_counts": df[lc].value_counts().head(20) if lc else pd.Series(dtype=int),
        "fact_counts": df[fc].value_counts().head(20) if fc else pd.Series(dtype=int),
        "area_counts": df[ac].value_counts() if ac else pd.Series(dtype=int),
    }


def make_violation_charts(a):
    if a is None:
        return {}, []
    figs = {}
    all_figs = []
    sn = " (Sample)" if a.get("is_sample") else ""
    df = a["df"]
    yc = a["yc"]
    years = a["years"]

    def save_bar(d, title, xlabel, ylabel, fn, cs):
        try:
            if d is None or len(d) == 0:
                return None
            fig = px.bar(x=d.index.astype(str), y=d.values,
                         labels={"x":xlabel,"y":ylabel}, title=title,
                         color=d.values, color_continuous_scale=cs)
            fig.update_layout(template="plotly_white")
            if len(d) > 5:
                fig.update_layout(xaxis_tickangle=-45)
            fig.write_html(fn, include_plotlyjs="cdn")
            return os.path.basename(fn)
        except Exception as e:
            print(f"    [Warning] {fn} failed: {e}")
            return None

    def save_hbar(d, title, ylabel, xlabel, fn, cs, top=15):
        try:
            if d is None or len(d) == 0:
                return None
            d15 = d.head(top)
            fig = px.bar(y=d15.index[::-1], x=d15.values[::-1],
                         orientation="h", labels={"y":ylabel,"x":xlabel}, title=title,
                         color=d15.values[::-1], color_continuous_scale=cs)
            fig.update_layout(template="plotly_white", height=600)
            fig.write_html(fn, include_plotlyjs="cdn")
            return os.path.basename(fn)
        except Exception as e:
            print(f"    [Warning] {fn} failed: {e}")
            return None

    print("\n  Generating all-year violation charts...")
    all_figs.append(save_bar(a["year_counts"], f"Violation Cases by Year{sn}", "Year", "Cases", "docs/charts/violation_yearly_all.html", "Reds"))
    all_figs.append(save_hbar(a["law_counts"], f"Top 15 Violation Laws{sn}", "Law", "Cases", "docs/charts/violation_laws_all.html", "Oranges"))
    all_figs.append(save_hbar(a["fact_counts"], f"Top 15 Violation Facts{sn}", "Fact", "Cases", "docs/charts/violation_facts_all.html", "Blues"))
    all_figs.append(save_bar(a["area_counts"], f"Violation Cases by District{sn}", "District", "Cases", "docs/charts/violation_area_all.html", "Purples"))

    try:
        if yc and yc in df.columns and a["ac"] and a["ac"] in df.columns:
            pivot = df.groupby([yc, a["ac"]]).size().unstack(fill_value=0)
            if pivot.shape[0] > 0 and pivot.shape[1] > 0:
                fig = px.imshow(pivot, labels=dict(x="District",y="Year",color="Cases"),
                               title=f"Violation Heatmap by Year & District{sn}",
                               aspect="auto", color_continuous_scale="YlOrRd")
                fig.update_layout(template="plotly_white", height=500)
                fig.write_html("docs/charts/violation_heatmap_all.html", include_plotlyjs="cdn")
                all_figs.append("violation_heatmap_all.html")
                print(f"    Generated: violation_heatmap_all.html")
    except Exception as e:
        print(f"    [Warning] Heatmap failed: {e}")

    all_figs = [f for f in all_figs if f]

    if yc and years:
        print(f"\n  Generating per-year violation charts ({len(years)} years)...")
        for year in years:
            ydf = df[df[yc] == year]
            if len(ydf) == 0:
                continue
            year_str = str(year)
            yfigs = []
            yfigs.append(save_bar(
                ydf[a["lc"]].value_counts().head(15) if a["lc"] else None,
                f"{year_str} Top Violation Laws{sn}", "Law", "Cases",
                f"docs/charts/violation_laws_{year_str}.html", "Oranges"))
            yfigs.append(save_bar(
                ydf[a["fc"]].value_counts().head(15) if a["fc"] else None,
                f"{year_str} Top Violation Facts{sn}", "Fact", "Cases",
                f"docs/charts/violation_facts_{year_str}.html", "Blues"))
            yfigs.append(save_bar(
                ydf[a["ac"]].value_counts() if a["ac"] else None,
                f"{year_str} Cases by District{sn}", "District", "Cases",
                f"docs/charts/violation_area_{year_str}.html", "Purples"))
            figs[year_str] = [f for f in yfigs if f]

    print(f"  Violation charts: {len(all_figs)} all-year, {len(figs)} year groups")
    return figs, all_figs


def make_violation_maps(a):
    if a is None:
        return {}, None
    df, lac, loc = a["df"], a["lac"], a["loc"]
    yc, lc, fc, ac, rc = a["yc"], a["lc"], a["fc"], a["ac"], a["rc"]
    years = a["years"]
    sn = " (Sample)" if a.get("is_sample") else ""

    if not lac or lac not in df.columns or not loc or loc not in df.columns:
        print("  [Info] Missing coordinates, skipping violation maps")
        return {}, None

    dm = df.copy()
    dm[lac] = pd.to_numeric(dm[lac], errors="coerce")
    dm[loc] = pd.to_numeric(dm[loc], errors="coerce")
    dm = dm.dropna(subset=[lac, loc])
    if len(dm) == 0:
        print("  [Info] No valid coordinates")
        return {}, None

    year_maps = {}

    print("\n  Generating combined violation map (all years as layers)...")
    try:
        m_all = folium.Map(location=[dm[lac].median(), dm[loc].median()], zoom_start=11)
        add_free_basemaps(m_all)

        if yc and yc in dm.columns and years:
            for year in years:
                ydf = dm[dm[yc] == year]
                if len(ydf) == 0:
                    continue
                fg = folium.FeatureGroup(name=f"{year} Violations{sn}")
                mc = MarkerCluster().add_to(fg)
                for _, row in ydf.iterrows():
                    popup = f"<b>Year:</b> {row.get(yc,'N/A')}<br>"
                    if ac: popup += f"<b>District:</b> {row.get(ac,'N/A')}<br>"
                    if rc: popup += f"<b>Road:</b> {row.get(rc,'N/A')}<br>"
                    if lc: popup += f"<b>Law:</b> {str(row.get(lc,'N/A'))[:50]}<br>"
                    if fc: popup += f"<b>Fact:</b> {str(row.get(fc,'N/A'))[:50]}"
                    folium.CircleMarker(location=[row[lac],row[loc]], radius=3,
                        popup=folium.Popup(popup,max_width=300),
                        color="red", fill=True, fill_opacity=0.6).add_to(mc)
                fg.add_to(m_all)
        else:
            mc = MarkerCluster().add_to(m_all)
            for _, row in dm.iterrows():
                popup = ""
                if ac: popup += f"<b>District:</b> {row.get(ac,'N/A')}<br>"
                if rc: popup += f"<b>Road:</b> {row.get(rc,'N/A')}<br>"
                if lc: popup += f"<b>Law:</b> {str(row.get(lc,'N/A'))[:50]}"
                folium.CircleMarker(location=[row[lac],row[loc]], radius=3,
                    popup=folium.Popup(popup,max_width=300),
                    color="red", fill=True, fill_opacity=0.6).add_to(mc)

        folium.LayerControl(collapsed=False).add_to(m_all)
        m_all.save("docs/maps/violation_map_all.html")
        print(f"    Generated: maps/violation_map_all.html")
        all_map = "maps/violation_map_all.html"
    except Exception as e:
        print(f"    [Warning] Combined map failed: {e}")
        traceback.print_exc()
        all_map = None

    if yc and years:
        print(f"\n  Generating per-year violation maps ({len(years)} years)...")
        for year in years:
            try:
                ydf = dm[dm[yc] == year]
                if len(ydf) == 0:
                    continue
                year_str = str(year)
                m = folium.Map(location=[ydf[lac].median(), ydf[loc].median()], zoom_start=11)
                add_free_basemaps(m)
                mc = MarkerCluster().add_to(m)
                for _, row in ydf.iterrows():
                    popup = f"<b>Year:</b> {row.get(yc,'N/A')}<br>"
                    if ac: popup += f"<b>District:</b> {row.get(ac,'N/A')}<br>"
                    if rc: popup += f"<b>Road:</b> {row.get(rc,'N/A')}<br>"
                    if lc: popup += f"<b>Law:</b> {str(row.get(lc,'N/A'))[:50]}<br>"
                    if fc: popup += f"<b>Fact:</b> {str(row.get(fc,'N/A'))[:50]}"
                    folium.CircleMarker(location=[row[lac],row[loc]], radius=3,
                        popup=folium.Popup(popup,max_width=300),
                        color="red", fill=True, fill_opacity=0.6).add_to(mc)
                folium.LayerControl().add_to(m)
                m.save(f"docs/maps/violation_map_{year_str}.html")
                year_maps[year_str] = f"maps/violation_map_{year_str}.html"
                print(f"    Generated: maps/violation_map_{year_str}.html")
            except Exception as e:
                print(f"    [Warning] {year} map failed: {e}")

    print(f"  Violation maps: 1 combined, {len(year_maps)} per-year")
    return year_maps, all_map


def analyze_accidents():
    print("\n" + "=" * 60)
    print("[Accident Data]")
    print("=" * 60)

    df = pd.DataFrame()
    used_id = None
    for ds_id in ACCIDENT_DATASET_IDS:
        df = fetch_dataset(ds_id, "Accidents")
        if not df.empty:
            used_id = ds_id
            break

    is_sample = False
    if df.empty:
        print("  [Warning] All accident APIs failed, using sample data")
        df = sample_accidents(3000)
        is_sample = True

    print(f"  Using: {used_id or 'sample data'}")

    yc = find_col(df, ["year","Year","YEAR"])
    tc = find_col(df, ["type","Type","TYPE","accident_type"])
    ac = find_col(df, ["area","Area","AREA","district"])
    pc = find_col(df, ["place","Place","location"])
    vc = find_col(df, ["vehicle","Vehicle","vehicle_type"])
    cc = find_col(df, ["count","Count","case_count"])
    dc = find_col(df, ["death","Death","deaths"])
    ic = find_col(df, ["injury","Injury","injuries"])

    print(f"  Columns: year={yc}, type={tc}, area={ac}, count={cc}, death={dc}, injury={ic}")

    for col in [cc, dc, ic]:
        if col and col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    years = []
    if yc and yc in df.columns:
        df[yc] = df[yc].astype(str)
        years = sorted(df[yc].dropna().unique())
    print(f"  Years: {years}")

    year_stats = None
    if yc and yc in df.columns:
        year_stats = df.groupby(yc)[cc].sum().sort_index() if cc else df[yc].value_counts().sort_index()

    type_stats = df.groupby(tc)[cc].sum().sort_values(ascending=False) if tc and cc else (df[tc].value_counts() if tc else None)
    area_stats = df.groupby(ac)[cc].sum().sort_values(ascending=False) if ac and cc else (df[ac].value_counts() if ac else None)
    place_stats = df.groupby(pc)[cc].sum().sort_values(ascending=False) if pc and cc else (df[pc].value_counts() if pc else None)
    vehicle_stats = df.groupby(vc)[cc].sum().sort_values(ascending=False) if vc and cc else (df[vc].value_counts() if vc else None)

    dis = None
    if yc and yc in df.columns:
        agg = {}
        if cc: agg["Total Cases"] = (cc, "sum")
        if dc: agg["Total Deaths"] = (dc, "sum")
        if ic: agg["Total Injuries"] = (ic, "sum")
        if agg:
            dis = df.groupby(yc).agg(**agg)

    return {
        "df": df, "is_sample": is_sample, "years": years,
        "yc": yc, "tc": tc, "ac": ac, "pc": pc, "vc": vc, "cc": cc, "dc": dc, "ic": ic,
        "year_stats": year_stats, "type_stats": type_stats, "area_stats": area_stats,
        "place_stats": place_stats, "vehicle_stats": vehicle_stats, "dis": dis,
    }


def make_accident_charts(a):
    if a is None:
        return {}, []
    figs = {}
    all_figs = []
    sn = " (Sample)" if a.get("is_sample") else ""
    df = a["df"]
    yc = a["yc"]
    years = a["years"]

    def save_bar(d, title, xlabel, ylabel, fn, cs):
        try:
            if d is None or len(d) == 0:
                return None
            fig = px.bar(x=d.index.astype(str), y=d.values,
                         labels={"x":xlabel,"y":ylabel}, title=title,
                         color=d.values, color_continuous_scale=cs)
            fig.update_layout(template="plotly_white")
            if len(d) > 5:
                fig.update_layout(xaxis_tickangle=-45)
            fig.write_html(fn, include_plotlyjs="cdn")
            return os.path.basename(fn)
        except Exception as e:
            print(f"    [Warning] {fn} failed: {e}")
            return None

    print("\n  Generating all-year accident charts...")

    all_figs.append(save_bar(a["year_stats"], f"Accident Cases by Year{sn}", "Year", "Cases", "docs/charts/accident_yearly_all.html", "Reds"))

    try:
        d = a["type_stats"]
        if d is not None and len(d) > 0:
            fig = px.pie(names=d.index, values=d.values, title=f"Accident Types{sn}", hole=0.4)
            fig.update_traces(textposition="inside", textinfo="percent+label")
            fig.update_layout(template="plotly_white")
            fig.write_html("docs/charts/accident_type_all.html", include_plotlyjs="cdn")
            all_figs.append("accident_type_all.html")
            print(f"    Generated: accident_type_all.html")
    except Exception as e:
        print(f"    [Warning] Type pie failed: {e}")

    all_figs.append(save_bar(a["area_stats"], f"Accidents by District{sn}", "District", "Cases", "docs/charts/accident_area_all.html", "Oranges"))

    try:
        d = a["place_stats"]
        if d is not None and len(d) > 0:
            d15 = d.head(15)
            fig = px.bar(y=d15.index[::-1], x=d15.values[::-1],
                         orientation="h", labels={"y":"Place","x":"Cases"},
                         title=f"Top 15 Accident Places{sn}",
                         color=d15.values[::-1], color_continuous_scale="Blues")
            fig.update_layout(template="plotly_white")
            fig.write_html("docs/charts/accident_place_all.html", include_plotlyjs="cdn")
            all_figs.append("accident_place_all.html")
            print(f"    Generated: accident_place_all.html")
    except Exception as e:
        print(f"    [Warning] Place chart failed: {e}")

    try:
        d = a["vehicle_stats"]
        if d is not None and len(d) > 0:
            d15 = d.head(15)
            fig = px.bar(y=d15.index[::-1], x=d15.values[::-1],
                         orientation="h", labels={"y":"Vehicle","x":"Cases"},
                         title=f"Top 15 Vehicle Types{sn}",
                         color=d15.values[::-1], color_continuous_scale="Greens")
            fig.update_layout(template="plotly_white")
            fig.write_html("docs/charts/accident_vehicle_all.html", include_plotlyjs="cdn")
            all_figs.append("accident_vehicle_all.html")
            print(f"    Generated: accident_vehicle_all.html")
    except Exception as e:
        print(f"    [Warning] Vehicle chart failed: {e}")

    try:
        dis = a["dis"]
        if dis is not None and len(dis) > 0:
            fig = go.Figure()
            for col in dis.columns:
                fig.add_trace(go.Scatter(x=dis.index.astype(str), y=dis[col].values,
                                         mode="lines+markers", name=col))
            fig.update_layout(title=f"Casualty Trend by Year{sn}",
                              xaxis_title="Year", yaxis_title="Count", template="plotly_white",
                              legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            fig.write_html("docs/charts/accident_casualty_all.html", include_plotlyjs="cdn")
            all_figs.append("accident_casualty_all.html")
            print(f"    Generated: accident_casualty_all.html")
    except Exception as e:
        print(f"    [Warning] Casualty trend failed: {e}")

    all_figs = [f for f in all_figs if f]

    if yc and years:
        print(f"\n  Generating per-year accident charts ({len(years)} years)...")
        for year in years:
            ydf = df[df[yc] == year]
            if len(ydf) == 0:
                continue
            year_str = str(year)
            yfigs = []
            yfigs.append(save_bar(
                ydf[a["tc"]].value_counts().head(15) if a["tc"] else None,
                f"{year_str} Accident Types{sn}", "Type", "Cases",
                f"docs/charts/accident_type_{year_str}.html", "Oranges"))
            yfigs.append(save_bar(
                ydf[a["ac"]].value_counts() if a["ac"] else None,
                f"{year_str} Accidents by District{sn}", "District", "Cases",
                f"docs/charts/accident_area_{year_str}.html", "Purples"))
            yfigs.append(save_bar(
                ydf[a["pc"]].value_counts().head(15) if a["pc"] else None,
                f"{year_str} Top Places{sn}", "Place", "Cases",
                f"docs/charts/accident_place_{year_str}.html", "Blues"))
            yfigs.append(save_bar(
                ydf[a["vc"]].value_counts().head(15) if a["vc"] else None,
                f"{year_str} Top Vehicles{sn}", "Vehicle", "Cases",
                f"docs/charts/accident_vehicle_{year_str}.html", "Greens"))
            figs[year_str] = [f for f in yfigs if f]

    print(f"  Accident charts: {len(all_figs)} all-year, {len(figs)} year groups")
    return figs, all_figs


def make_accident_maps(a):
    if a is None:
        return {}, None
    df = a["df"]
    ac, cc, dc, ic, yc = a["ac"], a["cc"], a["dc"], a["ic"], a["yc"]
    years = a["years"]
    sn = " (Sample)" if a.get("is_sample") else ""

    if not ac or ac not in df.columns:
        print("  [Info] Missing district data, skipping accident maps")
        return {}, None

    year_maps = {}

    print("\n  Generating combined accident map (all years as layers)...")
    try:
        m_all = folium.Map(location=[24.95, 121.25], zoom_start=10)
        add_free_basemaps(m_all)

        if yc and yc in df.columns and years:
            for year in years:
                ydf = df[df[yc] == year]
                if len(ydf) == 0:
                    continue
                fg = folium.FeatureGroup(name=f"{year} Accidents{sn}")
                if ac in ydf.columns:
                    summary = ydf.groupby(ac)[cc].sum() if cc else ydf[ac].value_counts()
                    for area, count in summary.items():
                        coords = None
                        for key, coord in TAOYUAN_AREAS.items():
                            if key in str(area) or str(area) in key:
                                coords = coord
                                break
                        if coords:
                            r = min(max(float(count)**0.5*2, 5), 50)
                            popup = f"<b>{year} {area}</b><br>Cases: {int(count)}"
                            if dc and dc in ydf.columns:
                                popup += f"<br>Deaths: {int(ydf[ydf[ac]==area][dc].sum())}"
                            if ic and ic in ydf.columns:
                                popup += f"<br>Injuries: {int(ydf[ydf[ac]==area][ic].sum())}"
                            folium.CircleMarker(location=coords, radius=r,
                                popup=folium.Popup(popup,max_width=250),
                                color="orange", fill=True, fill_color="orange", fill_opacity=0.6).add_to(fg)
                fg.add_to(m_all)
        else:
            summary = df.groupby(ac)[cc].sum() if cc else df[ac].value_counts()
            for area, count in summary.items():
                coords = None
                for key, coord in TAOYUAN_AREAS.items():
                    if key in str(area) or str(area) in key:
                        coords = coord
                        break
                if coords:
                    r = min(max(float(count)**0.5*2, 5), 50)
                    folium.CircleMarker(location=coords, radius=r,
                        popup=folium.Popup(f"<b>{area}</b><br>Cases: {int(count)}",max_width=250),
                        color="orange", fill=True, fill_color="orange", fill_opacity=0.6).add_to(m_all)

        folium.LayerControl(collapsed=False).add_to(m_all)
        m_all.save("docs/maps/accident_map_all.html")
        print(f"    Generated: maps/accident_map_all.html")
        all_map = "maps/accident_map_all.html"
    except Exception as e:
        print(f"    [Warning] Combined map failed: {e}")
        traceback.print_exc()
        all_map = None

    if yc and years:
        print(f"\n  Generating per-year accident maps ({len(years)} years)...")
        for year in years:
            try:
                ydf = df[df[yc] == year]
                if len(ydf) == 0:
                    continue
                year_str = str(year)
                m = folium.Map(location=[24.95, 121.25], zoom_start=10)
                add_free_basemaps(m)
                summary = ydf.groupby(ac)[cc].sum() if cc else ydf[ac].value_counts()
                for area, count in summary.items():
                    coords = None
                    for key, coord in TAOYUAN_AREAS.items():
                        if key in str(area) or str(area) in key:
                            coords = coord
                            break
                    if coords:
                        r = min(max(float(count)**0.5*2, 5), 50)
                        popup = f"<b>{year} {area}</b><br>Cases: {int(count)}"
                        if dc and dc in ydf.columns:
                            popup += f"<br>Deaths: {int(ydf[ydf[ac]==area][dc].sum())}"
                        if ic and ic in ydf.columns:
                            popup += f"<br>Injuries: {int(ydf[ydf[ac]==area][ic].sum())}"
                        folium.CircleMarker(location=coords, radius=r,
                            popup=folium.Popup(popup,max_width=250),
                            color="orange", fill=True, fill_color="orange", fill_opacity=0.6).add_to(m)
                folium.LayerControl().add_to(m)
                m.save(f"docs/maps/accident_map_{year_str}.html")
                year_maps[year_str] = f"maps/accident_map_{year_str}.html"
                print(f"    Generated: maps/accident_map_{year_str}.html")
            except Exception as e:
                print(f"    [Warning] {year} map failed: {e}")

    print(f"  Accident maps: 1 combined, {len(year_maps)} per-year")
    return year_maps, all_map


def generate_index(v_data, a_data):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    v_year_figs = v_data.get("year_figs", {})
    v_all_figs = v_data.get("all_figs", [])
    v_year_maps = v_data.get("year_maps", {})
    v_all_map = v_data.get("all_map")
    v_years = v_data.get("years", [])
    v_sample = v_data.get("is_sample", False)

    a_year_figs = a_data.get("year_figs", {})
    a_all_figs = a_data.get("all_figs", [])
    a_year_maps = a_data.get("year_maps", {})
    a_all_map = a_data.get("all_map")
    a_years = a_data.get("years", [])
    a_sample = a_data.get("is_sample", False)

    all_years = sorted(set([str(y) for y in v_years] + [str(y) for y in a_years]))

    sample_banner = ""
    if v_sample or a_sample:
        sample_banner = '<div style="background:#fff3cd;border:1px solid #ffeaa7;border-radius:8px;padding:1rem;margin:1rem 0;text-align:center;color:#856404;"><strong>Note:</strong> Currently displaying sample data. API connection may have failed. Check GitHub Actions logs.</div>'

    year_options = '<option value="all">All Years</option>\n'
    for year in all_years:
        year_options += f'    <option value="{year}">{year}</option>\n'

    chart_switch_js = """
function switchCharts(section, year) {
    var allContainer = document.getElementById(section + '_charts_all');
    if (allContainer) allContainer.style.display = 'none';
    var yearContainers = document.querySelectorAll('[id^="' + section + '_charts_"]');
    yearContainers.forEach(function(el) {
        if (el.id !== section + '_charts_all') el.style.display = 'none';
    });
    if (year === 'all') {
        if (allContainer) allContainer.style.display = 'grid';
    } else {
        var target = document.getElementById(section + '_charts_' + year);
        if (target) target.style.display = 'grid';
    }
}

function switchMap(section, year) {
    var allFrame = document.getElementById(section + '_map_all');
    if (allFrame) allFrame.style.display = 'none';
    var yearFrames = document.querySelectorAll('[id^="' + section + '_map_"]');
    yearFrames.forEach(function(el) {
        if (el.id !== section + '_map_all') el.style.display = 'none';
    });
    if (year === 'all') {
        if (allFrame) allFrame.style.display = 'block';
    } else {
        var target = document.getElementById(section + '_map_' + year);
        if (target) target.style.display = 'block';
    }
}

function switchYear(section, year) {
    switchCharts(section, year);
    switchMap(section, year);
}
"""

    def build_chart_grid(filenames, section, year_key):
        if not filenames:
            return '<p style="padding:2rem;color:#888;text-align:center;">No data available</p>'
        display = "grid" if year_key == "all" else "none"
        html = f'<div id="{section}_charts_{year_key}" class="chart-grid" style="display:{display};">'
        for fn in filenames:
            if not fn:
                continue
            name = fn.replace(".html","").replace("violation_","").replace("accident_","").replace("_all","").replace("_"," ").title()
            path = f"charts/{fn}"
            html += f'<div class="chart-card"><h3>{name}</h3><iframe src="{path}" width="100%" height="450"></iframe></div>'
        html += '</div>'
        return html

    def build_map(filename, section, year_key):
        if not filename:
            return '<p style="padding:2rem;color:#888;text-align:center;">No map data available</p>'
        display = "block" if year_key == "all" else "none"
        return f'<iframe id="{section}_map_{year_key}" src="{filename}" width="100%" height="600" style="display:{display};border-radius:8px;border:none;"></iframe>'

    v_charts_html = build_chart_grid(v_all_figs, "violation", "all")
    for year, filenames in v_year_figs.items():
        v_charts_html += build_chart_grid(filenames, "violation", year)

    v_maps_html = ""
    if v_all_map:
        v_maps_html += build_map(v_all_map, "violation", "all")
    for year, filename in v_year_maps.items():
        v_maps_html += build_map(filename, "violation", year)
    if not v_maps_html:
        v_maps_html = '<p style="padding:2rem;color:#888;text-align:center;">No map data available</p>'

    a_charts_html = build_chart_grid(a_all_figs, "accident", "all")
    for year, filenames in a_year_figs.items():
        a_charts_html += build_chart_grid(filenames, "accident", year)

    a_maps_html = ""
    if a_all_map:
        a_maps_html += build_map(a_all_map, "accident", "all")
    for year, filename in a_year_maps.items():
        a_maps_html += build_map(filename, "accident", year)
    if not a_maps_html:
        a_maps_html = '<p style="padding:2rem;color:#888;text-align:center;">No map data available</p>'

    css = """:root{--primary:#1a5276;--secondary:#2874a6;--accent:#e74c3c;--bg:#f8f9fa;--card-bg:#ffffff;--text:#2c3e50;--border:#dee2e6}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Segoe UI","Microsoft JhengHei",sans-serif;background:var(--bg);color:var(--text);line-height:1.6}
header{background:linear-gradient(135deg,var(--primary),var(--secondary));color:white;padding:2rem 1rem;text-align:center}
header h1{font-size:1.8rem;margin-bottom:0.5rem}
nav{background:#1a5276;padding:0.5rem 1rem;text-align:center;position:sticky;top:0;z-index:100;box-shadow:0 2px 4px rgba(0,0,0,0.1)}
nav a{color:white;text-decoration:none;margin:0 1rem;font-size:0.95rem;padding:0.3rem 0.8rem;border-radius:4px;display:inline-block}
nav a:hover{background:rgba(255,255,255,0.2)}
.update-time{text-align:center;padding:0.5rem;background:#e8f4f8;font-size:0.85rem;color:#555}
main{max-width:1400px;margin:0 auto;padding:1.5rem}
.section-title{font-size:1.4rem;color:var(--primary);margin:2rem 0 1rem;padding-bottom:0.5rem;border-bottom:3px solid var(--secondary);display:flex;align-items:center;gap:1rem;flex-wrap:wrap}
.year-selector{background:white;border:1px solid var(--border);border-radius:6px;padding:0.4rem 0.8rem;font-size:1rem;color:var(--text);cursor:pointer}
.chart-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(500px,1fr));gap:1.5rem;margin-bottom:1.5rem}
.chart-card,.map-card{background:var(--card-bg);border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.08);padding:1rem;transition:transform 0.2s}
.chart-card:hover,.map-card:hover{transform:translateY(-2px);box-shadow:0 4px 16px rgba(0,0,0,0.12)}
.chart-card h3,.map-card h3{font-size:1rem;color:var(--primary);margin-bottom:0.75rem;padding-left:0.5rem;border-left:4px solid var(--accent)}
.map-card{margin-bottom:1.5rem}
iframe{border-radius:8px;width:100%;border:none}
footer{text-align:center;padding:1.5rem;color:#888;font-size:0.8rem;border-top:1px solid var(--border)}
footer a{color:var(--secondary);text-decoration:none}
@media(max-width:600px){.chart-grid{grid-template-columns:1fr}header h1{font-size:1.3rem}nav a{margin:0 0.3rem;font-size:0.85rem}.section-title{font-size:1.1rem}}"""

    html = f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Taoyuan Traffic Report</title>
<style>{css}</style>
<script>{chart_switch_js}</script>
</head>
<body>
<header><h1>Taoyuan Traffic Violation & Accident Report</h1><p>Data Source: Taoyuan Open Data Platform | Auto-updated via GitHub Actions</p></header>
<nav><a href="#violations">Traffic Violations</a><a href="#accidents">Accident Analysis</a></nav>
<div class="update-time">Report Generated: {now}</div>
{sample_banner}
<main>

<section id="violations">
<div class="section-title">
  Traffic Violation Analysis
  <select class="year-selector" onchange="switchYear('violation', this.value)">
{year_options}  </select>
</div>
{v_charts_html}
<div class="map-card"><h3>Violation Location Map</h3>
{v_maps_html}
<p style="font-size:0.8rem;color:#888;margin-top:0.5rem;">Free basemaps: OpenStreetMap, CartoDB Positron/Dark, Esri Satellite. Use the layer control (top-right) to switch. Combined map supports year switching via left layer menu.</p>
</div>
</section>

<section id="accidents">
<div class="section-title">
  Accident Analysis
  <select class="year-selector" onchange="switchYear('accident', this.value)">
{year_options}  </select>
</div>
{a_charts_html}
<div class="map-card"><h3>Accident Hotspot Map</h3>
{a_maps_html}
<p style="font-size:0.8rem;color:#888;margin-top:0.5rem;">Free basemaps: OpenStreetMap, CartoDB Positron/Dark, Esri Satellite. Use the layer control (top-right) to switch. Combined map supports year switching via left layer menu.</p>
</div>
</section>

</main>
<footer><p>Data Source: <a href="https://opendata.tycg.gov.tw" target="_blank">Taoyuan Open Data Platform</a></p><p>Auto-generated by GitHub Actions. For reference only.</p></footer>
</body>
</html>'''

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    size = os.path.getsize("docs/index.html")
    print(f"\n[Done] docs/index.html ({size} bytes)")
    return "docs/index.html"


def main():
    print("=" * 60)
    print("Taoyuan Traffic Report Generator v4.0")
    print("=" * 60)

    v_data = {"year_figs": {}, "all_figs": [], "year_maps": {}, "all_map": None, "years": [], "is_sample": False}
    a_data = {"year_figs": {}, "all_figs": [], "year_maps": {}, "all_map": None, "years": [], "is_sample": False}

    try:
        va = analyze_violations()
        if va:
            v_data["years"] = va["years"]
            v_data["is_sample"] = va.get("is_sample", False)
            v_year_figs, v_all_figs = make_violation_charts(va)
            v_year_maps, v_all_map = make_violation_maps(va)
            v_data["year_figs"] = v_year_figs
            v_data["all_figs"] = v_all_figs
            v_data["year_maps"] = v_year_maps
            v_data["all_map"] = v_all_map
    except Exception as e:
        print(f"\n[Error] Violation analysis: {e}")
        traceback.print_exc()

    try:
        aa = analyze_accidents()
        if aa:
            a_data["years"] = aa["years"]
            a_data["is_sample"] = aa.get("is_sample", False)
            a_year_figs, a_all_figs = make_accident_charts(aa)
            a_year_maps, a_all_map = make_accident_maps(aa)
            a_data["year_figs"] = a_year_figs
            a_data["all_figs"] = a_all_figs
            a_data["year_maps"] = a_year_maps
            a_data["all_map"] = a_all_map
    except Exception as e:
        print(f"\n[Error] Accident analysis: {e}")
        traceback.print_exc()

    print("\n" + "-" * 60)
    print("Generating index...")
    print("-" * 60)
    try:
        generate_index(v_data, a_data)
    except Exception as e:
        print(f"[Error] Index generation: {e}")
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("Done. Output: docs/index.html")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
