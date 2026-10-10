# Taoyuan-Traffic-Violations-and-Accidents

# 桃園市交通裁罰及傷亡資訊報告

本專案透過 GitHub Actions 自動從桃園資料開放平台 API 介接資料，生成互動式交通裁罰及傷亡資訊報告，並部署至 GitHub Pages。

## 公開網址

部署完成後，可透過以下網址瀏覽報告：

```
https://<你的 GitHub 帳號>.github.io/<repository 名稱>/
```

例如：`https://username.github.io/taoyuan-traffic-report/`

---

## 專案結構

```
.
├── .github/
│   └── workflows/
│       └── deploy.yml          # GitHub Actions 工作流程
├── generate_report.py           # 報告生成腳本（API 直接介接）
├── docs/                        # 生成的報告輸出目錄
│   └── index.html               # 整合主報告頁面
└── README.md
```

---

## 快速開始

### 1. 建立 GitHub Repository

1. 登入 GitHub，點擊右上角 **+** → **New repository**
2. 輸入 Repository 名稱，例如 `taoyuan-traffic-report`
3. 選擇 **Public**（GitHub Pages 免費版需公開）
4. 點擊 **Create repository**

### 2. 上傳檔案

將以下檔案上傳至 Repository 根目錄：

- `generate_report.py`
- `.github/workflows/deploy.yml`

```bash
git clone https://github.com/<username>/taoyuan-traffic-report.git
cd taoyuan-traffic-report
# 將 generate_report.py 與 deploy.yml 放入對應位置
git add .
git commit -m "Initial commit: add report generator and GitHub Actions"
git push origin main
```

### 3. 啟用 GitHub Pages

1. 進入 Repository → **Settings** → **Pages**
2. **Source** 選擇 **Deploy from a branch**
3. **Branch** 選擇 `gh-pages` / `root`
4. 點擊 **Save**

### 4. 觸發第一次執行

- 方式一：手動觸發
  - 進入 Repository → **Actions** → **Generate and Deploy Report**
  - 點擊 **Run workflow** → **Run workflow**

- 方式二：等待排程
  - 預設每日 UTC 02:00（台灣時間 10:00）自動執行

### 5. 查看報告

Actions 執行完成後（約 3-5 分鐘），即可透過以下網址瀏覽：

```
https://<username>.github.io/<repository-name>/
```

---

## 報告內容

### 交通違規裁罰分析

- 各年度交通違規裁罰件數統計（長條圖）
- 主要違反法條 TOP 15（橫條圖）
- 主要違規事實 TOP 15（橫條圖）
- 各行政區交通違規裁罰分布（長條圖）
- 各年度行政區違規裁罰熱力圖
- 違規裁罰點位分布地圖（folium 互動地圖）

### 交通事故分析

- 各年度交通事故件數統計（長條圖）
- 主要事故類別分布（圓環圖）
- 各行政區交通事故分布（長條圖）
- 事故場所類別分布 TOP 15（橫條圖）
- 事故運具類別分布 TOP 15（橫條圖）
- 各年度交通事故傷亡趨勢（折線圖）
- 交通事故熱點分布地圖（folium 互動地圖）

---

## 技術說明

- **資料來源**：桃園資料開放平台 API（直接介接，不儲存中間檔案）
- **圖表繪製**：Plotly（互動，支援縮放、篩選）
- **地圖繪製**：Folium + MarkerCluster（分層顯示各年度資料）
- **自動化**：GitHub Actions（每日排程 + 手動觸發）
- **部署平台**：GitHub Pages（免費靜態網站代管）

---

## 資料集

| 類別 | Dataset ID | 說明 |
|------|-----------|------|
| 交通違規舉發 | `08b2987e-01e5-458d-a8c1-cd4b540a0105` | 交通違規舉發項目及地點 |
| 交通事故熱點 | `24bf2215-8c80-439e-b553-59ccfc82ca78` | 交通事故點位統計 |

---

## 注意事項

1. GitHub Pages 首次部署可能需要數分鐘才能生效
2. 若 API 資料更新，報告會在下次排程執行後自動更新
3. 本報告僅供參考，實際數據請以桃園資料開放平台為準

---

## License

MIT License
