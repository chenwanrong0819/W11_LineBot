# W11 作業：股票 LINE Bot

> **繳交方式**：將你的 GitHub repo 網址貼到作業繳交區
> **作業性質**：個人作業

---

## 作業目標

利用上週設計的 Skill，開發一個股票相關的 LINE Bot。
重點不是功能多寡，而是你設計的 **Skill 品質**——Skill 寫得越具體，AI 產出的程式碼就越接近可以直接執行。

---

## 功能要求（擇一實作）

| 功能 | 說明 |
| --- | --- |
| AI 分析股票 | 使用者說股票名稱，Gemini 給出分析 |
| 追蹤清單 | 儲存使用者的自選股清單到 SQLite |
| 查詢即時價格 | 整合 yfinance 或 twstock 取得股價 |

> 以「可以執行、能回覆訊息」為目標，不需要複雜

---

## 繳交項目

你的 GitHub repo 需要包含：

| 項目 | 說明 |
| --- | --- |
| `app.py` | LINE Webhook + Gemini + SQLite 後端 |
| `requirements.txt` | 所有套件 |
| `.env.example` | 環境變數範本（不含真實 token） |
| `.agents/skills/` | 至少包含 `/linebot-implement` Skill |
| `README.md` | 本檔案（含心得報告） |
| `screenshots/chat.png` | LINE Bot 對話截圖（至少一輪完整對話） |

### Skill 要求

`.agents/skills/` 至少需要包含：

- `/linebot-implement`：產出 LINE Bot 主程式（必要）
- `/prd` 或 `/architecture`：延用上週的
- `/commit`：延用上週的

---

## 專案結構

```
your-repo/
├── .agents/
│   └── skills/
│       ├── prd/SKILL.md
│       ├── linebot-implement/SKILL.md
│       └── commit/SKILL.md
├── docs/
│   └── PRD.md
├── screenshots/
│   └── chat.png
├── app.py
├── requirements.txt
├── .env.example
└── README.md
```

> `.env` 和 `users.db` 不要 commit（加入 `.gitignore`）

---

## 啟動方式

```bash
# 1. 建立虛擬環境
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. 安裝套件
pip install -r requirements.txt

# 3. 設定環境變數
cp .env.example .env
# 編輯 .env，填入三個 token

# 4. 啟動 FastAPI
uvicorn app:app --reload

# 5. 另開終端機啟動 ngrok
ngrok http 8000
# 複製 https 網址，填入 LINE Developers Console 的 Webhook URL（加上 /callback）
# 點「Verify」確認連線正常後，掃 QR Code 加好友開始測試
```

---

## 心得報告

**姓名**：陳婉榕
**學號**：D1285534

**Q1. 你在 `/linebot-implement` Skill 的「注意事項」寫了哪些規則？為什麼這樣寫？**

> 我在注意事項中要求程式必須使用 FastAPI 建立 LINE Webhook，並且要能接收使用者訊息後回覆 LINE 訊息。同時也規定環境變數要從 .env 讀取，不能把 LINE token、channel secret、Gemini API key 寫死在程式裡。另外也提醒要使用 SQLite 儲存資料，並且要處理基本錯誤，例如使用者輸入格式錯誤、API 查詢失敗或資料庫連線問題。

這樣寫是因為 LINE Bot 需要和外部服務串接，如果 token 寫死會有安全問題；而且作業目標是做出可以執行、可以回覆訊息的 Bot，所以 Skill 裡必須把 Webhook、AI 回覆、資料庫和錯誤處理都寫清楚，AI 產生的程式才比較接近可直接執行。

---

**Q2. 你的 Skill 第一次執行後，AI 產出的程式直接能跑嗎？需要修改哪些地方？修改後有沒有更新 Skill？**

> 第一次產出的程式大致架構可以使用，但沒有完全直接成功執行。我有修改環境變數名稱、LINE Webhook callback 路徑，以及部分套件匯入方式，讓它和 requirements.txt、.env.example 對應一致。另外也有補上 SQLite 資料表初始化，避免第一次執行時因為找不到資料表而出錯。

修改後我有把這些容易出錯的地方更新回 /linebot-implement Skill，例如要求 AI 必須自動建立資料表、環境變數名稱要固定、callback 路徑要使用 /callback，讓之後產生的程式更穩定。

---

**Q3. 你遇到什麼問題是 AI 沒辦法自己解決、需要你介入處理的？**

> 主要是 LINE Developers Console 和 ngrok 的設定需要自己處理。AI 可以提供程式碼和設定步驟，但實際的 Channel Access Token、Channel Secret、Gemini API Key 都需要我自己建立並填入 .env。另外，Webhook URL 也需要我自己把 ngrok 產生的 HTTPS 網址貼到 LINE Developers Console，並確認 /callback 路徑是否正確。

還有截圖 screenshots/chat.png 也必須由我實際測試 LINE Bot 對話後取得，AI 無法代替我完成真實的 LINE 測試流程。

---

**Q4. 如果你要把這個 LINE Bot 讓朋友使用，你還需要做什麼？**

> 如果要讓朋友使用，不能只在本機用 ngrok 測試，還需要把程式部署到可以長時間運作的雲端平台，例如 Render、Railway 或其他伺服器。接著要把正式的 Webhook URL 設定到 LINE Developers Console，並確認伺服器不會因為本機關閉而中斷。

另外，也需要保護 .env 裡面的 token，不可以上傳到 GitHub。若使用 SQLite，也要考慮資料備份和多人使用時的穩定性。最後還需要測試不同使用者輸入，例如股票代號錯誤、API 查不到資料、Gemini 回覆失敗等情況，避免朋友使用時 Bot 沒有回應。