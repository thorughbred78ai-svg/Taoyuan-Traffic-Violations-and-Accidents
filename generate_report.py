#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
桃園市交通裁罰及傷亡資訊報告生成器 v2.1
直接從 API 介接資料，不儲存中間檔案
API 失敗時自動使用範例資料產生報告
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

API_TIMEOUT = 60
API_RETRY = 3

API_BASES = [
    "https://opendata.tycg.gov.tw/api/v1/rest",
    "https://data.tycg.gov.tw/api/v1/rest",
]

VIOLATION_DATASET_ID = "08b2987e-01e5-458d-a8c1-cd4b540a0105"

ACCIDENT_DATASET_IDS = [
    "08d560b5-7cf2-4909-8a02-da39c74d8b09",
    "db5055c9-9f2e-4546-8e58-e413dfbbcdeb",
    "f4c49615-1120-4fd5-8ada-e9a77b1c784e",
]

TAOYUAN_AREAS = {
    "桃園區": [24.989, 121.313], "中壢區": [24.965, 121.221],
    "平鎮區": [24.947, 121.206], "八德區": [24.930, 121.290],
    "楊梅區": [24.907, 121.146], "蘆竹區": [25.045, 121.290],
    "大溪區": [24.883, 121.288], "龍潭區": [24.864, 121.211],
    "龜山區": [25.022, 121.400], "大園區": [25.066, 121.197],
    "觀音區": [25.036, 121.133], "新屋區": [24.974, 121.106],
    "復興區": [24.817, 121.375],
}

VIOLATION_LAWS = [
    "未依規定使用燈光", "未保持行車安全距離", "變換車道未依規定使用方向燈",
    "超速行駛", "闖紅燈", "未禮讓行人", "違規停車", "未依標線行駛",
    "未繫安全帶", "使用手持行動電話", "逆向行駛", "未依號誌行駛",
    "違規迴車", "未依規定車道行駛", "違規變換車道",
]

VIOLATION_FACTS = [
    "行駛中未保持安全距離", "變換車道未打方向燈", "闖紅燈右轉",
    "行駛中超速", "行人穿越道未禮讓行人", "紅燈越線", "違規停車於路口",
    "行駛中使用手機", "未依兩段式左轉", "逆向行駛於單行道",
    "未依線行駛", "違規迴車於路口", "未繫安全帶行駛",
    "違規變換車道", "未依號誌行駛",
]

ACCIDENT_TYPES = [
    "路口交岔撞", "同向擦撞", "對向撞", "追撞", "倒車撞",
    "側撞", "衝出路外", "行人事故", "自行車事故", "其他",
]


def api_get(url, params=None, timeout=API_TIMEOUT):
    for attempt in range(1, API_RETRY + 1):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"    [API 錯誤] 嘗試 {attempt}/{API_RETRY}: {url}")
            print(f"             {e}")
            if attempt == API_RETRY:
                return None
    return None


def get_dataset_metadata(dataset_id):
    for base in API_BASES:
        url = f"{base}/dataset/{dataset_id}"
        print(f"  嘗試介接資料集詮釋資料: {url}")
        data = api_get(url, timeout=30)
        if data:
            print(f"  成功取得資料集詮釋資料")
            result = data.get("result") or data
            resources = []
            raw_resources = result.get("resources") or result.get("resource") or []
            if isinstance(raw_resources, list):
                for r in raw_resources:
                    rid = r.get("id") or r.get("resource_id") or r.get("_id")
                    rname = r.get("name") or r.get("resource_name") or r.get("format", "")
                    if rid:
                        resources.append({"id": rid, "name": rname, "raw": r})
            if not resources and "id" in result:
                rid = result.get("id")
                if rid and rid != dataset_id:
                    resources.append({"id": rid, "name": result.get("name", ""), "raw": result})
            print(f"  找到 {len(resources)} 個 resource")
            for r in resources:
                print(f"    - {r['name']} (ID: {r['id']})")
            return resources
    print(f"  [錯誤] 無法取得資料集 {dataset_id} 的詮釋資料")
    return []


