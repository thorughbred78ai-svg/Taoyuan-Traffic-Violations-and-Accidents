# Taoyuan-Traffic-Violations-and-Accidents

# 桃園市交通裁罰及傷亡資訊報告

透過 GitHub Actions 自動從「桃園資料開放平台」介接交通違規裁罰與交通事故資料，生成互動式 HTML 報告並發布至 GitHub Pages。

## 功能特性

### v5.3 主要更新
- **年度切換聯動**：KPI 儀表板、圖表、地圖、專業分析摘要、決策建議全部支援「全部年度 / 單一年度」切換
- **KPI 動態更新**：選擇單一年度時，總案件數、死亡/受傷人數、最高風險行政區、主要違規/事故類型會自動更新為該年度數據
- **繁體中文內容**：所有資料標籤、圖表標題、分析摘要、決策建議均為繁體中文
- **事故資料修復**：擴充欄位對應邏輯，同時支援 API 原始欄位與範例資料欄位名稱

### 報告內容
| 區塊 | 內容 |
|------|------|
| 交通違規裁罰分析 | 各年度件數統計、主要違反法條 TOP 15、主要違規事實 TOP 15、行政區分布、熱力圖、點位分布地圖 |
| 交通事故分析 | 各年度件數統計、事故類別分布、行政區分布、場所類別分布、運具類別分布、傷亡趨勢、熱點分布地圖 |
| KPI 儀表板 | 總案件數、死亡/受傷人數、年度變化(YoY)、年均案件數、最高風險行政區、主要類型 |
| 專業分析摘要 | 依據數據自動生成行政區風險分析、違規/事故類型分析 |
| 決策建議 | 依據數據自動生成執法資源部署、道路改善、教育宣導建議 |

### 互動功能
- **年度下拉選單**：切換「全部年度」或單一年度，所有內容同步更新
- **Plotly 圖表**：支援縮放、平移、資料點提示、圖例篩選
- **Folium 地圖**：多層底圖切換（OpenStreetMap / CartoDB Positron / CartoDB Dark / Esri 衛星影像）
- **響應式設計**：支援桌面與行動裝置瀏覽

## 技術棧

| 項目 | 說明 |
|------|------|
| Python 3.x | 資料處理與報告生成 |
| Pandas | 資料彙整與統計 |
| Plotly | 互動式圖表（CDN 載入） |
| Folium | 互動式地圖 |
| GitHub Actions | 自動排程執行（每日 UTC 00:00） |
| GitHub Pages | 靜態網站託管 |

## 資料來源

- [桃園資料開放平台](https://opendata.tycg.gov.tw/)
  - 交通違規舉發資料
  - 交通事故資料（多個資料集自動輪詢）

API 介接失敗時，會自動使用範例資料生成報告，確保網頁正常顯示。

## 部署方式

### 1. Fork / 建立 Repository

將 `generate_report.py` 與 `.github/workflows/report.yml` 放入 Repository 根目錄。

### 2. 設定 GitHub Actions

`.github/workflows/report.yml`：

```yaml
name: Generate Traffic Report

on:
  schedule:
    - cron: '0 0 * * *'  # 每日 UTC 00:00
  workflow_dispatch:      # 支援手動觸發

permissions:
  contents: write
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install pandas requests plotly folium

      - name: Generate report
        run: python generate_report.py

      - name: Upload Pages artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: docs/

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
