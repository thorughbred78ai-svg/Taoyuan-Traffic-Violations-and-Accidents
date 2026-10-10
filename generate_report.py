#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
桃園市交通裁罰及傷亡資訊報告生成器 v5.3
- KPI、圖表、地圖、分析摘要、決策建議全部支援年度切換
- 修復事故資料顯示問題
- 免費 GIS 底圖（無需 API Key）
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
    "桃園區": [24.989, 121.313], "中壢區": [24.965, 121.221],
    "平鎮區": [24.947, 121.206], "八德區": [24.930, 121.290],
    "楊梅區": [24.907, 121.146], "蘆竹區": [25.045, 121.290],
    "大溪區": [24.883, 121.288], "龍潭區": [24.864, 121.211],
    "龜山區": [25.022, 121.400], "大園區": [25.066, 121.197],
    "觀音區": [25.036, 121.133], "新屋區": [24.974, 121.106],
    "復興區": [24.817, 121.375],
}

VIOLATION_LAWS_TC = [
    "超速行駛", "闖紅燈", "違規停車", "未繫安全帶", "使用手持電話",
    "逆向行駛", "違規變換車道", "未禮讓行人", "未依標線行駛", "違規迴車",
    "未保持安全距離", "未依號誌行駛", "違規左轉", "違規右轉", "未依車道行駛",
    "燈光使用不當", "牌照問題", "酒後駕車", "超重載貨", "未依規定讓車",
    "行人優先區違規", "公車專用道違規", "機車行駛禁行區", "未戴安全帽",
    "拼裝車輛上路", "車輛機件不合", "未依規定裝載", "危險駕駛", "逼車",
    "蛇行", "惡意阻擋", "未依規定轉彎", "未依兩段式左轉", "行駛路肩",
    "違規超車", "未依順行方向停車", "占用身障車位", "占用消防通道",
    "紅線停車", "黃線臨停違規", "公車招呼站違停", "交叉路口違停",
    "人行道違停", "騎樓違停", "併排停車", "逆向停車", "未依規定使用方向燈",
    "夜間未開燈", "霧燈使用不當", "遠燈使用不當", "煞車燈故障",
]

VIOLATION_FACTS_TC = [
    "行駛中超速", "紅燈右轉", "路口違規停車", "行駛中未繫安全帶",
    "行駛中使用手機", "單行道逆向行駛", "變換車道未打方向燈",
    "行人穿越道未禮讓", "壓線行駛", "路口違規迴車",
    "未保持行車安全距離", "紅燈越線", "禁止左轉時段違規左轉",
    "禁止右轉時段違規右轉", "公車專用道違規行駛",
    "夜間未開大燈行駛", "遠光燈使用不當", "煞車燈不亮",
    "車牌汙損不清", "臨時停車逾時", "併排停車",
    "人行道停車", "騎樓停車", "交叉路口停車",
    "公車站停車", "消防栓前停車", "身障車位占用",
    "黃線停車", "紅線停車", "逆向停車",
    "未緊靠路緣停車", "停車未距路口五公尺", "停車未距消防栓三公尺",
    "停車未距人行道一公尺", "停車未距彎道十公尺", "停車未距坡道十公尺",
    "停車未距橋樑十公尺", "停車未距隧道十公尺", "停車未距鐵路十公尺",
    "停車未距平交道十公尺", "停車未距公車站十公尺", "停車未距學校三十公尺",
    "停車未距醫院三十公尺", "停車未距市場三十公尺", "停車未距教堂三十公尺",
    "停車未距殯儀館三十公尺", "停車未距加油站十公尺", "停車未距加氣站十公尺",
    "停車未距化學工廠三十公尺", "停車未距高壓電設施十公尺",
]

ACCIDENT_TYPES_TC = [
    "路口交岔撞", "同向擦撞", "對向撞", "追撞", "倒車撞",
    "側撞", "衝出路外", "行人事故", "自行車事故", "其他",
    "路口側撞", "路口追撞", "路口擦撞", "快車道事故", "慢車道事故",
    "機慢車事故", "汽機車事故", "大客車事故", "大貨車事故", "聯結車事故",
    "計程車事故", "公車事故", "校車事故", "救護車事故", "消防車事故",
    "警車事故", "工程車事故", "垃圾車事故", "灑水車事故", "吊車事故",
    "拖吊車事故", "砂石車事故", "油罐車事故", "化學車事故", "冷凍車事故",
    "貨櫃車事故", "遊覽車事故", "客運事故", "酒駕事故", "毒駕事故",
    "疲勞駕駛事故", "分心駕駛事故", "超速事故", "闖紅燈事故", "違規左轉事故",
    "違規右轉事故", "違規迴車事故", "違規變換車道事故", "違規超車事故", "違規停車事故",
]

VEHICLE_TYPES_TC = [
    "小客車", "機車", "腳踏車", "大貨車", "行人",
    "大客車", "聯結車", "計程車", "公車", "校車",
    "救護車", "消防車", "警車", "工程車", "垃圾車",
    "灑水車", "吊車", "拖吊車", "砂石車", "油罐車",
    "化學車", "冷凍車", "貨車", "遊覽車", "客運",
    "火車", "捷運", "輕軌", "高鐵", "電動車",
]

ROADS_TC = [
    "中山路", "中正路", "復興路", "文化路", "明德路",
    "信義路", "和平路", "博愛路", "成功路", "建國路",
    "中華路", "民族路", "民權路", "民生路", "忠孝路",
    "仁愛路", "大同路", "光復路", "自強路", "新生路",
]

AGE_GROUPS_TC = ["18-24歲", "25-39歲", "40-64歲", "65歲以上"]


def api_get(url, params=None, timeout=API_TIMEOUT):
    for attempt in range(1, API_RETRY + 1):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"      API 錯誤 (嘗試 {attempt}/{API_RETRY}): {e}")
            if attempt == API_RETRY:
                return None
    return None


def fetch_datastore_direct(resource_id, limit=100000):
    url = f"{API_BASE}/datastore/{resource_id}"
    params = {"format": "json", "limit": limit}
    print(f"    介接: {url}")
    data = api_get(url, params=params, timeout=API_TIMEOUT)
    if not data:
        return []
    result = data.get("result", {})
    records = result.get("records") or result.get("results") or []
    return records


def fetch_dataset(dataset_id, name=""):
    print(f"\n[{name}] Dataset ID: {dataset_id}")
    meta_url = f"{API_BASE}/dataset/{dataset_id}"
    print(f"  取得詮釋資料: {meta_url}")
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
        print(f"  找到 {len(resource_ids)} 個 resource")
    else:
        print(f"  [警告] 無法取得詮釋資料，嘗試直接存取")
        resource_ids = [(dataset_id, "direct")]

    for rid, rname in resource_ids:
        print(f"    介接 resource: {rname or rid}")
        records = fetch_datastore_direct(rid, limit=100000)
        if records:
            print(f"    成功: {len(records)} 筆")
            for rec in records:
                rec["_source"] = rname
            all_records.extend(records)
        else:
            print(f"    失敗或無資料")

    df = pd.DataFrame(all_records)
    print(f"  合計: {df.shape[0]} 列 x {df.shape[1]} 欄")
    if not df.empty:
        print(f"  欄位: {list(df.columns)}")
    return df


def find_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def add_free_basemaps(m):
    folium.TileLayer(
        tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        name="OpenStreetMap",
        overlay=False, control=True,
    ).add_to(m)
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        name="CartoDB Positron",
        overlay=False, control=True,
    ).add_to(m)
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        name="CartoDB Dark",
        overlay=False, control=True,
    ).add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles &copy; Esri",
        name="Esri 衛星影像",
        overlay=False, control=True,
    ).add_to(m)
    return m


