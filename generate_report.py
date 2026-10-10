#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
桃園市交通裁罰及傷亡資訊報告生成器
直接從 API 介接資料，不儲存中間存中間檔案，減少儲存負擔
"""

import requests
import json
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from folium.plugins import MarkerCluster
from datetime import datetime

os.makedirs("docs", exist_ok=True)

BASE_URL = "https://data.tycg.gov.tw/api/v1/rest/datastore"

# ========== API 資料得 ==========

def api_get(url, params=None, timeout=120):
    """通用 API GET 請求"""
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"API 請求失敗: {url} | 錯誤: {e}")
        return None


def get_dataset_metadata(dataset_id):
    """取得資料集詮釋資料，提取 resource ID 列表"""
    url = f"https://data.tycg.gov.tw/api/v1/rest/dataset/{dataset_id}"
    data = api_get(url, timeout=60)
    if not data or "result" not in data:
        return []
    result = data["result"]
    resources = result.get("resources") or result.get("resource") or []
    # 回傳 (resource_id, resource_name) 列表
    out = []
    for r in resources:
        rid = r.get("id", "")
        rname = r.get("name") or r.get("resource_name", "")
        if rid:
            out.append((rid, rname))
    return out


def fetch_resource_records(resource_id, limit=100000):
    """ API 取得單一 resource 的資料記錄"""
    url = f"{BASE_URL}/{resource_id}"
    params = {"format": "json", "limit": limit}
    data = api_get(url, params=params)
    if not data:
        return []
    result = data.get("result", {})
    records = result.get("records") or result.get("results") or []
    return records


def fetch_dataset_all_records(dataset_id, dataset_name=""):
    """
    取得資料集下所有 resource 的記錄，直接合併回傳 DataFrame
    不寫入檔案，全程記憶體處理
    """
    resources = get_dataset_metadata(dataset_id)
    all_records = []
    print(f"[{dataset_name}] 發現 {len(resources)} 個 resource")
    for rid, rname in resources:
        print(f"  介接: {rname} (ID: {rid})")
        records = fetch_resource_records(rid)
        if records:
            print(f"    取得 {len(records)} 筆")
            for r in records:
                r["_source_resource"] = rname
            all_records.extend(records)
        else:
            print(f"    無資料")
    if not all_records:
        # fallback: 嘗試直接用 dataset_id 作為 resource_id
        print(f"  fallback: 嘗試直接用 dataset_id 介接")
        records = fetch_resource_records(dataset_id)
        if records:
            print(f"    取得 {len(records)} 筆")
            all_records.extend(records)
    return pd.DataFrame(all_records)


# ========== 交通違規裁罰分析 ==========

VIOLATION_DATASET_ID = "08b2987e-01e5-458d-a8c1-cd4b540a0105"


def analyze_violations_from_api():
    """直接從 API 取得違規裁罰資料並分析"""
    print("\n===== 交通違規裁罰資料 =====")
    df = fetch_dataset_all_records(VIOLATION_DATASET_ID, "交通違規舉發")
    if df.empty:
        print("未取得違規資料")
        return None
    print(f"總筆數: {len(df)}")

    # 自動偵測欄位
    year_col = next((c for c in df.columns if "year" in c.lower() or "年度" in c or c == "年"), None)
    law_col = next((c for c in df.columns if "law" in c.lower() or "法條" in c), None)
    fact_col = next((c for c in df.columns if "fact" in c.lower() or "違規事實" in c or "事實" in c), None)
    area_col = next((c for c in df.columns if "area" in c.lower() or "行政區" in c or "區" in c), None)
    lat_col = next((c for c in df.columns if "lat" in c.lower() or "緯度" in c), None)
    lon_col = next((c for c in df.columns if "lon" in c.lower() or "經度" in c), None)
    road_col = next((c for c in df.columns if "road" in c.lower() or "路段" in c or "路" in c), None)

    print(f"欄位: year={year_col}, law={law_col}, fact={fact_col}, area={area_col}, lat={lat_col}, lon={lon_col}")

    year_counts = df[year_col].value_counts().sort_index() if year_col and year_col in df.columns else pd.Series(dtype=int)
    law_counts = df[law_col].value_counts().head(20) if law_col and law_col in df.columns else pd.Series(dtype=int)
    fact_counts = df[fact_col].value_counts().head(20) if fact_col and fact_col in df.columns else pd.Series(dtype=int)
    area_counts = df[area_col].value_counts() if area_col and area_col in df.columns else pd.Series(dtype=int)

    return {
        "df": df, "year_col": year_col, "law_col": law_col, "fact_col": fact_col,
        "area_col": area_col, "lat_col": lat_col, "lon_col": lon_col, "road_col": road_col,
        "year_counts": year_counts, "law_counts": law_counts,
        "fact_counts": fact_counts, "area_counts": area_counts,
    }


def create_violation_charts(a):
    if a is None:
        return []
    figs = []
    df = a["df"]

    # 1. 各年度裁罰件數趨勢
    if len(a["year_counts"]) > 0:
        fig = px.bar(
            x=a["year_counts"].index.astype(str), y=a["year_counts"].values,
            labels={"x": "年度", "y": "裁罰件數"},
            title="各年度交通違規裁罰件數統計",
            color=a["year_counts"].values, color_continuous_scale="Reds"
        )
        fig.update_layout(template="plotly_white")
        fig.write_html("docs/violation_yearly_trend.html", include_plotlyjs="cdn")
        figs.append("violation_yearly_trend.html")

    # 2. 主要違反法條 TOP 15
    if len(a["law_counts"]) > 0:
        fig = px.bar(
            y=a["law_counts"].head(15).index[::-1],
            x=a["law_counts"].head(15).values[::-1],
            orientation="h",
            labels={"y": "違反法條", "x": "件數"},
            title="主要違反法條 TOP 15",
            color=a["law_counts"].head(15).values[::-1], color_continuous_scale="Oranges"
        )
        fig.update_layout(template="plotly_white", height=600)
        fig.write_html("docs/violation_top_laws.html", include_plotlyjs="cdn")
        figs.append("violation_top_laws.html")

    # 3. 主要違規事實 TOP 15
    if len(a["fact_counts"]) > 0:
        fig = px.bar(
            y=a["fact_counts"].head(15).index[::-1],
            x=a["fact_counts"].head(15).values[::-1],
            orientation="h",
            labels={"y": "違規事實", "x": "件數"},
            title="主要違規事實 TOP 15",
            color=a["fact_counts"].head(15).values[::-1], color_continuous_scale="Blues"
        )
        fig.update_layout(template="plotly_white", height=600)
        fig.write_html("docs/violation_top_facts.html", include_plotlyjs="cdn")
        figs.append("violation_top_facts.html")

    # 4. 行政區分布
    if len(a["area_counts"]) > 0:
        fig = px.bar(
            x=a["area_counts"].index, y=a["area_counts"].values,
            labels={"x": "行政區", "y": "裁罰件數"},
            title="各行政區交通違規裁罰分布",
            color=a["area_counts"].values, color_continuous_scale="Purples"
        )
        fig.update_layout(template="plotly_white", xaxis_tickangle=-45)
        fig.write_html("docs/violation_area_distribution.html", include_plotlyjs="cdn")
        figs.append("violation_area_distribution.html")

    # 5. 年度 x 行政區熱力圖
    year_col = a["year_col"]
    area_col = a["area_col"]
    if year_col and year_col in df.columns and area_col and area_col in df.columns:
        pivot = df.groupby([year_col, area_col]).size().unstack(fill_value=0)
        if pivot.shape[0] > 0 and pivot.shape[1] > 0:
            fig = px.imshow(
                pivot, labels=dict(x="行政區", y="年度", color="件數"),
                title="各年度行政區違規裁罰熱力圖",
                aspect="auto", color_continuous_scale="YlOrRd"
            )
            fig.update_layout(template="plotly_white", height=500)
            fig.write_html("docs/violation_heatmap.html", include_plotlyjs="cdn")
            figs.append("violation_heatmap.html")

    print(f"違規圖表: {len(figs)} 個")
    return figs


def create_violation_map(a):
    if a is None:
        return None
    df = a["df"]
    lat_col = a["lat_col"]
    lon_col = a["lon_col"]
    year_col = a["year_col"]
    law_col = a["law_col"]
    fact_col = a["fact_col"]
    area_col = a["area_col"]
    road_col = a["road_col"]

    if not lat_col or lat_col not in df.columns or not lon_col or lon_col not in df.columns:
        print("缺少經緯度資料，略過違規地圖")
        return None

    df_map = df.copy()
    df_map[lat_col] = pd.to_numeric(df_map[lat_col], errors="coerce")
    df_map[lon_col] = pd.to_numeric(df_map[lon_col], errors="coerce")
    df_map = df_map.dropna(subset=[lat_col, lon_col])
    if len(df_map) == 0:
        print("無有效座標")
        return None

    center_lat = df_map[lat_col].median()
    center_lon = df_map[lon_col].median()
    m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles="CartoDB positron")

    if year_col and year_col in df_map.columns:
        for year in sorted(df_map[year_col].dropna().unique()):
            year_df = df_map[df_map[year_col] == year]
            if len(year_df) == 0:
                continue
            fg = folium.FeatureGroup(name=f"{year}年違規裁罰點位")
            mc = MarkerCluster().add_to(fg)
            for _, row in year_df.iterrows():
                popup = f"<b>年度:</b> {row.get(year_col, 'N/A')}<br>"
                if area_col:
                    popup += f"<b>行政區:</b> {row.get(area_col, 'N/A')}<br>"
                if road_col:
                    popup += f"<b>路段:</b> {row.get(road_col, 'N/A')}<br>"
                if law_col:
                    popup += f"<b>法條:</b> {str(row.get(law_col, 'N/A'))[:50]}<br>"
                if fact_col:
                    popup += f"<b>事實:</b> {str(row.get(fact_col, 'N/A'))[:50]}"
                folium.CircleMarker(
                    location=[row[lat_col], row[lon_col]], radius=3,
                    popup=folium.Popup(popup, max_width=300),
                    color="red", fill=True, fill_opacity=0.6
                ).add_to(mc)
            fg.add_to(m)
    else:
        mc = MarkerCluster().add_to(m)
        for _, row in df_map.iterrows():
            popup = ""
            if area_col:
                popup += f"<b>行政區:</b> {row.get(area_col, 'N/A')}<br>"
            if road_col:
                popup += f"<b>路段:</b> {row.get(road_col, 'N/A')}<br>"
            if law_col:
                popup += f"<b>法條:</b> {str(row.get(law_col, 'N/A'))[:50]}"
            folium.CircleMarker(
                location=[row[lat_col], row[lon_col]], radius=3,
                popup=folium.Popup(popup, max_width=300),
                color="red", fill=True, fill_opacity=0.6
            ).add_to(mc)

    folium.LayerControl().add_to(m)
    m.save("docs/violation_map.html")
    print("已生成違規裁罰分布地圖")
    return "violation_map.html"


# ========== 交通事故分析 ==========

ACCIDENT_DATASET_ID = "24bf2215-8c80-439e-b553-59ccfc82ca78"

TAOYUAN_AREAS = {
    "桃園區": [24.989, 121.313], "中壢區": [24.965, 121.221],
    "平鎮區": [24.947, 121.206], "八德區": [24.930, 121.290],
    "楊梅區": [24.907, 121.146], "蘆竹區": [25.045, 121.290],
    "大溪區": [24.883, 121.288], "龍潭區": [24.864, 121.211],
    "龜山區": [25.022, 121.400], "大園區": [25.066, 121.197],
    "觀音區": [25.036, 121.133], "新屋區": [24.974, 121.106],
    "復興區": [24.817, 121.375],
}


def analyze_accidents_from_api():
    """直接從 API 取得交通事故資料並分析"""
    print("\n===== 交通事故熱點資料 =====")
    df = fetch_dataset_all_records(ACCIDENT_DATASET_ID, "交通事故熱點")
    if df.empty:
        print("未取得事故資料")
        return None
    print(f"總筆數: {len(df)}")

    year_col = next((c for c in df.columns if "year" in c.lower() or "年度" in c or c == "年度"), None)
    type_col = next((c for c in df.columns if "類別" in c or "type" in c.lower() or "事故" in c), None)
    area_col = next((c for c in df.columns if "地區" in c or "area" in c.lower() or "區" in c), None)
    place_col = next((c for c in df.columns if "場所" in c or "place" in c.lower()), None)
    vehicle_col = next((c for c in df.columns if "運具" in c or "vehicle" in c.lower() or "車" in c), None)
    count_col = next((c for c in df.columns if "案件總數" in c or "count" in c.lower() or "總數" in c), None)
    death_col = next((c for c in df.columns if "死亡" in c or "death" in c.lower()), None)
    injury_col = next((c for c in df.columns if "受傷" in c or "injury" in c.lower()), None)

    print(f"欄位: year={year_col}, type={type_col}, area={area_col}, count={count_col}, death={death_col}, injury={injury_col}")

    if count_col and count_col in df.columns:
        df[count_col] = pd.to_numeric(df[count_col], errors="coerce").fillna(0)
    if death_col and death_col in df.columns:
        df[death_col] = pd.to_numeric(df[death_col], errors="coerce").fillna(0)
    if injury_col and injury_col in df.columns:
        df[injury_col] = pd.to_numeric(df[injury_col], errors="coerce").fillna(0)

    year_stats = None
    if year_col and year_col in df.columns:
        df[year_col] = df[year_col].astype(str)
        if count_col and count_col in df.columns:
            year_stats = df.groupby(year_col)[count_col].sum().sort_index()
        else:
            year_stats = df[year_col].value_counts().sort_index()

    type_stats = None
    if type_col and type_col in df.columns:
        type_stats = df.groupby(type_col)[count_col].sum().sort_values(ascending=False) if count_col else df[type_col].value_counts()

    area_stats = None
    if area_col and area_col in df.columns:
        area_stats = df.groupby(area_col)[count_col].sum().sort_values(ascending=False) if count_col else df[area_col].value_counts()

    place_stats = None
    if place_col and place_col in df.columns:
        place_stats = df.groupby(place_col)[count_col].sum().sort_values(ascending=False) if count_col else df[place_col].value_counts()

    vehicle_stats = None
    if vehicle_col and vehicle_col in df.columns:
        vehicle_stats = df.groupby(vehicle_col)[count_col].sum().sort_values(ascending=False) if count_col else df[vehicle_col].value_counts()

    death_injury_stats = None
    if year_col and year_col in df.columns:
        agg_dict = {}
        if count_col:
            agg_dict["案件總數"] = (count_col, "sum")
        if death_col:
            agg_dict["死亡總數"] = (death_col, "sum")
        if injury_col:
            agg_dict["受傷總數"] = (injury_col, "sum")
        if agg_dict:
            death_injury_stats = df.groupby(year_col).agg(**agg_dict)

    return {
        "df": df, "year_col": year_col, "type_col": type_col, "area_col": area_col,
        "place_col": place_col, "vehicle_col": vehicle_col, "count_col": count_col,
        "death_col": death_col, "injury_col": injury_col,
        "year_stats": year_stats, "type_stats": type_stats, "area_stats": area_stats,
        "place_stats": place_stats, "vehicle_stats": vehicle_stats,
        "death_injury_stats": death_injury_stats,
    }


def create_accident_charts(a):
    if a is None:
        return []
    figs = []

    if a["year_stats"] is not None and len(a["year_stats"]) > 0:
        fig = px.bar(
            x=a["year_stats"].index.astype(str), y=a["year_stats"].values,
            labels={"x": "年度", "y": "事故件數"},
            title="各年度交通事故件數統計",
            color=a["year_stats"].values, color_continuous_scale="Reds"
        )
        fig.update_layout(template="plotly_white")
        fig.write_html("docs/accident_yearly_trend.html", include_plotlyjs="cdn")
        figs.append("accident_yearly_trend.html")

    if a["type_stats"] is not None and len(a["type_stats"]) > 0:
        fig = px.pie(
            names=a["type_stats"].index, values=a["type_stats"].values,
            title="主要事故類別分布", hole=0.4
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(template="plotly_white")
        fig.write_html("docs/accident_type_distribution.html", include_plotlyjs="cdn")
        figs.append("accident_type_distribution.html")

    if a["area_stats"] is not None and len(a["area_stats"]) > 0:
        fig = px.bar(
            x=a["area_stats"].index, y=a["area_stats"].values,
            labels={"x": "地區", "y": "事故件數"},
            title="各行政區交通事故分布",
            color=a["area_stats"].values, color_continuous_scale="Oranges"
        )
        fig.update_layout(template="plotly_white", xaxis_tickangle=-45)
        fig.write_html("docs/accident_area_distribution.html", include_plotlyjs="cdn")
        figs.append("accident_area_distribution.html")

    if a["place_stats"] is not None and len(a["place_stats"]) > 0:
        fig = px.bar(
            y=a["place_stats"].head(15).index[::-1],
            x=a["place_stats"].head(15).values[::-1],
            orientation="h",
            labels={"y": "場所類別", "x": "事故件數"},
            title="事故場所類別分布 TOP 15",
            color=a["place_stats"].head(15).values[::-1], color_continuous_scale="Blues"
        )
        fig.update_layout(template="plotly_white")
        fig.write_html("docs/accident_place_distribution.html", include_plotlyjs="cdn")
        figs.append("accident_place_distribution.html")

    if a["vehicle_stats"] is not None and len(a["vehicle_stats"]) > 0:
        fig = px.bar(
            y=a["vehicle_stats"].head(15).index[::-1],
            x=a["vehicle_stats"].head(15).values[::-1],
            orientation="h",
            labels={"y": "運具類別", "x": "事故件數"},
            title="事故運具類別分布 TOP 15",
            color=a["vehicle_stats"].head(15).values[::-1], color_continuous_scale="Greens"
        )
        fig.update_layout(template="plotly_white")
        fig.write_html("docs/accident_vehicle_distribution.html", include_plotlyjs="cdn")
        figs.append("accident_vehicle_distribution.html")

    if a["death_injury_stats"] is not None and len(a["death_injury_stats"]) > 0:
        fig = go.Figure()
        for col in a["death_injury_stats"].columns:
            fig.add_trace(go.Scatter(
                x=a["death_injury_stats"].index.astype(str),
                y=a["death_injury_stats"][col].values,
                mode="lines+markers", name=col,
            ))
        fig.update_layout(
            title="各年度交通事故傷亡趨勢",
            xaxis_title="年度", yaxis_title="人數/件數",
            template="plotly_white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        fig.write_html("docs/accident_casualty_trend.html", include_plotlyjs="cdn")
        figs.append("accident_casualty_trend.html")

    print(f"事故圖表: {len(figs)} 個")
    return figs


def match_area_coords(area_name):
    area_key = str(area_name).replace("桃園市", "").replace("區", "區")
    for key, coord in TAOYUAN_AREAS.items():
        if key in area_key or area_key in key:
            return coord
    return None


def create_accident_map(a):
    if a is None:
        return None
    df = a["df"]
    area_col = a["area_col"]
    count_col = a["count_col"]
    death_col = a["death_col"]
    injury_col = a["injury_col"]
    year_col = a["year_col"]

    m = folium.Map(location=[24.95, 121.25], zoom_start=10, tiles="CartoDB positron")

    if year_col and year_col in df.columns:
        for year in sorted(df[year_col].dropna().unique()):
            year_df = df[df[year_col] == year]
            if len(year_df) == 0:
                continue
            fg = folium.FeatureGroup(name=f"{year}年事故熱點")
            if area_col and area_col in year_df.columns:
                summary = year_df.groupby(area_col)[count_col].sum() if count_col else year_df[area_col].value_counts()
                for area, count in summary.items():
                    coords = match_area_coords(area)
                    if coords:
                        radius = min(max(float(count) ** 0.5 * 2, 5), 50)
                        popup = f"<b>{year}年 {area}</b><br>事故件數: {int(count)}"
                        if death_col and death_col in year_df.columns:
                            deaths = year_df[year_df[area_col] == area][death_col].sum()
                            popup += f"<br>死亡: {int(deaths)}"
                        if injury_col and injury_col in year_df.columns:
                            injuries = year_df[year_df[area_col] == area][injury_col].sum()
                            popup += f"<br>受傷: {int(injuries)}"
                        folium.CircleMarker(
                            location=coords, radius=radius,
                            popup=folium.Popup(popup, max_width=250),
                            color="orange", fill=True, fill_color="orange", fill_opacity=0.6
                        ).add_to(fg)
            fg.add_to(m)
    else:
        if area_col and area_col in df.columns:
            summary = df.groupby(area_col)[count_col].sum() if count_col else df[area_col].value_counts()
            for area, count in summary.items():
                coords = match_area_coords(area)
                if coords:
                    radius = min(max(float(count) ** 0.5 * 2, 5), 50)
                    popup = f"<b>{area}</b><br>事故件數: {int(count)}"
                    folium.CircleMarker(
                        location=coords, radius=radius,
                        popup=folium.Popup(popup, max_width=250),
                        color="orange", fill=True, fill_color="orange", fill_opacity=0.6
                    ).add_to(m)

    folium.LayerControl().add_to(m)
    m.save("docs/accident_map.html")
    print("已生成交通事故熱點地圖")
    return "accident_map.html"


# ========== 主報告頁面 ==========

def generate_index(violation_figs, accident_figs, violation_map, accident_map):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    v_section = ""
    if violation_figs:
        v_section = '<h2 class="section-title">交通違規裁罰分析</h2><div class="chart-grid">'
        for fig in violation_figs:
            name = fig.replace(".html", "").replace("violation_", "").replace("_", " ").title()
            v_section += f'<div class="chart-card"><h3>{name}</h3><iframe src="{fig}" width="100%" height="450"></iframe></div>'
        v_section += "</div>"
        if violation_map:
            v_section += f'<div class="map-card"><h3>違規裁罰點位分布地圖</h3><iframe src="{violation_map}" width="100%" height="600"></iframe></div>'

    a_section = ""
    if accident_figs:
        a_section = '<h2 class="section-title">交通事故分析</h2><div class="chart-grid">'
        for fig in accident_figs:
            name = fig.replace(".html", "").replace("accident_", "").replace("_", " ").title()
            a_section += f'<div class="chart-card"><h3>{name}</h3><iframe src="{fig}" width="100%" height="450"></iframe></div>'
        a_section += "</div>"
        if accident_map:
            a_section += f'<div class="map-card"><h3>交通事故熱點分布地圖</h3><iframe src="{accident_map}" width="100%" height="600"></iframe></div>'

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>桃園市交通裁罰及傷亡資訊報告</title>
<style>
:root {{ --primary: #1a5276; --secondary: #2874a6; --accent: #e74c3c; --bg: #f8f9fa; --card-bg: #ffffff; --text: #2c3e50; --border: #dee2e6; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: "Segoe UI", "Microsoft JhengHei", sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }}
header {{ background: linear-gradient(135deg, var(--primary), var(--secondary)); color: white; padding: 2rem 1rem; text-align: center; }}
header h1 {{ font-size: 1.8rem; margin-bottom: 0.5rem; }}
header p {{ opacity: 0.9; font-size: 0.95rem; }}
.update-time {{ text-align: center; padding: 0.5rem; background: #e8f4f8; font-size: 0.85rem; color: #555; }}
main {{ max-width: 1400px; margin: 0 auto; padding: 1.5rem; }}
.section-title {{ font-size: 1.4rem; color: var(--primary); margin: 2rem 0 1rem; padding-bottom: 0.5rem; border-bottom: 3px solid var(--secondary); }}
.chart-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 1.5rem; margin-bottom: 1.5rem; }}
.chart-card, .map-card {{ background: var(--card-bg); border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); padding: 1rem; transition: transform 0.2s; }}
.chart-card:hover, .map-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,0.12); }}
.chart-card h3, .map-card h3 {{ font-size: 1rem; color: var(--primary); margin-bottom: 0.75rem; padding-left: 0.5rem; border-left: 4px solid var(--accent); }}
.map-card {{ margin-bottom: 1.5rem; }}
iframe {{ border-radius: 8px; width: 100%; border: none; }}
footer {{ text-align: center; padding: 1.5rem; color: #888; font-size: 0.8rem; border-top: 1px solid var(--border); }}
footer a {{ color: var(--secondary); text-decoration: none; }}
@media (max-width: 600px) {{ .chart-grid {{ grid-template-columns: 1fr; }} header h1 {{ font-size: 1.3rem; }} }}
</style>
</head>
<body>
<header><h1>桃園市交通裁罰及傷亡資訊報告</h1><p>資料來源：桃園資料開放平台 | 透過 GitHub Actions 自動更新</p></header>
<div class="update-time">報告生成時間：{now}</div>
<main>{v_section}{a_section}</main>
<footer><p>資料來源：<a href="https://opendata.tycg.gov.tw" target="_blank">桃園資料開放平台</a></p><p>本報告由 GitHub Actions 自動生成，僅供參考</p></footer>
</body>
</html>"""

    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("已生成主報告頁面")


# ========== 主程式 ==========

def main():
    print("=" * 60)
    print("桃園市交通裁罰及傷亡資訊報告生成器")
    print("模式: API 直接介接，不儲存中間資料")
    print("=" * 60)

    # 違規裁罰
    va = analyze_violations_from_api()
    vf = create_violation_charts(va)
    vm = create_violation_map(va)

    # 交通事故
    aa = analyze_accidents_from_api()
    af = create_accident_charts(aa)
    am = create_accident_map(aa)

    # 主頁面
    generate_index(vf, af, vm, am)

    print("\n" + "=" * 60)
    print("報告生成完成！輸出: docs/")
    print("=" * 60)


if __name__ == "__main__":
    main()
