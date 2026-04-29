"""
股票小助手 LINE Bot
====================
查詢台股即時價格 + Gemini AI 分析 + 個人追蹤清單

技術棧：FastAPI + LINE Messaging API v3 + Google Gemini + twstock + SQLite
啟動方式：python -m uvicorn app:app --reload
"""

import os
import json
import hmac
import hashlib
import base64
import logging
import sqlite3
import asyncio
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException

from google import genai
import twstock

from linebot.v3.messaging import (
    Configuration,
    AsyncApiClient,
    AsyncMessagingApi,
    ReplyMessageRequest,
    TextMessage,
)

# ========== 載入環境變數 ==========
load_dotenv()

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ========== Logging 設定 ==========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ========== 資料庫初始化 ==========
DB_PATH = "stocks.db"


def init_db():
    """初始化 SQLite 資料庫，建立所需的 table"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            stock_id TEXT NOT NULL,
            stock_name TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, stock_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS query_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            stock_id TEXT NOT NULL,
            stock_name TEXT,
            query_type TEXT DEFAULT 'price',
            queried_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    logger.info("資料庫初始化完成")


# ========== Gemini AI 初始化 ==========
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# ========== LINE Bot 初始化 ==========
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
async_api_client = AsyncApiClient(configuration)
line_bot_api = AsyncMessagingApi(async_api_client)


# ========== FastAPI 應用 ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式生命週期管理"""
    init_db()
    logger.info("股票小助手 LINE Bot 已啟動")
    yield

app = FastAPI(title="股票小助手 LINE Bot", version="1.0.0", lifespan=lifespan)


# ========== 簽名驗證 ==========
def verify_signature(body: bytes, signature: str) -> bool:
    """驗證 LINE Webhook 簽名"""
    hash_value = hmac.new(
        LINE_CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256
    ).digest()
    expected = base64.b64encode(hash_value).decode("utf-8")
    return hmac.compare_digest(expected, signature)


# ========== 工具函式 ==========

def find_stock_id(keyword: str):
    """根據股票代號或名稱查找股票"""
    if keyword in twstock.codes:
        return (keyword, twstock.codes[keyword].name)
    for code, stock in twstock.codes.items():
        if stock.name == keyword:
            return (code, stock.name)
    return None


def get_realtime_price(stock_id: str):
    """取得台股即時報價"""
    try:
        data = twstock.realtime.get(stock_id)
        if data.get("success"):
            return data
        return None
    except Exception as e:
        logger.error(f"即時報價查詢例外: {e}")
        return None


def format_stock_price(data: dict) -> str:
    """將即時報價資料格式化為文字訊息"""
    info = data.get("info", {})
    realtime = data.get("realtime", {})

    name = info.get("name", "未知")
    code = info.get("code", "----")
    time_str = info.get("time", "")
    latest_price = realtime.get("latest_trade_price", "N/A")
    open_price = realtime.get("open", "N/A")
    high = realtime.get("high", "N/A")
    low = realtime.get("low", "N/A")
    volume = realtime.get("accumulate_trade_volume", "N/A")

    change_str = ""
    yesterday_close = realtime.get("yesterday_close", None)
    if yesterday_close and latest_price and latest_price != "N/A":
        try:
            change = float(latest_price) - float(yesterday_close)
            change_pct = (change / float(yesterday_close)) * 100
            arrow = "📈" if change >= 0 else "📉"
            sign = "+" if change >= 0 else ""
            change_str = f"\n{arrow} 漲跌：{sign}{change:.2f}（{sign}{change_pct:.2f}%）"
        except (ValueError, ZeroDivisionError):
            pass

    return (
        f"📊 {name}（{code}）\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 即時價格：{latest_price}\n"
        f"📖 開盤價：{open_price}\n"
        f"⬆️ 最高：{high}\n"
        f"⬇️ 最低：{low}\n"
        f"📦 成交量：{volume}"
        f"{change_str}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🕐 更新時間：{time_str}"
    )