def fetch_datastore(resource_id, limit=100000):
    for base in API_BASES:
        url = f"{base}/datastore/{resource_id}"
        params = {"format": "json", "limit": limit}
        print(f"    嘗試 Datastore: {url} (limit={limit})")
        data = api_get(url, params=params, timeout=API_TIMEOUT)
        if data:
            result = data.get("result") or data
            records = result.get("records") or result.get("results") or []
            if records:
                print(f"    成功取得 {len(records)} 筆資料")
                return records
            if isinstance(data, list):
                print(f"    成功取得 {len(data)} 筆資料 (list 格式)")
                return data
            print(f"    回傳結構: {list(data.keys()) if isinstance(data, dict) else type(data)}")
    print(f"    [錯誤] 無法取得 resource {resource_id} 的資料")
    return []


def fetch_dataset_all_records(dataset_id, dataset_name=""):
    print(f"\n[{dataset_name}] Dataset ID: {dataset_id}")
    resources = get_dataset_metadata(dataset_id)
    all_records = []

    if resources:
        for r in resources:
            rid = r["id"]
            rname = r["name"]
            records = fetch_datastore(rid, limit=100000)
            if records:
                for rec in records:
                    rec["_source_resource"] = rname
                all_records.extend(records)
    else:
        print(f"  未找到 resources，嘗試直接用 dataset_id 存取 datastore")
        records = fetch_datastore(dataset_id, limit=100000)
        if records:
            all_records.extend(records)

    df = pd.DataFrame(all_records)
    print(f"  DataFrame: {df.shape[0]} 列 x {df.shape[1]} 欄")
    if not df.empty:
        print(f"  欄位: {list(df.columns)}")
    return df


def generate_sample_violation_data(n=5000):
    print(f"\n[Fallback] 產生範例違規資料 {n} 筆")
    areas = list(TAOYUAN_AREAS.keys())
    years = list(range(109, 115))
    data = []
    for _ in range(n):
        area = random.choice(areas)
        lat, lon = TAOYUAN_AREAS[area]
        lat += random.uniform(-0.05, 0.05)
        lon += random.uniform(-0.05, 0.05)
        data.append({
            "year": random.choice(years),
            "month": random.randint(1, 12),
            "time": f"{random.randint(0, 23):02d}:{random.randint(0, 59):02d}",
            "law": random.choice(VIOLATION_LAWS),
            "fact": random.choice(VIOLATION_FACTS),
            "CountyCode": "68",
            "AreaName": area,
            "AreaCode": "",
            "Road": random.choice(["中山路", "中正路", "復興路", "文化路", "明德路", "信義路"]),
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
        })
    return pd.DataFrame(data)