def sample_violations(n=5000):
    print(f"\n[Fallback] 產生範例違規資料 {n} 筆")
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
            "law": random.choice(VIOLATION_LAWS_TC),
            "fact": random.choice(VIOLATION_FACTS_TC),
            "CountyCode": "68",
            "AreaName": area,
            "AreaCode": "",
            "Road": random.choice(ROADS_TC),
            "latitude": round(lat + random.uniform(-0.05, 0.05), 6),
            "longitude": round(lon + random.uniform(-0.05, 0.05), 6),
        })
    return pd.DataFrame(data)


def sample_accidents(n=3000):
    print(f"\n[Fallback] 產生範例事故資料 {n} 筆")
    areas = list(TAOYUAN_AREAS.keys())
    years = list(range(108, 115))
    data = []
    for _ in range(n):
        area = random.choice(areas)
        count = random.randint(1, 50)
        data.append({
            "year": random.choice(years),
            "accident_type": random.choice(ACCIDENT_TYPES_TC),
            "city": "桃園市",
            "district": area,
            "age_group": random.choice(AGE_GROUPS_TC),
            "vehicle_type": random.choice(VEHICLE_TYPES_TC),
            "case_count": count,
            "deaths": random.randint(0, min(3, count//10)),
            "injuries": random.randint(0, count*3),
        })
    return pd.DataFrame(data)


def compute_yoy_change(series):
    if series is None or len(series) < 2:
        return None, None
    values = series.values
    latest = values[-1]
    prev = values[-2]
    if prev == 0:
        return None, latest
    change = (latest - prev) / prev * 100
    return change, latest


def compute_violation_kpi(df, yc, ac, lc, year_filter=None):
    """計算違規 KPI（全年度或單一年度）"""
    if year_filter is not None and yc and yc in df.columns:
        df = df[df[yc] == year_filter]

    total_cases = len(df)
    top_district = "N/A"
    top_violation = "N/A"

    if ac and ac in df.columns and len(df) > 0:
        area_counts = df[ac].value_counts()
        if len(area_counts) > 0:
            top_district = str(area_counts.index[0])

    if lc and lc in df.columns and len(df) > 0:
        law_counts = df[lc].value_counts()
        if len(law_counts) > 0:
            top_violation = str(law_counts.index[0])

    return {
        "total_cases": total_cases,
        "top_district": top_district,
        "top_violation": top_violation,
    }


def compute_accident_kpi(df, yc, ac, tc, cc, dc, ic, year_filter=None):
    """計算事故 KPI（全年度或單一年度）"""
    if year_filter is not None and yc and yc in df.columns:
        df = df[df[yc] == year_filter]

    total_cases = df[cc].sum() if cc and cc in df.columns else len(df)
    total_deaths = df[dc].sum() if dc and dc in df.columns else 0
    total_injuries = df[ic].sum() if ic and ic in df.columns else 0
    top_district = "N/A"
    top_type = "N/A"

    if ac and ac in df.columns and cc and cc in df.columns and len(df) > 0:
        area_stats = df.groupby(ac)[cc].sum().sort_values(ascending=False)
        if len(area_stats) > 0:
            top_district = str(area_stats.index[0])

    if tc and tc in df.columns and cc and cc in df.columns and len(df) > 0:
        type_stats = df.groupby(tc)[cc].sum().sort_values(ascending=False)
        if len(type_stats) > 0:
            top_type = str(type_stats.index[0])

    return {
        "total_cases": int(total_cases),
        "total_deaths": int(total_deaths),
        "total_injuries": int(total_injuries),
        "top_district": top_district,
        "top_type": top_type,
    }


def generate_violation_insights(df, yc, ac, lc, year_filter=None):
    """生成違規分析摘要（全年度或單一年度）"""
    insights = []
    if year_filter is not None and yc and yc in df.columns:
        df_filtered = df[df[yc] == year_filter]
        year_label = f"{year_filter}年"
    else:
        df_filtered = df
        year_label = "統計期間"

    if len(df_filtered) == 0:
        return insights

    total = len(df_filtered)
    insights.append(f"{year_label}共計 {total:,} 件違規裁罰案件。")

    if ac and ac in df_filtered.columns:
        area_counts = df_filtered[ac].value_counts()
        if len(area_counts) > 0:
            top_district = area_counts.index[0]
            top_count = area_counts.iloc[0]
            pct = top_count / area_counts.sum() * 100
            insights.append(f"{top_district} 為違規裁罰最高發行政區，佔總數 {pct:.1f}%（{top_count:,} 件），建議優先部署執法資源。")

    if lc and lc in df_filtered.columns:
        law_counts = df_filtered[lc].value_counts()
        if len(law_counts) > 0:
            top_law = law_counts.index[0]
            top_count = law_counts.iloc[0]
            pct = top_count / law_counts.sum() * 100
            insights.append(f"{top_law} 為最常見違規類型，佔總數 {pct:.1f}%（{top_count:,} 件），應加強相關法規宣導。")

    return insights


def generate_accident_insights(df, yc, ac, tc, cc, dc, ic, year_filter=None):
    """生成事故分析摘要（全年度或單一年度）"""
    insights = []
    if year_filter is not None and yc and yc in df.columns:
        df_filtered = df[df[yc] == year_filter]
        year_label = f"{year_filter}年"
    else:
        df_filtered = df
        year_label = "統計期間"

    if len(df_filtered) == 0:
        return insights

    total = df_filtered[cc].sum() if cc and cc in df_filtered.columns else len(df_filtered)
    insights.append(f"{year_label}共計 {int(total):,} 件交通事故。")

    if dc and dc in df_filtered.columns:
        total_deaths = df_filtered[dc].sum()
        if total_deaths > 0:
            insights.append(f"{year_label}累計死亡 {int(total_deaths)} 人，平均每件事故死亡風險約 {total_deaths/total:.3f} 人。")

    if ic and ic in df_filtered.columns:
        total_injuries = df_filtered[ic].sum()
        if total_injuries > 0:
            insights.append(f"{year_label}累計受傷 {int(total_injuries)} 人，平均每件事故受傷約 {total_injuries/total:.1f} 人。")

    if ac and ac in df_filtered.columns and cc and cc in df_filtered.columns:
        area_stats = df_filtered.groupby(ac)[cc].sum().sort_values(ascending=False)
        if len(area_stats) > 0:
            top_district = area_stats.index[0]
            top_count = area_stats.iloc[0]
            pct = top_count / area_stats.sum() * 100
            insights.append(f"{top_district} 為事故最高發行政區，佔總數 {pct:.1f}%（{int(top_count)} 件），建議優先改善路口設計與號誌配置。")

    if tc and tc in df_filtered.columns and cc and cc in df_filtered.columns:
        type_stats = df_filtered.groupby(tc)[cc].sum().sort_values(ascending=False)
        if len(type_stats) > 0:
            top_type = type_stats.index[0]
            top_count = type_stats.iloc[0]
            pct = top_count / type_stats.sum() * 100
            insights.append(f"{top_type} 為最主要事故類型，佔總數 {pct:.1f}%（{int(top_count)} 件），應針對此類事故加強預防措施。")

    return insights


def generate_violation_recommendations(df, ac, lc, year_filter=None):
    """生成違規決策建議（全年度或單一年度）"""
    recs = []
    if year_filter is not None:
        year_label = f"{year_filter}年"
    else:
        year_label = "統計期間"

    if len(df) == 0:
        recs.append("建議持續監測各行政區違規趨勢，並定期評估執法策略成效。")
        return recs

    if ac and ac in df.columns:
        area_counts = df[ac].value_counts()
        if len(area_counts) > 0:
            top3 = "、".join([str(x) for x in area_counts.head(3).index])
            recs.append(f"優先於 {top3} 等高風險行政區設置違規舉發專案，結合社區宣導提升守法意識。")

    if lc and lc in df.columns:
        law_counts = df[lc].value_counts()
        if len(law_counts) > 0:
            top_law = law_counts.index[0]
            recs.append(f"針對 {top_law} 等高頻違規類型，建議加強駕駛人教育訓練與媒體宣導，並檢視相關法規罰則嚇阻效果。")

    if len(recs) == 0:
        recs.append("建議持續監測各行政區違規趨勢，並定期評估執法策略成效。")

    return recs


def generate_accident_recommendations(df, yc, ac, tc, cc, dc, year_filter=None):
    """生成事故決策建議（全年度或單一年度）"""
    recs = []
    if year_filter is not None:
        year_label = f"{year_filter}年"
    else:
        year_label = "統計期間"

    if len(df) == 0:
        recs.append("建議持續追蹤事故類型分布與行政區風險變化，並建立預警機制。")
        return recs

    if dc and dc in df.columns:
        total_deaths = df[dc].sum()
        if total_deaths > 5:
            recs.append(f"{year_label}死亡事故累計達 {int(total_deaths)} 人，建議優先檢視行人保護設施、路口視距及速限管理措施。")

    if ac and ac in df.columns and cc and cc in df.columns:
        area_stats = df.groupby(ac)[cc].sum().sort_values(ascending=False)
        if len(area_stats) > 0:
            top3 = "、".join([str(x) for x in area_stats.head(3).index])
            recs.append(f"針對 {top3} 等高事故行政區，建議進行道路安全稽核並優先改善事故熱點。")

    if tc and tc in df.columns and cc and cc in df.columns:
        type_stats = df.groupby(tc)[cc].sum().sort_values(ascending=False)
        if len(type_stats) > 0:
            top_type = type_stats.index[0]
            recs.append(f"{top_type} 為主要事故類型，建議分析其成因並設計針對性改善方案（如路口幾何調整、號誌時制優化）。")

    if len(recs) == 0:
        recs.append("建議持續追蹤事故類型分布與行政區風險變化，並建立預警機制。")

    return recs


def analyze_violations():
    print("\n" + "=" * 60)
    print("【交通違規裁罰資料】")
    print("=" * 60)

    df = fetch_dataset(VIOLATION_DATASET_ID, "交通違規舉發")
    is_sample = False
    if df.empty:
        print("  [警告] API 未取得資料，改用範例資料")
        df = sample_violations(5000)
        is_sample = True

    yc = find_col(df, ["year","Year","YEAR","年度","年"])
    lc = find_col(df, ["law","Law","LAW","違反法條","法條"])
    fc = find_col(df, ["fact","Fact","FACT","違規事實","事實"])
    ac = find_col(df, ["AreaName","areaName","area","AREA","行政區","行政區名稱","區"])
    lac = find_col(df, ["latitude","Latitude","LATITUDE","lat","Lat","緯度"])
    loc = find_col(df, ["longitude","Longitude","LONGITUDE","lon","Lng","經度"])
    rc = find_col(df, ["Road","road","ROAD","路段","路名"])

    print(f"  欄位對應: year={yc}, law={lc}, fact={fc}, area={ac}, lat={lac}, lon={loc}")

    years = []
    if yc and yc in df.columns:
        years = sorted(df[yc].dropna().unique())
        years = [int(y) if str(y).isdigit() else y for y in years]
        years = sorted(years)
    print(f"  資料年度: {years}")

    year_counts = df[yc].value_counts().sort_index() if yc else pd.Series(dtype=int)
    law_counts = df[lc].value_counts().head(20) if lc else pd.Series(dtype=int)
    fact_counts = df[fc].value_counts().head(20) if fc else pd.Series(dtype=int)
    area_counts = df[ac].value_counts() if ac else pd.Series(dtype=int)

    # 全年度 KPI
    kpi_all = compute_violation_kpi(df, yc, ac, lc, year_filter=None)
    change, latest = compute_yoy_change(year_counts)
    kpi_all["yoy_change"] = change
    kpi_all["avg_cases"] = year_counts.mean() if year_counts is not None else 0

    # 各年度 KPI
    kpi_year = {}
    if yc and years:
        for year in years:
            ky = compute_violation_kpi(df, yc, ac, lc, year_filter=year)
            # 單一年度的 YoY 與年均無意義，設為 N/A
            ky["yoy_change"] = None
            ky["avg_cases"] = year_counts.get(year, 0) if year_counts is not None else 0
            kpi_year[str(year)] = ky

    # 全年度分析摘要與建議
    all_insights = generate_violation_insights(df, yc, ac, lc, year_filter=None)
    all_recommendations = generate_violation_recommendations(df, ac, lc, year_filter=None)

    # 各年度分析摘要與建議
    year_insights = {}
    year_recommendations = {}
    if yc and years:
        for year in years:
            year_insights[str(year)] = generate_violation_insights(df, yc, ac, lc, year_filter=year)
            year_recommendations[str(year)] = generate_violation_recommendations(df, ac, lc, year_filter=year)

    return {
        "df": df, "is_sample": is_sample, "years": years,
        "yc": yc, "lc": lc, "fc": fc, "ac": ac, "lac": lac, "loc": loc, "rc": rc,
        "year_counts": year_counts, "law_counts": law_counts,
        "fact_counts": fact_counts, "area_counts": area_counts,
        "kpi_all": kpi_all,
        "kpi_year": kpi_year,
        "all_insights": all_insights,
        "all_recommendations": all_recommendations,
        "year_insights": year_insights,
        "year_recommendations": year_recommendations,
    }


def make_violation_charts(a):
    if a is None:
        return {}, []
    figs = {}
    all_figs = []
    sn = "（範例資料）" if a.get("is_sample") else ""
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
            print(f"    [警告] {fn} 失敗: {e}")
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
            print(f"    [警告] {fn} 失敗: {e}")
            return None

    print("\n  生成全部年度違規圖表...")
    all_figs.append(save_bar(a["year_counts"], f"各年度交通違規裁罰件數統計{sn}", "年度", "裁罰件數", "docs/charts/violation_yearly_all.html", "Reds"))
    all_figs.append(save_hbar(a["law_counts"], f"主要違反法條 TOP 15{sn}", "違反法條", "件數", "docs/charts/violation_laws_all.html", "Oranges"))
    all_figs.append(save_hbar(a["fact_counts"], f"主要違規事實 TOP 15{sn}", "違規事實", "件數", "docs/charts/violation_facts_all.html", "Blues"))
    all_figs.append(save_bar(a["area_counts"], f"各行政區交通違規裁罰分布{sn}", "行政區", "裁罰件數", "docs/charts/violation_area_all.html", "Purples"))

    try:
        if yc and yc in df.columns and a["ac"] and a["ac"] in df.columns:
            pivot = df.groupby([yc, a["ac"]]).size().unstack(fill_value=0)
            if pivot.shape[0] > 0 and pivot.shape[1] > 0:
                fig = px.imshow(pivot, labels=dict(x="行政區",y="年度",color="件數"),
                               title=f"各年度行政區違規裁罰熱力圖{sn}",
                               aspect="auto", color_continuous_scale="YlOrRd")
                fig.update_layout(template="plotly_white", height=500)
                fig.write_html("docs/charts/violation_heatmap_all.html", include_plotlyjs="cdn")
                all_figs.append("violation_heatmap_all.html")
                print(f"    已生成: violation_heatmap_all.html")
    except Exception as e:
        print(f"    [警告] 熱力圖失敗: {e}")

    all_figs = [f for f in all_figs if f]

    if yc and years:
        print(f"\n  生成各年度違規圖表 ({len(years)} 個年度)...")
        for year in years:
            ydf = df[df[yc] == year]
            if len(ydf) == 0:
                continue
            year_str = str(year)
            yfigs = []
            yfigs.append(save_bar(
                ydf[a["lc"]].value_counts().head(15) if a["lc"] else None,
                f"{year_str}年 主要違反法條 TOP 15{sn}", "違反法條", "件數",
                f"docs/charts/violation_laws_{year_str}.html", "Oranges"))
            yfigs.append(save_bar(
                ydf[a["fc"]].value_counts().head(15) if a["fc"] else None,
                f"{year_str}年 主要違規事實 TOP 15{sn}", "違規事實", "件數",
                f"docs/charts/violation_facts_{year_str}.html", "Blues"))
            yfigs.append(save_bar(
                ydf[a["ac"]].value_counts() if a["ac"] else None,
                f"{year_str}年 各行政區交通違規裁罰分布{sn}", "行政區", "裁罰件數",
                f"docs/charts/violation_area_{year_str}.html", "Purples"))
            figs[year_str] = [f for f in yfigs if f]

    print(f"  違規圖表: 全部 {len(all_figs)} 個, 年度 {len(figs)} 組")
    return figs, all_figs


def make_violation_maps(a):
    if a is None:
        return {}, None
    df, lac, loc = a["df"], a["lac"], a["loc"]
    yc, lc, fc, ac, rc = a["yc"], a["lc"], a["fc"], a["ac"], a["rc"]
    years = a["years"]
    sn = "（範例資料）" if a.get("is_sample") else ""

    if not lac or lac not in df.columns or not loc or loc not in df.columns:
        print("  [資訊] 缺少座標資料，略過違規地圖")
        return {}, None

    dm = df.copy()
    dm[lac] = pd.to_numeric(dm[lac], errors="coerce")
    dm[loc] = pd.to_numeric(dm[loc], errors="coerce")
    dm = dm.dropna(subset=[lac, loc])
    if len(dm) == 0:
        print("  [資訊] 無有效座標")
        return {}, None

    year_maps = {}

    print("\n  生成違規綜合地圖(全部年度分層)...")
    try:
        m_all = folium.Map(location=[dm[lac].median(), dm[loc].median()], zoom_start=11)
        add_free_basemaps(m_all)

        if yc and yc in dm.columns and years:
            for year in years:
                ydf = dm[dm[yc] == year]
                if len(ydf) == 0:
                    continue
                fg = folium.FeatureGroup(name=f"{year}年違規點位{sn}")
                mc = MarkerCluster().add_to(fg)
                for _, row in ydf.iterrows():
                    popup = f"<b>年度:</b> {row.get(yc,'N/A')}<br>"
                    if ac: popup += f"<b>行政區:</b> {row.get(ac,'N/A')}<br>"
                    if rc: popup += f"<b>路段:</b> {row.get(rc,'N/A')}<br>"
                    if lc: popup += f"<b>法條:</b> {str(row.get(lc,'N/A'))[:50]}<br>"
                    if fc: popup += f"<b>事實:</b> {str(row.get(fc,'N/A'))[:50]}"
                    folium.CircleMarker(location=[row[lac],row[loc]], radius=3,
                        popup=folium.Popup(popup,max_width=300),
                        color="red", fill=True, fill_opacity=0.6).add_to(mc)
                fg.add_to(m_all)
        else:
            mc = MarkerCluster().add_to(m_all)
            for _, row in dm.iterrows():
                popup = ""
                if ac: popup += f"<b>行政區:</b> {row.get(ac,'N/A')}<br>"
                if rc: popup += f"<b>路段:</b> {row.get(rc,'N/A')}<br>"
                if lc: popup += f"<b>法條:</b> {str(row.get(lc,'N/A'))[:50]}"
                folium.CircleMarker(location=[row[lac],row[loc]], radius=3,
                    popup=folium.Popup(popup,max_width=300),
                    color="red", fill=True, fill_opacity=0.6).add_to(mc)

        folium.LayerControl(collapsed=False).add_to(m_all)
        m_all.save("docs/maps/violation_map_all.html")
        print(f"    已生成: maps/violation_map_all.html")
        all_map = "maps/violation_map_all.html"
    except Exception as e:
        print(f"    [警告] 綜合地圖失敗: {e}")
        traceback.print_exc()
        all_map = None

    if yc and years:
        print(f"\n  生成各年度違規地圖 ({len(years)} 個)...")
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
                    popup = f"<b>年度:</b> {row.get(yc,'N/A')}<br>"
                    if ac: popup += f"<b>行政區:</b> {row.get(ac,'N/A')}<br>"
                    if rc: popup += f"<b>路段:</b> {row.get(rc,'N/A')}<br>"
                    if lc: popup += f"<b>法條:</b> {str(row.get(lc,'N/A'))[:50]}<br>"
                    if fc: popup += f"<b>事實:</b> {str(row.get(fc,'N/A'))[:50]}"
                    folium.CircleMarker(location=[row[lac],row[loc]], radius=3,
                        popup=folium.Popup(popup,max_width=300),
                        color="red", fill=True, fill_opacity=0.6).add_to(mc)
                folium.LayerControl().add_to(m)
                m.save(f"docs/maps/violation_map_{year_str}.html")
                year_maps[year_str] = f"maps/violation_map_{year_str}.html"
                print(f"    已生成: maps/violation_map_{year_str}.html")
            except Exception as e:
                print(f"    [警告] {year}年地圖失敗: {e}")

    print(f"  違規地圖: 綜合 1 個, 年度 {len(year_maps)} 個")
    return year_maps, all_map


def analyze_accidents():
    print("\n" + "=" * 60)
    print("【交通事故資料】")
    print("=" * 60)

    df = pd.DataFrame()
    used_id = None
    for ds_id in ACCIDENT_DATASET_IDS:
        df = fetch_dataset(ds_id, "交通事故")
        if not df.empty:
            used_id = ds_id
            break

    is_sample = False
    if df.empty:
        print("  [警告] 所有事故 API 均失敗，改用範例資料")
        df = sample_accidents(3000)
        is_sample = True

    print(f"  使用: {used_id or '範例資料'}")
    print(f"  欄位: {list(df.columns)}")

    # 針對範例資料和 API 資料的欄位名稱做對應
    yc = find_col(df, ["year","Year","YEAR","年度","年","發生年度"])
    tc = find_col(df, ["type","Type","TYPE","事故類別","事故類別名稱","類別","accident_type"])
    ac = find_col(df, ["area","Area","AREA","發生市區鄉鎮名稱","行政區","區","district"])
    pc = find_col(df, ["place","Place","場所","事故位置","位置"])
    vc = find_col(df, ["vehicle","Vehicle","車種","當事者使用車種_大類別","運具","vehicle_type"])
    cc = find_col(df, ["count","Count","案件總數","總數","件數","case_count"])
    dc = find_col(df, ["death","Death","死亡","死亡人數","deaths"])
    ic = find_col(df, ["injury","Injury","受傷","受傷人數","injuries"])

    print(f"  欄位對應: year={yc}, type={tc}, area={ac}, count={cc}, death={dc}, injury={ic}")

    # 確保數值欄位正確轉換
    for col in [cc, dc, ic]:
        if col and col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    years = []
    if yc and yc in df.columns:
        df[yc] = df[yc].astype(str)
        years = sorted(df[yc].dropna().unique())
    print(f"  資料年度: {years}")

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
        if cc: agg["案件總數"] = (cc, "sum")
        if dc: agg["死亡總數"] = (dc, "sum")
        if ic: agg["受傷總數"] = (ic, "sum")
        if agg:
            dis = df.groupby(yc).agg(**agg)

    # 全年度 KPI
    kpi_all = compute_accident_kpi(df, yc, ac, tc, cc, dc, ic, year_filter=None)
    change, latest = compute_yoy_change(year_stats)
    kpi_all["yoy_change"] = change
    kpi_all["avg_cases"] = year_stats.mean() if year_stats is not None else 0

    # 各年度 KPI
    kpi_year = {}
    if yc and years:
        for year in years:
            ky = compute_accident_kpi(df, yc, ac, tc, cc, dc, ic, year_filter=year)
            ky["yoy_change"] = None
            ky["avg_cases"] = year_stats.get(year, 0) if year_stats is not None else 0
            kpi_year[str(year)] = ky

    # 全年度分析摘要與建議
    all_insights = generate_accident_insights(df, yc, ac, tc, cc, dc, ic, year_filter=None)
    all_recommendations = generate_accident_recommendations(df, yc, ac, tc, cc, dc, year_filter=None)

    # 各年度分析摘要與建議
    year_insights = {}
    year_recommendations = {}
    if yc and years:
        for year in years:
            year_insights[str(year)] = generate_accident_insights(df, yc, ac, tc, cc, dc, ic, year_filter=year)
            year_recommendations[str(year)] = generate_accident_recommendations(df, yc, ac, tc, cc, dc, year_filter=year)

    return {
        "df": df, "is_sample": is_sample, "years": years,
        "yc": yc, "tc": tc, "ac": ac, "pc": pc, "vc": vc, "cc": cc, "dc": dc, "ic": ic,
        "year_stats": year_stats, "type_stats": type_stats, "area_stats": area_stats,
        "place_stats": place_stats, "vehicle_stats": vehicle_stats, "dis": dis,
        "kpi_all": kpi_all,
        "kpi_year": kpi_year,
        "all_insights": all_insights,
        "all_recommendations": all_recommendations,
        "year_insights": year_insights,
        "year_recommendations": year_recommendations,
    }


def make_accident_charts(a):
    if a is None:
        return {}, []
    figs = {}
    all_figs = []
    sn = "（範例資料）" if a.get("is_sample") else ""
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
            print(f"    [警告] {fn} 失敗: {e}")
            return None

    print("\n  生成全部年度事故圖表...")

    all_figs.append(save_bar(a["year_stats"], f"各年度交通事故件數統計{sn}", "年度", "事故件數", "docs/charts/accident_yearly_all.html", "Reds"))

    try:
        d = a["type_stats"]
        if d is not None and len(d) > 0:
            fig = px.pie(names=d.index, values=d.values, title=f"主要事故類別分布{sn}", hole=0.4)
            fig.update_traces(textposition="inside", textinfo="percent+label")
            fig.update_layout(template="plotly_white")
            fig.write_html("docs/charts/accident_type_all.html", include_plotlyjs="cdn")
            all_figs.append("accident_type_all.html")
            print(f"    已生成: accident_type_all.html")
    except Exception as e:
        print(f"    [警告] 類別分布失敗: {e}")

    all_figs.append(save_bar(a["area_stats"], f"各行政區交通事故分布{sn}", "地區", "事故件數", "docs/charts/accident_area_all.html", "Oranges"))

    try:
        d = a["place_stats"]
        if d is not None and len(d) > 0:
            d15 = d.head(15)
            fig = px.bar(y=d15.index[::-1], x=d15.values[::-1],
                         orientation="h", labels={"y":"場所類別","x":"事故件數"},
                         title=f"事故場所類別分布 TOP 15{sn}",
                         color=d15.values[::-1], color_continuous_scale="Blues")
            fig.update_layout(template="plotly_white")
            fig.write_html("docs/charts/accident_place_all.html", include_plotlyjs="cdn")
            all_figs.append("accident_place_all.html")
            print(f"    已生成: accident_place_all.html")
    except Exception as e:
        print(f"    [警告] 場所分布失敗: {e}")

    try:
        d = a["vehicle_stats"]
        if d is not None and len(d) > 0:
            d15 = d.head(15)
            fig = px.bar(y=d15.index[::-1], x=d15.values[::-1],
                         orientation="h", labels={"y":"運具類別","x":"事故件數"},
                         title=f"事故運具類別分布 TOP 15{sn}",
                         color=d15.values[::-1], color_continuous_scale="Greens")
            fig.update_layout(template="plotly_white")
            fig.write_html("docs/charts/accident_vehicle_all.html", include_plotlyjs="cdn")
            all_figs.append("accident_vehicle_all.html")
            print(f"    已生成: accident_vehicle_all.html")
    except Exception as e:
        print(f"    [警告] 運具分布失敗: {e}")

    try:
        dis = a["dis"]
        if dis is not None and len(dis) > 0:
            fig = go.Figure()
            for col in dis.columns:
                fig.add_trace(go.Scatter(x=dis.index.astype(str), y=dis[col].values,
                                         mode="lines+markers", name=col))
            fig.update_layout(title=f"各年度交通事故傷亡趨勢{sn}",
                              xaxis_title="年度", yaxis_title="人數/件數", template="plotly_white",
                              legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            fig.write_html("docs/charts/accident_casualty_all.html", include_plotlyjs="cdn")
            all_figs.append("accident_casualty_all.html")
            print(f"    已生成: accident_casualty_all.html")
    except Exception as e:
        print(f"    [警告] 傷亡趨勢失敗: {e}")

    all_figs = [f for f in all_figs if f]

    if yc and years:
        print(f"\n  生成各年度事故圖表 ({len(years)} 個年度)...")
        for year in years:
            ydf = df[df[yc] == year]
            if len(ydf) == 0:
                continue
            year_str = str(year)
            yfigs = []
            yfigs.append(save_bar(
                ydf[a["tc"]].value_counts().head(15) if a["tc"] else None,
                f"{year_str}年 主要事故類別分布{sn}", "事故類別", "件數",
                f"docs/charts/accident_type_{year_str}.html", "Oranges"))
            yfigs.append(save_bar(
                ydf[a["ac"]].value_counts() if a["ac"] else None,
                f"{year_str}年 各行政區交通事故分布{sn}", "地區", "事故件數",
                f"docs/charts/accident_area_{year_str}.html", "Purples"))
            yfigs.append(save_bar(
                ydf[a["pc"]].value_counts().head(15) if a["pc"] else None,
                f"{year_str}年 事故場所類別分布 TOP 15{sn}", "場所類別", "件數",
                f"docs/charts/accident_place_{year_str}.html", "Blues"))
            yfigs.append(save_bar(
                ydf[a["vc"]].value_counts().head(15) if a["vc"] else None,
                f"{year_str}年 事故運具類別分布 TOP 15{sn}", "運具類別", "件數",
                f"docs/charts/accident_vehicle_{year_str}.html", "Greens"))
            figs[year_str] = [f for f in yfigs if f]

    print(f"  事故圖表: 全部 {len(all_figs)} 個, 年度 {len(figs)} 組")
    return figs, all_figs


def make_accident_maps(a):
    if a is None:
        return {}, None
    df = a["df"]
    ac, cc, dc, ic, yc = a["ac"], a["cc"], a["dc"], a["ic"], a["yc"]
    years = a["years"]
    sn = "（範例資料）" if a.get("is_sample") else ""

    if not ac or ac not in df.columns:
        print("  [資訊] 缺少行政區資料，略過事故地圖")
        return {}, None

    year_maps = {}

    print("\n  生成事故綜合地圖(全部年度分層)...")
    try:
        m_all = folium.Map(location=[24.95, 121.25], zoom_start=10)
        add_free_basemaps(m_all)

        if yc and yc in df.columns and years:
            for year in years:
                ydf = df[df[yc] == year]
                if len(ydf) == 0:
                    continue
                fg = folium.FeatureGroup(name=f"{year}年事故熱點{sn}")
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
                            popup = f"<b>{year}年 {area}</b><br>事故件數: {int(count)}"
                            if dc and dc in ydf.columns:
                                popup += f"<br>死亡: {int(ydf[ydf[ac]==area][dc].sum())}"
                            if ic and ic in ydf.columns:
                                popup += f"<br>受傷: {int(ydf[ydf[ac]==area][ic].sum())}"
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
                        popup=folium.Popup(f"<b>{area}</b><br>事故件數: {int(count)}",max_width=250),
                        color="orange", fill=True, fill_color="orange", fill_opacity=0.6).add_to(m_all)

        folium.LayerControl(collapsed=False).add_to(m_all)
        m_all.save("docs/maps/accident_map_all.html")
        print(f"    已生成: maps/accident_map_all.html")
        all_map = "maps/accident_map_all.html"
    except Exception as e:
        print(f"    [警告] 綜合地圖失敗: {e}")
        traceback.print_exc()
        all_map = None

    if yc and years:
        print(f"\n  生成各年度事故地圖 ({len(years)} 個)...")
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
                        popup = f"<b>{year}年 {area}</b><br>事故件數: {int(count)}"
                        if dc and dc in ydf.columns:
                            popup += f"<br>死亡: {int(ydf[ydf[ac]==area][dc].sum())}"
                        if ic and ic in ydf.columns:
                            popup += f"<br>受傷: {int(ydf[ydf[ac]==area][ic].sum())}"
                        folium.CircleMarker(location=coords, radius=r,
                            popup=folium.Popup(popup,max_width=250),
                            color="orange", fill=True, fill_color="orange", fill_opacity=0.6).add_to(m)
                folium.LayerControl().add_to(m)
                m.save(f"docs/maps/accident_map_{year_str}.html")
                year_maps[year_str] = f"maps/accident_map_{year_str}.html"
                print(f"    已生成: maps/accident_map_{year_str}.html")
            except Exception as e:
                print(f"    [警告] {year}年地圖失敗: {e}")

    print(f"  事故地圖: 綜合 1 個, 年度 {len(year_maps)} 個")
    return year_maps, all_map


def generate_index(v_data, a_data):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    v_year_figs = v_data.get("year_figs", {})
    v_all_figs = v_data.get("all_figs", [])
    v_year_maps = v_data.get("year_maps", {})
    v_all_map = v_data.get("all_map")
    v_years = v_data.get("years", [])
    v_sample = v_data.get("is_sample", False)
    v_kpi_all = v_data.get("kpi_all", {})
    v_kpi_year = v_data.get("kpi_year", {})
    v_all_insights = v_data.get("all_insights", [])
    v_all_recommendations = v_data.get("all_recommendations", [])
    v_year_insights = v_data.get("year_insights", {})
    v_year_recommendations = v_data.get("year_recommendations", {})

    a_year_figs = a_data.get("year_figs", {})
    a_all_figs = a_data.get("all_figs", [])
    a_year_maps = a_data.get("year_maps", {})
    a_all_map = a_data.get("all_map")
    a_years = a_data.get("years", [])
    a_sample = a_data.get("is_sample", False)
    a_kpi_all = a_data.get("kpi_all", {})
    a_kpi_year = a_data.get("kpi_year", {})
    a_all_insights = a_data.get("all_insights", [])
    a_all_recommendations = a_data.get("all_recommendations", [])
    a_year_insights = a_data.get("year_insights", {})
    a_year_recommendations = a_data.get("year_recommendations", {})

    all_years = sorted(set([str(y) for y in v_years] + [str(y) for y in a_years]))

    sample_banner = ""
    if v_sample or a_sample:
        sample_banner = '<div style="background:#fff3cd;border:1px solid #ffeaa7;border-radius:8px;padding:1rem;margin:1rem 0;text-align:center;color:#856404;"><strong>注意：</strong>目前顯示範例資料。API 可能因網路或資料集異動失敗，請查看 GitHub Actions 日誌。</div>'

    year_options = '<option value="all">全部年度</option>\n'
    for year in all_years:
        year_options += f'    <option value="{year}">{year}年</option>\n'

    # 生成 KPI HTML（支援年度切換）
    def build_kpi_html(kpi_all, kpi_year, section, is_accident=False):
        # 全年度 KPI
        change = kpi_all.get("yoy_change")
        change_str = f"{change:+.1f}%" if change is not None else "N/A"
        change_color = "#e74c3c" if change and change > 0 else "#27ae60" if change and change < 0 else "#1a5276"

        html = f'<div id="{section}_kpi_all" class="kpi-grid" style="display:grid;">\n'
        html += kpi_card("&#128203;", "總案件數", f"{kpi_all.get('total_cases', 0):,}")
        if is_accident:
            html += kpi_card("&#128128;", "死亡人數", f"{kpi_all.get('total_deaths', 0):,}")
            html += kpi_card("&#129657;", "受傷人數", f"{kpi_all.get('total_injuries', 0):,}")
        html += kpi_card("&#128200;", "年度變化", change_str, color=change_color)
        html += kpi_card("&#128205;", "年均案件數", f"{kpi_all.get('avg_cases', 0):.0f}")
        html += kpi_card("&#128681;", "最高風險行政區", kpi_all.get('top_district', 'N/A'))
        if is_accident:
            html += kpi_card("&#9888;", "主要事故類型", kpi_all.get('top_type', 'N/A'))
        else:
            html += kpi_card("&#9888;", "主要違規類型", kpi_all.get('top_violation', 'N/A'))
        html += '</div>'

        # 各年度 KPI
        for year, ky in kpi_year.items():
            html += f'<div id="{section}_kpi_{year}" class="kpi-grid" style="display:none;">\n'
            html += kpi_card("&#128203;", "總案件數", f"{ky.get('total_cases', 0):,}")
            if is_accident:
                html += kpi_card("&#128128;", "死亡人數", f"{ky.get('total_deaths', 0):,}")
                html += kpi_card("&#129657;", "受傷人數", f"{ky.get('total_injuries', 0):,}")
            html += kpi_card("&#128200;", "年度變化", "N/A", color="#1a5276")
            html += kpi_card("&#128205;", "該年案件數", f"{ky.get('avg_cases', 0):.0f}")
            html += kpi_card("&#128681;", "最高風險行政區", ky.get('top_district', 'N/A'))
            if is_accident:
                html += kpi_card("&#9888;", "主要事故類型", ky.get('top_type', 'N/A'))
            else:
                html += kpi_card("&#9888;", "主要違規類型", ky.get('top_violation', 'N/A'))
            html += '</div>'

        return html

    def kpi_card(icon, label, value, unit="", color="#1a5276"):
        return f'''<div class="kpi-card" style="border-top-color:{color}">
  <div class="kpi-icon">{icon}</div>
  <div class="kpi-label">{label}</div>
  <div class="kpi-value">{value}<span class="kpi-unit">{unit}</span></div>
</div>'''

    # 生成分析摘要與建議 HTML（支援年度切換）
    def build_insights_html(all_insights, year_insights, section):
        html = f'<div id="{section}_insights_all" class="insights-card" style="display:block;">'
        html += '<h3>專業分析摘要</h3><ul>'
        for item in all_insights:
            html += f'<li>{item}</li>'
        html += '</ul></div>'

        for year, insights in year_insights.items():
            html += f'<div id="{section}_insights_{year}" class="insights-card" style="display:none;">'
            html += f'<h3>{year}年 專業分析摘要</h3><ul>'
            for item in insights:
                html += f'<li>{item}</li>'
            html += '</ul></div>'
        return html

    def build_recommendations_html(all_recs, year_recs, section):
        html = f'<div id="{section}_recommendations_all" class="recommendations-card" style="display:block;">'
        html += '<h3>決策建議</h3><ul>'
        for item in all_recs:
            html += f'<li>{item}</li>'
        html += '</ul></div>'

        for year, recs in year_recs.items():
            html += f'<div id="{section}_recommendations_{year}" class="recommendations-card" style="display:none;">'
            html += f'<h3>{year}年 決策建議</h3><ul>'
            for item in recs:
                html += f'<li>{item}</li>'
            html += '</ul></div>'
        return html

    chart_switch_js = """
function switchCharts(section, year) {
    var allContainer = document.getElementById(section + '_charts_all');
    if (allContainer) allContainer.style.display = 'none';
    document.querySelectorAll('[id^="' + section + '_charts_"]').forEach(function(el) {
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
    document.querySelectorAll('[id^="' + section + '_map_"]').forEach(function(el) {
        if (el.id !== section + '_map_all') el.style.display = 'none';
    });
    if (year === 'all') {
        if (allFrame) allFrame.style.display = 'block';
    } else {
        var target = document.getElementById(section + '_map_' + year);
        if (target) target.style.display = 'block';
    }
}

function switchKPI(section, year) {
    var allDiv = document.getElementById(section + '_kpi_all');
    if (allDiv) allDiv.style.display = 'none';
    document.querySelectorAll('[id^="' + section + '_kpi_"]').forEach(function(el) {
        if (el.id !== section + '_kpi_all') el.style.display = 'none';
    });
    if (year === 'all') {
        if (allDiv) allDiv.style.display = 'grid';
    } else {
        var target = document.getElementById(section + '_kpi_' + year);
        if (target) target.style.display = 'grid';
    }
}

function switchInsights(section, year) {
    var allDiv = document.getElementById(section + '_insights_all');
    if (allDiv) allDiv.style.display = 'none';
    document.querySelectorAll('[id^="' + section + '_insights_"]').forEach(function(el) {
        if (el.id !== section + '_insights_all') el.style.display = 'none';
    });
    if (year === 'all') {
        if (allDiv) allDiv.style.display = 'block';
    } else {
        var target = document.getElementById(section + '_insights_' + year);
        if (target) target.style.display = 'block';
    }
}

function switchRecommendations(section, year) {
    var allDiv = document.getElementById(section + '_recommendations_all');
    if (allDiv) allDiv.style.display = 'none';
    document.querySelectorAll('[id^="' + section + '_recommendations_"]').forEach(function(el) {
        if (el.id !== section + '_recommendations_all') el.style.display = 'none';
    });
    if (year === 'all') {
        if (allDiv) allDiv.style.display = 'block';
    } else {
        var target = document.getElementById(section + '_recommendations_' + year);
        if (target) target.style.display = 'block';
    }
}

function switchYear(section, year) {
    switchKPI(section, year);
    switchCharts(section, year);
    switchMap(section, year);
    switchInsights(section, year);
    switchRecommendations(section, year);
}
"""

    def build_chart_grid(filenames, section, year_key):
        if not filenames:
            return '<p style="padding:2rem;color:#888;text-align:center;">暫無資料</p>'
        display = "grid" if year_key == "all" else "none"
        html = f'<div id="{section}_charts_{year_key}" class="chart-grid" style="display:{display};">'
        for fn in filenames:
            if not fn:
                continue
            name = fn.replace(".html","").replace("violation_","").replace("accident_","").replace("_all","").replace("_"," ")
            path = f"charts/{fn}"
            html += f'<div class="chart-card"><h3>{name}</h3><iframe src="{path}" width="100%" height="450"></iframe></div>'
        html += '</div>'
        return html

    def build_map(filename, section, year_key):
        if not filename:
            return '<p style="padding:2rem;color:#888;text-align:center;">暫無地圖資料</p>'
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
        v_maps_html = '<p style="padding:2rem;color:#888;text-align:center;">暫無地圖資料</p>'

    a_charts_html = build_chart_grid(a_all_figs, "accident", "all")
    for year, filenames in a_year_figs.items():
        a_charts_html += build_chart_grid(filenames, "accident", year)

    a_maps_html = ""
    if a_all_map:
        a_maps_html += build_map(a_all_map, "accident", "all")
    for year, filename in a_year_maps.items():
        a_maps_html += build_map(filename, "accident", year)
    if not a_maps_html:
        a_maps_html = '<p style="padding:2rem;color:#888;text-align:center;">暫無地圖資料</p>'

    v_kpi_html = build_kpi_html(v_kpi_all, v_kpi_year, "violation", is_accident=False)
    a_kpi_html = build_kpi_html(a_kpi_all, a_kpi_year, "accident", is_accident=True)

    v_insights_html = build_insights_html(v_all_insights, v_year_insights, "violation")
    v_recs_html = build_recommendations_html(v_all_recommendations, v_year_recommendations, "violation")
    a_insights_html = build_insights_html(a_all_insights, a_year_insights, "accident")
    a_recs_html = build_recommendations_html(a_all_recommendations, a_year_recommendations, "accident")

    css = """:root{--primary:#1a5276;--secondary:#2874a6;--accent:#e74c3c;--bg:#f8f9fa;--card-bg:#ffffff;--text:#2c3e50;--border:#dee2e6;--success:#27ae60;--warning:#f39c12}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Segoe UI","Microsoft JhengHei",sans-serif;background:var(--bg);color:var(--text);line-height:1.6}
header{background:linear-gradient(135deg,var(--primary),var(--secondary));color:white;padding:2rem 1rem;text-align:center;position:relative}
header h1{font-size:1.8rem;margin-bottom:0.5rem}
header p{opacity:0.9;font-size:0.95rem}
nav{background:#1a5276;padding:0.5rem 1rem;text-align:center;position:sticky;top:0;z-index:100;box-shadow:0 2px 4px rgba(0,0,0,0.1)}
nav a{color:white;text-decoration:none;margin:0 1rem;font-size:0.95rem;padding:0.3rem 0.8rem;border-radius:4px;display:inline-block}
nav a:hover{background:rgba(255,255,255,0.2)}
.update-time{text-align:center;padding:0.5rem;background:#e8f4f8;font-size:0.85rem;color:#555}
main{max-width:1400px;margin:0 auto;padding:1.5rem}
.section-title{font-size:1.4rem;color:var(--primary);margin:2rem 0 1rem;padding-bottom:0.5rem;border-bottom:3px solid var(--secondary);display:flex;align-items:center;gap:1rem;flex-wrap:wrap}
.year-selector{background:white;border:1px solid var(--border);border-radius:6px;padding:0.4rem 0.8rem;font-size:1rem;color:var(--text);cursor:pointer}
.sample-banner{background:#fff3cd;border:1px solid #ffeaa7;border-radius:8px;padding:1rem;margin:1rem 0;text-align:center;color:#856404}
.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1rem;margin-bottom:1.5rem}
.kpi-card{background:var(--card-bg);border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.08);padding:1.2rem;text-align:center;border-top:4px solid var(--primary);transition:transform 0.2s}
.kpi-card:hover{transform:translateY(-3px);box-shadow:0 4px 16px rgba(0,0,0,0.12)}
.kpi-icon{font-size:1.8rem;margin-bottom:0.3rem}
.kpi-label{font-size:0.85rem;color:#888;margin-bottom:0.3rem;text-transform:uppercase;letter-spacing:0.5px}
.kpi-value{font-size:1.6rem;font-weight:bold;color:var(--primary)}
.kpi-unit{font-size:0.9rem;color:#888;margin-left:0.2rem}
.chart-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(500px,1fr));gap:1.5rem;margin-bottom:1.5rem}
.chart-card,.map-card,.insights-card,.recommendations-card{background:var(--card-bg);border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.08);padding:1rem;transition:transform 0.2s}
.chart-card:hover,.map-card:hover{transform:translateY(-2px);box-shadow:0 4px 16px rgba(0,0,0,0.12)}
.chart-card h3,.map-card h3{font-size:1rem;color:var(--primary);margin-bottom:0.75rem;padding-left:0.5rem;border-left:4px solid var(--accent)}
.map-card{margin-bottom:1.5rem}
iframe{border-radius:8px;width:100%;border:none}
.insights-card{border-left:4px solid var(--secondary);margin-bottom:1rem}
.insights-card h3{color:var(--primary);margin-bottom:0.75rem;font-size:1.1rem}
.insights-card ul{margin-left:1.5rem;color:#444}
.insights-card li{margin-bottom:0.5rem}
.recommendations-card{border-left:4px solid var(--success);margin-bottom:1.5rem}
.recommendations-card h3{color:var(--success);margin-bottom:0.75rem;font-size:1.1rem}
.recommendations-card ul{margin-left:1.5rem;color:#444}
.recommendations-card li{margin-bottom:0.5rem}
footer{text-align:center;padding:1.5rem;color:#888;font-size:0.8rem;border-top:1px solid var(--border)}
footer a{color:var(--secondary);text-decoration:none}
@media(max-width:600px){.chart-grid{grid-template-columns:1fr}header h1{font-size:1.3rem}nav a{margin:0 0.3rem;font-size:0.85rem}.section-title{font-size:1.1rem}.kpi-grid{grid-template-columns:repeat(2,1fr)}}"""

    html = f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>桃園市交通裁罰及傷亡資訊報告</title>
<style>{css}</style>
<script>{chart_switch_js}</script>
</head>
<body>
<header>
  <h1>桃園市交通裁罰及傷亡資訊報告</h1>
  <p>資料來源：桃園資料開放平台 | 透過 GitHub Actions 自動更新</p>
</header>
<nav>
  <a href="#violations">交通違規裁罰</a>
  <a href="#accidents">交通事故分析</a>
</nav>
<div class="update-time">報告生成時間：{now}</div>
{sample_banner}
<main>

<section id="violations">
<div class="section-title">
  交通違規裁罰分析
  <select class="year-selector" onchange="switchYear('violation', this.value)">
{year_options}  </select>
</div>
{v_kpi_html}
{v_insights_html}
{v_recs_html}
{v_charts_html}
<div class="map-card">
  <h3>違規裁罰點位分布地圖</h3>
  {v_maps_html}
  <p style="font-size:0.8rem;color:#888;margin-top:0.5rem;">免費底圖：OpenStreetMap、CartoDB Positron/Dark、Esri 衛星影像。使用右上角圖層控制切換。綜合地圖可透過左側圖層選單切換年度。</p>
</div>
</section>

<section id="accidents">
<div class="section-title">
  交通事故分析
  <select class="year-selector" onchange="switchYear('accident', this.value)">
{year_options}  </select>
</div>
{a_kpi_html}
{a_insights_html}
{a_recs_html}
{a_charts_html}
<div class="map-card">
  <h3>交通事故熱點分布地圖</h3>
  {a_maps_html}
  <p style="font-size:0.8rem;color:#888;margin-top:0.5rem;">免費底圖：OpenStreetMap、CartoDB Positron/Dark、Esri 衛星影像。使用右上角衛星影像。使用右上角圖層控制切換。綜合地圖可透過左側圖層選單切換年度。</p>
</div>
</section>

</main>
<footer>
  <p>資料來源：<a href="https://opendata.tycg.gov.tw" target="_blank">桃園資料開放平台</a></p>
  <p>本報告由 GitHub Actions 自動生成，僅供參考</p>
</footer>
</body>
</html>'''

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    size = os.path.getsize("docs/index.html")
    print(f"\n[完成] docs/index.html ({size} bytes)")
    return "docs/index.html"


def main():
    print("=" * 60)
    print("桃園市交通裁罰及傷亡資訊報告生成器 v5.3")
    print("=" * 60)

    v_data = {"year_figs": {}, "all_figs": [], "year_maps": {}, "all_map": None, "years": [], "is_sample": False, "kpi_all": {}, "kpi_year": {}, "all_insights": [], "all_recommendations": [], "year_insights": {}, "year_recommendations": {}}
    a_data = {"year_figs": {}, "all_figs": [], "year_maps": {}, "all_map": None, "years": [], "is_sample": False, "kpi_all": {}, "kpi_year": {}, "all_insights": [], "all_recommendations": [], "year_insights": {}, "year_recommendations": {}}

    try:
        va = analyze_violations()
        if va:
            v_data["years"] = va["years"]
            v_data["is_sample"] = va.get("is_sample", False)
            v_data["kpi_all"] = va.get("kpi_all", {})
            v_data["kpi_year"] = va.get("kpi_year", {})
            v_data["all_insights"] = va.get("all_insights", [])
            v_data["all_recommendations"] = va.get("all_recommendations", [])
            v_data["year_insights"] = va.get("year_insights", {})
            v_data["year_recommendations"] = va.get("year_recommendations", {})
            v_year_figs, v_all_figs = make_violation_charts(va)
            v_year_maps, v_all_map = make_violation_maps(va)
            v_data["year_figs"] = v_year_figs
            v_data["all_figs"] = v_all_figs
            v_data["year_maps"] = v_year_maps
            v_data["all_map"] = v_all_map
    except Exception as e:
        print(f"\n[錯誤] 違規分析: {e}")
        traceback.print_exc()

    try:
        aa = analyze_accidents()
        if aa:
            a_data["years"] = aa["years"]
            a_data["is_sample"] = aa.get("is_sample", False)
            a_data["kpi_all"] = aa.get("kpi_all", {})
            a_data["kpi_year"] = aa.get("kpi_year", {})
            a_data["all_insights"] = aa.get("all_insights", [])
            a_data["all_recommendations"] = aa.get("all_recommendations", [])
            a_data["year_insights"] = aa.get("year_insights", {})
            a_data["year_recommendations"] = aa.get("year_recommendations", {})
            a_year_figs, a_all_figs = make_accident_charts(aa)
            a_year_maps, a_all_map = make_accident_maps(aa)
            a_data["year_figs"] = a_year_figs
            a_data["all_figs"] = a_all_figs
            a_data["year_maps"] = a_year_maps
            a_data["all_map"] = a_all_map
    except Exception as e:
        print(f"\n[錯誤] 事故分析: {e}")
        traceback.print_exc()

    print("\n" + "-" * 60)
    print("生成整合主報告頁面...")
    print("-" * 60)
    try:
        generate_index(v_data, a_data)
    except Exception as e:
        print(f"[錯誤] 主報告頁面: {e}")
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("完成。輸出: docs/index.html")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