def ai_analyze_stock(stock_id: str, stock_name: str, price_data) -> str:
    """使用 Gemini AI 分析股票"""
    context = f"股票代號：{stock_id}\n股票名稱：{stock_name}\n"
    if price_data and price_data.get("success"):
        rt = price_data.get("realtime", {})
        context += (
            f"即時價格：{rt.get('latest_trade_price', 'N/A')}\n"
            f"開盤價：{rt.get('open', 'N/A')}\n"
            f"最高價：{rt.get('high', 'N/A')}\n"
            f"最低價：{rt.get('low', 'N/A')}\n"
            f"成交量：{rt.get('accumulate_trade_volume', 'N/A')}\n"
        )

    prompt = f"""你是一位專業的台灣股票分析師。請根據以下股票資訊，提供簡短的分析建議。

{context}

請以繁體中文回覆，包含：1. 📊 技術面簡析 2. 📋 基本面概述 3. 💡 投資建議
回覆控制在 300 字以內，請提醒這只是 AI 分析，不構成投資建議。"""

    for model in ["gemini-2.5-flash", "gemini-2.5-flash-lite"]:
        try:
            response = gemini_client.models.generate_content(
                model=model, contents=prompt,
            )
            text = response.text.replace("**", "")
            return f"🤖 AI 分析：{stock_name}（{stock_id}）\n━━━━━━━━━━━━━━━\n{text}"
        except Exception as e:
            logger.warning(f"Gemini [{model}] 失敗，嘗試下一個模型: {e}")
    return "⚠️ AI 分析暫時無法使用，請稍後再試。"


def log_query(user_id, stock_id, stock_name, query_type="price"):
    """記錄查詢紀錄"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO query_log (user_id, stock_id, stock_name, query_type) VALUES (?, ?, ?, ?)",
            (user_id, stock_id, stock_name, query_type),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"記錄查詢紀錄失敗: {e}")


def add_to_watchlist(user_id, stock_id, stock_name) -> str:
    """加入追蹤清單"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO watchlist (user_id, stock_id, stock_name) VALUES (?, ?, ?)",
            (user_id, stock_id, stock_name),
        )
        if cursor.rowcount > 0:
            conn.commit(); conn.close()
            return f"✅ 已將 {stock_name}（{stock_id}）加入追蹤清單！"
        conn.close()
        return f"ℹ️ {stock_name}（{stock_id}）已在追蹤清單中。"
    except Exception as e:
        logger.error(f"加入追蹤清單失敗: {e}")
        return "⚠️ 加入追蹤清單失敗，請稍後再試。"


def remove_from_watchlist(user_id, stock_id) -> str:
    """移除追蹤清單"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM watchlist WHERE user_id = ? AND stock_id = ?", (user_id, stock_id))
        if cursor.rowcount > 0:
            conn.commit(); conn.close()
            return f"✅ 已將 {stock_id} 從追蹤清單移除。"
        conn.close()
        return f"ℹ️ {stock_id} 不在追蹤清單中。"
    except Exception as e:
        logger.error(f"移除追蹤清單失敗: {e}")
        return "⚠️ 移除追蹤清單失敗，請稍後再試。"


def get_watchlist(user_id) -> str:
    """取得追蹤清單"""
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT stock_id, stock_name FROM watchlist WHERE user_id = ? ORDER BY added_at DESC",
            (user_id,),
        ).fetchall()
        conn.close()
        if not rows:
            return "📋 你的追蹤清單是空的。\n\n輸入「追蹤 <股票代號>」來新增股票！"
        msg = "📋 我的追蹤清單\n━━━━━━━━━━━━━━━\n"
        for i, (sid, sname) in enumerate(rows, 1):
            msg += f"{i}. {sname}（{sid}）\n"
        msg += f"━━━━━━━━━━━━━━━\n共 {len(rows)} 檔股票"
        return msg
    except Exception as e:
        logger.error(f"取得追蹤清單失敗: {e}")
        return "⚠️ 無法取得追蹤清單，請稍後再試。"


def get_help_message() -> str:
    """回傳使用說明"""
    return (
        "📖 股票小助手 使用說明\n"
        "━━━━━━━━━━━━━━━\n"
        "📊 查詢股價\n  → 查詢 2330\n  → 查詢 台積電\n\n"
        "🤖 AI 分析\n  → 分析 2330\n  → 分析 台積電\n\n"
        "⭐ 追蹤清單\n  → 追蹤 2330\n  → 取消追蹤 2330\n  → 我的清單\n\n"
        "❓ 其他\n  → 幫助 / help\n"
        "━━━━━━━━━━━━━━━\n"
        "💬 也可以直接輸入任何股票相關問題，AI 會盡力回答！"
    )


def general_chat(text: str) -> str:
    """一般對話交給 Gemini"""
    prompt = f"""你是一位友善的台灣股票小助手 LINE Bot。
使用者傳了以下訊息，請用繁體中文簡短回覆（200 字以內）。
如果是股票相關問題就回答，如果不是就友善地引導他使用股票功能。

