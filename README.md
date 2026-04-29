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

**姓名**：洪紹禎
**學號**：D1249373

**Q1. 你在 `/linebot-implement` Skill 的「注意事項」寫了哪些規則？為什麼這樣寫？**

> 我在 Skill 中加入了幾條注意事項：第一，Webhook handler 必須使用 async 函式，且耗時的外部 API 呼叫（如 Gemini、twstock）要用 `asyncio.to_thread` 包起來，避免阻塞 event loop；第二，LINE 的 reply token 有效期約一分鐘，若處理時間過長會導致回覆失敗；第三，Gemini 回傳的文字可能包含 Markdown 語法（如 `**粗體**`），LINE 不會渲染，需要在回傳前手動清除。這些規則都是因為初版程式直接踩到這些坑才補上的。

---

**Q2. 你的 Skill 第一次執行後，AI 產出的程式直接能跑嗎？需要修改哪些地方？修改後有沒有更新 Skill？**

> 第一次產出的程式可以啟動，LINE 也能收到 Webhook，但會出現「已讀不回」的問題。原因是 `process_message` 是同步函式，直接在 async handler 裡呼叫會阻塞 event loop，導致 reply token 在回覆送出前就過期。修正方式是改用 `asyncio.to_thread(process_message, ...)` 包起來。此外，Gemini 模型名稱也需要根據目前 API 支援情況調整，並加入備用模型的 fallback 機制。這些問題修正後有更新 Skill 的注意事項。

---

**Q3. 你遇到什麼問題是 AI 沒辦法自己解決、需要你介入處理的？**

> 最主要的問題是 Gemini 模型的可用性。AI 產出的程式使用了 `gemini-2.0-flash`，但該模型後來被下架；改用 `gemini-2.5-flash` 後，又因為流量過高收到 503 錯誤。這類「哪個模型現在實際可用」的問題 AI 無法預先知道，需要我自己去查 Google AI Studio 的文件確認，再告訴 AI 要改成哪個版本。另外，ngrok 每次重啟都會換網址，需要手動更新 LINE Developers Console 的 Webhook URL，這也是 AI 無法自動處理的操作。

---

**Q4. 如果你要把這個 LINE Bot 讓朋友使用，你還需要做什麼？**

> 目前架構跑在本機 + ngrok，關掉電腦 Bot 就離線，不適合給朋友長期使用。若要正式開放，需要：一、部署到雲端伺服器（如 Railway、Render 或 GCP）取得固定的 HTTPS 網址；二、把 API 金鑰透過雲端環境變數設定，不能把 `.env` 一起上傳到 GitHub；三、考慮加入錯誤通知機制，當 Gemini API 連續失敗時能即時收到警告；四、twstock 的即時報價在非交易時段會回傳失敗，需要對使用者給出更友善的提示。