def generate_sample_accident_data(n=3000):
    print(f"\n[Fallback] 產生範例事故資料 {n} 筆")
    areas = list(TAOYUAN_AREAS.keys())
    years = list(range(108, 115))
    data = []
    for _ in range(n):
        area = random.choice(areas)
        year = random.choice(years)
        count = random.randint(1, 50)
        deaths = random.randint(0, min(3, count // 10))
        injuries = random.randint(0, count * 3)
        data.append({
            "發生年度": year,
            "事故類別名稱": random.choice(ACCIDENT_TYPES),
            "發生縣市名稱": "桃園市",
            "發生市區鄉鎮名稱": area,
            "當事者年齡": random.choice(["18-24", "25-39", "40-64", "65+"]),
            "當事者使用車種_類別": random.choice(["小客車", "機車", "腳踏車", "大貨車", "行人"]),
            "案件總數": count,
            "死亡": deaths,
            "受傷": injuries,
        })
    return pd.DataFrame(data)


def find_column(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def analyze_violations():
    print("\n" + "=" * 60)
    print("【交通違規裁罰資料】")
    print("=" * 60)

    df = fetch_dataset_all_records(VIOLATION_DATASET_ID, "交通違規舉發")
    is_sample = False
    if df.empty:
        print("  [警告] API 未取得資料，改用範例資料")
        df = generate_sample_violation_data(5000)
        is_sample = True

    year_col = find_column(df, ["year", "Year", "YEAR", "年度", "年"])
    law_col = find_column(df, ["law", "Law", "LAW", "違反法條", "法條"])
    fact_col = find_column(df, ["fact", "Fact", "FACT", "違規事", "事實", "違規事實內容"])
    area_col = find_column(df, ["AreaName", "areaName", "area", "AREA", "行政區", "行政區名稱", "區"])
    lat_col = find_column(df, ["latitude", "Latitude", "LATITUDE", "lat", "Lat", "緯度"])
    lon_col = find_column(df, ["longitude", "Longitude", "LONGITUDE", "lon", "Lng", "經度"])
    road_col = find_column(df, ["Road", "road", "ROAD", "路段", "路名", "路段路名"])

    print(f"  欄位對應: year={year_col}, law={law_col}, fact={fact_col}, area={area_col}, lat={lat_col}, lon={lon_col}")

    year_counts = df[year_col].value_counts().sort_index() if year_col else pd.Series(dtype=int)
    law_counts = df[law_col].value_counts().head(20) if law_col else pd.Series(dtype=int)
    fact_counts = df[fact_col].value_counts().head(20) if fact_col else pd.Series(dtype=int)
    area_counts = df[area_col].value_counts() if area_col else pd.Series(dtype=int)

    return {
        "df": df, "year_col": year_col, "law_col": law_col, "fact_col": fact_col,
        "area_col": area_col, "lat_col": lat_col, "lon_col": lon_col, "road_col": road_col,
        "year_counts": year_counts, "law_counts": law_counts,
        "fact_counts": fact_counts, "area_counts": area_counts,
        "is_sample": is_sample,
    }


def create_violation_charts(a):
    if a is None:
        return []
    figs = []
    df = a["df"]
    sample_note = " (範例資料)" if a.get("is_sample") else ""

    def save_bar(d, title, xlabel, ylabel, filename, color_scale):
        try:
            if d is None or len(d) == 0:
                return False
            fig = px.bar(x=d.index.astype(str), y=d.values,
                         labels={"x": xlabel, "y": ylabel}, title=f"{title}{sample_note}",
                         color=d.values, color_continuous_scale=color_scale)
            fig.update_layout(template="plotly_white")
            fig.write_html(f"docs/{filename}", include_plotlyjs="cdn")
            figs.append(filename)
            print(f"    已生成: {filename}")
            return True
        except Exception as e:
            print(f"    [警告] 圖表生成失敗 {filename}: {e}")
            return False

    def save_hbar(d, title, ylabel, xlabel, filename, color_scale, top=15):
        try:
            if d is None or len(d) == 0:
                return False
            d_top = d.head(top)
            fig = px.bar(y=d_top.index[::-1], x=d_top.values[::-1],
                         orientation="h", labels={"y": ylabel, "x": xlabel},
                         title=f"{title}{sample_note}",
                         color=d_top.values[::-1], color_continuous_scale=color_scale)
            fig.update_layout(template="plotly_white", height=600)
            fig.write_html(f"docs/{filename}", include_plotlyjs="cdn")
            figs.append(filename)
            print(f"    已生成: {filename}")
            return True
        except Exception as e:
            print(f"    [警告] 圖表生成失敗 {filename}: {e}")
            return False

    save_bar(a["year_counts"], "各年度交通違規裁罰件數統計", "年度", "裁罰件數",
             "violation_yearly_trend.html", "Reds")
    save_hbar(a["law_counts"], "主要違反法條 TOP 15", "違反法條", "件數",
              "violation_top_laws.html", "Oranges")
    save_hbar(a["fact_counts"], "主要違規事實 TOP 15", "違規事實", "件數",
              "violation_top_facts.html", "Blues")
    save_bar(a["area_counts"], "各行政區交通違規裁罰分布", "行政區", "裁罰件數",
             "violation_area_distribution.html", "Purples")

    try:
        year_col = a["year_col"]
        area_col = a["area_col"]
        if year_col and year_col in df.columns and area_col and area_col in df.columns:
            pivot = df.groupby([year_col, area_col]).size().unstack(fill_value=0)
            if pivot.shape[0] > 0 and pivot.shape[1] > 0:
                fig = px.imshow(pivot, labels=dict(x="行政區", y="年度", color="件數"),
                               title=f"各年度行政區違規裁罰熱力圖{sample_note}",
                               aspect="auto", color_continuous_scale="YlOrRd")
                fig.update_layout(template="plotly_white", height=500)
                fig.write_html("docs/violation_heatmap.html", include_plotlyjs="cdn")
                figs.append("violation_heatmap.html")
                print(f"    已生成: violation_heatmap.html")
    except Exception as e:
        print(f"    [警告] 熱力圖生成失敗: {e}")

    print(f"  違規圖表共 {len(figs)} 個")
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
    sample_note = " (範例資料)" if a.get("is_sample") else ""

    if not lat_col or lat_col not in df.columns or not lon_col or lon_col not in df.columns:
        print("  [資訊] 少經緯度資料，略過違規地圖")
        return None

    try:
        df_map = df.copy()
        df_map[lat_col] = pd.to_numeric(df_map[lat_col], errors="coerce")
        df_map[lon_col] = pd.to_numeric(df_map[lon_col], errors="coerce")
        df_map = df_map.dropna(subset=[lat_col, lon_col])
        if len(df_map) == 0:
            print("  [資訊] 無有效座標資料")
            return None

        center_lat = df_map[lat_col].median()
        center_lon = df_map[lon_col].median()
        m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles="CartoDB positron")

        if year_col and year_col in df_map.columns:
            years = sorted(df_map[year_col].dropna().unique())
            for year in years:
                year_df = df_map[df_map[year_col] == year]
                if len(year_df) == 0:
                    continue
                fg = folium.FeatureGroup(name=f"{year}年違規裁罰點位{sample_note}")
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
        print(f"  已生成違規裁罰分布地圖{sample_note}")
        return "violation_map.html"
    except Exception as e:
        print(f"  [警告] 違規地圖生成失敗: {e}")
        traceback.print_exc()
        return None


def analyze_accidents():
    print("\n" + "=" * 60)
    print("【交通事故資】")
    print("=" * 60)

    df = pd.DataFrame()
    used_dataset_id = None
    for ds_id in ACCIDENT_DATASET_IDS:
        df = fetch_dataset_all_records(ds_id, "交通事故")
        if not df.empty:
            used_dataset_id = ds_id
            break

    is_sample = False
    if df.empty:
        print("  [警告] 所有事故資料集 API 均未取得資料，改用範例資料")
        df = generate_sample_accident_data(3000)
        is_sample = True

    print(f"  使資料集: {used_dataset_id or '範例資料'}")

    year_col = find_column(df, ["year", "Year", "YEAR", "年度", "年", "發生年度"])
    type_col = find_column(df, ["type", "Type", "TYPE", "事故類別", "事故類別名稱", "類別"])
    area_col = find_column(df, ["area", "Area", "AREA", "發生市區鄉鎮名稱", "行政區", "區"])
    place_col = find_column(df, ["place", "Place", "場所", "事故位置", "位置"])
    vehicle_col = find_column(df, ["vehicle", "Vehicle", "車種", "當事者使用車種_大類別", "運具"])
    count_col = find_column(df, ["count", "Count", "案件總數", "總數", "件數"])
    death_col = find_column(df, ["death", "Death", "死亡", "死亡人數"])
    injury_col = find_column(df, ["injury", "Injury", "受傷", "受傷人數"])

    print(f"  欄位對應: year={year_col}, type={type_col}, area={area_col}, count={count_col}, death={death_col}, injury={injury_col}")

    for col in [count_col, death_col, injury_col]:
        if col and col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

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
        "is_sample": is_sample,
    }


def create_accident_charts(a):
    if a is None:
        return []
    figs = []
    sample_note = " (範例資料)" if a.get("is_sample") else ""

    def save_bar(d, title, xlabel, ylabel, filename, color_scale):
        try:
            if d is None or len(d) == 0:
                return False
            fig = px.bar(x=d.index.astype(str), y=d.values,
                         labels={"x": xlabel, "y": ylabel}, title=f"{title}{sample_note}",
                         color=d.values, color_continuous_scale=color_scale)
            fig.update_layout(template="plotly_white")
            fig.write_html(f"docs/{filename}", include_plotlyjs="cdn")
            figs.append(filename)
            print(f"    已生成: {filename}")
            return True
        except Exception as e:
            print(f"    [警告] 圖表生成失敗 {filename}: {e}")
            return False

    def save_hbar(d, title, ylabel, xlabel, filename, color_scale, top=15):
        try:
            if d is None or len(d) == 0:
                return False
            d_top = d.head(top)
            fig = px.bar(y=d_top.index[::-1], x=d_top.values[::-1],
                         orientation="h", labels={"y": ylabel, "x": xlabel},
                         title=f"{title}{sample_note}",
                         color=d_top.values[::-1], color_continuous_scale=color_scale)
            fig.update_layout(template="plotly_white")
            fig.write_html(f"docs/{filename}", include_plotlyjs="cdn")
            figs.append(filename)
            print(f"    已生成: {filename}")
            return True
        except Exception as e:
            print(f"    [警告] 圖表生成失敗 {filename}: {e}")
            return False

    save_bar(a["year_stats"], "各年度交通事故件數統計", "年度", "事故件數",
             "accident_yearly_trend.html", "Reds")

    try:
        d = a["type_stats"]
        if d is not None and len(d) > 0:
            fig = px.pie(names=d.index, values=d.values,
                         title=f"主要事故類別分布{sample_note}", hole=0.4)
            fig.update_traces(textposition="inside", textinfo="percent+label")
            fig.update_layout(template="plotly_white")
            fig.write_html("docs/accident_type_distribution.html", include_plotlyjs="cdn")
            figs.append("accident_type_distribution.html")
            print(f"    已生成: accident_type_distribution.html")
    except Exception as e:
        print(f"    [警告] 事故類別圖生成失敗: {e}")

    save_bar(a["area_stats"], "各行政區交通事故分布", "地區", "事故件數",
             "accident_area_distribution.html", "Oranges")
    save_hbar(a["place_stats"], "事故場所類別分布 TOP 15", "場所類別", "事故件數",
              "accident_place_distribution.html", "Blues")
    save_hbar(a["vehicle_stats"], "事故運具類別分布 TOP 15", "運具類別", "事故件數",
              "accident_vehicle_distribution.html", "Greens")

    try:
        dis = a.get("death_injury_stats")
        if dis is not None and len(dis) > 0:
            fig = go.Figure()
            for col in dis.columns:
                fig.add_trace(go.Scatter(
                    x=dis.index.astype(str), y=dis[col].values,
                    mode="lines+markers", name=col,
                ))
            fig.update_layout(
                title=f"各年度交通事故傷亡趨勢{sample_note}",
                xaxis_title="年度", yaxis_title="人數/件數", template="plotly_white",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            fig.write_html("docs/accident_casualty_trend.html", include_plotlyjs="cdn")
            figs.append("accident_casualty_trend.html")
            print(f"    已生成: accident_casualty_trend.html")
    except Exception as e:
        print(f"    [警告] 傷亡趨勢圖生失敗: {e}")

    print(f"  事故圖表共 {len(figs)} 個")
    return figs


def match_area_coords(area_name):
    area_key = str(area_name).replace("桃園市", "").replace("桃園", "")
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
    sample_note = " (範例資料)" if a.get("is_sample") else ""

    if not area_col or area_col not in df.columns:
        print("  [資訊] 缺少行政區資料，略過事故地圖")
        return None

    try:
        m = folium.Map(location=[24.95, 121.25], zoom_start=10, tiles="CartoDB positron")

        if year_col and year_col in df.columns:
            years = sorted(df[year_col].dropna().unique())
            for year in years:
                year_df = df[df[year_col] == year]
                if len(year_df) == 0:
                    continue
                fg = folium.FeatureGroup(name=f"{year}年事故熱點{sample_note}")
                if area_col in year_df.columns:
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
        print(f"  已生成交通事故熱點地圖{sample_note}")
        return "accident_map.html"
    except Exception as e:
        print(f"  [警告] 事故地圖生成失敗: {e}")
        traceback.print_exc()
        return None


def generate_index(violation_figs, accident_figs, violation_map, accident_map,
                   violation_sample=False, accident_sample=False):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sample_banner = ""
    if violation_sample or accident_sample:
        sample_banner = '<div style="background:#fff3cd;border:1px solid #ffeaa7;border-radius:8px;padding:1rem;margin:1rem 0;text-align:center;color:#856404;"><strong>注意：</strong>目前顯示的資料為範例資料。API 介接可能因網路或資料集異動而失敗，請檢查 GitHub Actions 日誌確認 API 狀態。</div>'

    def make_section(title, anchor, figs, map_file, section_type):
        if not figs and not map_file:
            return f'<h2 id="{anchor}" class="section-title">{title}</h2><div class="chart-card"><p style="padding:2rem;color:#888;text-align:center;">暫無資料</p></div>'
        html = f'<h2 id="{anchor}" class="section-title">{title}</h2>'
        if figs:
            html += '<div class="chart-grid">'
            for fig in figs:
                name = fig.replace(".html", "").replace(f"{section_type}_", "").replace("_", " ").title()
                html += f'<div class="chart-card"><h3>{name}</h3><iframe src="{fig}" width="100%" height="450"></iframe></div>'
            html += '</div>'
        if map_file:
            map_title = "違規裁罰點位分布地圖" if section_type == "violation" else "交通事故熱點分布地圖"
            html += f'<div class="map-card"><h3>{map_title}</h3><iframe src="{map_file}" width="100%" height="600"></iframe></div>'
        return html

    v_section = make_section("交通違規裁罰分析", "violations", violation_figs, violation_map, "violation")
    a_section = make_section("交通事故分析", "accidents", accident_figs, accident_map, "accident")

    html = '<!DOCTYPE html>\n<html lang="zh-TW">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>桃園市交通裁罰及傷亡資訊報告</title>\n<style>\n:root { --primary: #1a5276; --secondary: #2874a6; --accent: #e74c3c; --bg: #f8f9fa; --card-bg: #ffffff; --text: #2c3e50; --border: #dee2e6; }\n* { margin: 0; padding: 0; box-sizing: border-box; }\nbody { font-family: "Segoe UI", "Microsoft JhengHei", sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }\nheader { background: linear-gradient(135deg, var(--primary), var(--secondary)); color: white; padding: 2rem 1rem; text-align: center; position: relative; }\nheader h1 { font-size: 1.8rem; margin-bottom: 0.5rem; }\nheader p { opacity: 0.9; font-size: 0.95rem; }\nnav { background: #1a5276; padding: 0.5rem 1rem; text-align: center; position: sticky; top: 0; z-index: 100; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }\nnav a { color: white; text-decoration: none; margin: 0 1rem; font-size: 0.95rem; padding: 0.3rem 0.8rem; border-radius: 4px; transition: background 0.2s; display: inline-block; }\nnav a:hover { background: rgba(255,255,255,0.2); }\n.update-time { text-align: center; padding: 0.5rem; background: #e8f4f8; font-size: 0.85rem; color: #555; }\nmain { max-width: 1400px; margin: 0 auto; padding: 1.5rem; }\n.section-title { font-size: 1.4rem; color: var(--primary); margin: 2rem 0 1rem; padding-bottom: 0.5rem; border-bottom: 3px solid var(--secondary); }\n.chart-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 1.5rem; margin-bottom: 1.5rem; }\n.chart-card, .map-card { background: var(--card-bg); border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); padding: 1rem; transition: transform 0.2s; }\n.chart-card:hover, .map-card:hover { transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,0.12); }\n.chart-card h3, .map-card h3 { font-size: 1rem; color: var(--primary); margin-bottom: 0.75rem; padding-left: 0.5rem; border-left: 4px solid var(--accent); }\n.map-card { margin-bottom: 1.5rem; }\niframe { border-radius: 8px; width: 100%; border: none; }\nfooter { text-align: center; padding: 1.5rem; color: #888; font-size: 0.8rem; border-top: 1px solid var(--border); }\nfooter a { color: var(--secondary); text-decoration: none; }\n@media (max-width: 600px) { .chart-grid { grid-template-columns: 1fr; } header h1 { font-size: 1.3rem; } nav a { margin: 0 0.3rem; font-size: 0.85rem; } }\n</style>\n</head>\n<body>\n<header>\n<h1>桃園市交通裁罰及傷亡資訊報告</h1>\n<p>資料來源：桃園資料開放平台 | 透過 GitHub Actions 自動更新</p>\n</header>\n<nav>\n<a href="#violations">交通違規裁罰</a>\n<a href="#accidents">交通事故分析</a>\n</nav>\n<div class="update-time">報告生成時間：' + now + '</div>' + sample_banner + '\n<main>\n' + v_section + '\n' + a_section + '\n</main>\n<footer>\n<p>資料來源：<a href="https://opendata.tycg.gov.tw" target="_blank">桃園資料開放平台</a></p>\n<p>本報告由 GitHub Actions 自動生成，僅供參考</p>\n</footer>\n</body>\n</html>'

    os.makedirs("docs", exist_ok=True)
    index_path = "docs/index.html"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)

    if os.path.exists(index_path):
        size = os.path.getsize(index_path)
        print(f"\n[完成] 已生成整合主報告頁面: {index_path} ({size} bytes)")
    else:
        print(f"\n[錯誤] 檔案寫入失敗！")
    return index_path


def main():
    print("=" * 60)
    print("桃園市交通裁罰及傷亡資訊報告生成器 v2.1")
    print("模式: API 直接介接 + 範例資料 fallback")
    print("=" * 60)

    vf, vm, af, am = [], None, [], None
    v_sample, a_sample = False, False

    try:
        va = analyze_violations()
        if va:
            vf = create_violation_charts(va)
            vm = create_violation_map(va)
            v_sample = va.get("is_sample", False)
    except Exception as e:
        print(f"\n[錯誤] 違規分析階段失敗: {e}")
        traceback.print_exc()

    try:
        aa = analyze_accidents()
        if aa:
            af = create_accident_charts(aa)
            am = create_accident_map(aa)
            a_sample = aa.get("is_sample", False)
    except Exception as e:
        print(f"\n[錯誤] 事故分析階段失敗: {e}")
        traceback.print_exc()

    print("\n" + "-" * 60)
    print("生成整合主報告頁面...")
    print("-" * 60)
    try:
        generate_index(vf, af, vm, am, v_sample, a_sample)
    except Exception as e:
        print(f"[錯誤] 生成主報告頁面失敗: {e}")
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("報告生成流程結束")
    print("輸出目錄: docs/")
    print("主頁面: docs/index.html")
    print("=" * 60)

    return 0 if (vf or af) else 1


if __name__ == "__main__":
    sys.exit(main())