使用者訊息：{text}

提示使用者可以輸入「幫助」查看所有功能。"""
    for model in ["gemini-2.5-flash", "gemini-2.5-flash-lite-preview-06-17"]:
        try:
            response = gemini_client.models.generate_content(
                model=model, contents=prompt,
            )
            return response.text.replace("**", "")
        except Exception as e:
            logger.warning(f"Gemini [{model}] 一般對話失敗，嘗試下一個模型: {e}")
    return "抱歉，我暫時無法回覆。請輸入「幫助」查看可用功能！"


# ========== 訊息處理核心 ==========

def process_message(user_id: str, text: str) -> str:
    """根據使用者輸入處理訊息並回傳回覆文字"""
    text = text.strip()

    if text.startswith("查詢"):
        keyword = text.replace("查詢", "").strip()
        if not keyword:
            return "請輸入股票代號或名稱，例如：查詢 2330"
        result = find_stock_id(keyword)
        if not result:
            return f"❌ 找不到「{keyword}」對應的股票，請確認代號或名稱是否正確。"
        stock_id, stock_name = result
        price_data = get_realtime_price(stock_id)
        if price_data:
            log_query(user_id, stock_id, stock_name, "price")
            return format_stock_price(price_data)
        return f"⚠️ 無法取得 {stock_name}（{stock_id}）的即時報價，可能非交易時段。"

    elif text.startswith("分析"):
        keyword = text.replace("分析", "").strip()
        if not keyword:
            return "請輸入股票代號或名稱，例如：分析 2330"
        result = find_stock_id(keyword)
        if not result:
            return f"❌ 找不到「{keyword}」對應的股票，請確認代號或名稱是否正確。"
        stock_id, stock_name = result
        price_data = get_realtime_price(stock_id)
        log_query(user_id, stock_id, stock_name, "analysis")
        return ai_analyze_stock(stock_id, stock_name, price_data)

    elif text.startswith("取消追蹤"):
        keyword = text.replace("取消追蹤", "").strip()
        if not keyword:
            return "請輸入股票代號，例如：取消追蹤 2330"
        result = find_stock_id(keyword)
        if result:
            return remove_from_watchlist(user_id, result[0])
        return remove_from_watchlist(user_id, keyword)

    elif text.startswith("追蹤"):
        keyword = text.replace("追蹤", "").strip()
        if not keyword:
            return "請輸入股票代號，例如：追蹤 2330"
        result = find_stock_id(keyword)
        if not result:
            return f"❌ 找不到「{keyword}」對應的股票，請確認代號或名稱是否正確。"
        return add_to_watchlist(user_id, result[0], result[1])

    elif text in ["我的清單", "清單", "自選股"]:
        return get_watchlist(user_id)

    elif text.lower() in ["幫助", "help", "說明", "指令"]:
        return get_help_message()

    else:
        return general_chat(text)


# ========== LINE Webhook 路由 ==========

@app.post("/callback")
async def callback(request: Request):
    """LINE Webhook 接收端點 — 直接解析事件，不依賴 WebhookHandler"""
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()

    # 驗證簽名
    if not verify_signature(body, signature):
        logger.error("簽名驗證失敗")
        raise HTTPException(status_code=400, detail="Invalid signature")

    logger.info("收到 Webhook 請求")

    # 解析事件
    try:
        body_json = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    events = body_json.get("events", [])

    for event in events:
        # 只處理文字訊息事件
        if event.get("type") != "message" or event.get("message", {}).get("type") != "text":
            continue

        user_id = event.get("source", {}).get("userId", "unknown")
        text = event.get("message", {}).get("text", "")
        reply_token = event.get("replyToken", "")

        logger.info(f"使用者 {user_id} 傳送：{text}")

        # 處理訊息（在 thread pool 中執行同步阻塞函式，避免卡住 event loop）
        try:
            reply_text = await asyncio.to_thread(process_message, user_id, text)
        except Exception as e:
            logger.error(f"處理訊息時發生例外: {e}")
            reply_text = "⚠️ 處理訊息時發生錯誤，請稍後再試。"

        # 回覆
        try:
            await line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
            logger.info(f"已回覆使用者 {user_id}")
        except Exception as e:
            logger.error(f"回覆訊息失敗: {e}")

    return "OK"


@app.get("/")
async def root():
    """健康檢查端點"""
    return {"status": "ok", "message": "股票小助手 LINE Bot 運行中"}
