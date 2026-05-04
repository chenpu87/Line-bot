# ==========================================
# LINE Bot with Gemini AI + Image Support
# Orange Fruit 小橙特助
# ==========================================
import os
import re
import json
import base64
import datetime
import logging
import tempfile
import urllib.parse
import urllib.request
import requests
import threading
import google.generativeai as genai

from flask import Flask, request, abort, send_file

# Playwright 可用性檢查（Render 上需在 requirements.txt 加 playwright）
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage,
    ImageMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# ==========================================
# 環境變數
# ==========================================
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET       = os.getenv('LINE_CHANNEL_SECRET')
GEMINI_API_KEY            = os.getenv('GEMINI_API_KEY')
NOTIFY_GROUP_ID           = os.getenv('NOTIFY_GROUP_ID', '')
OWNER_USER_ID             = os.getenv('OWNER_USER_ID', '')

SERVICE_START = 9
SERVICE_END   = 12
TZ_OFFSET     = 8

FRAME_CODE_MAP = {
    ("merida", "reacto", "2026"): "MER-REA-26",
    ("merida", "reacto", "2025"): "MER-REA-25",
    ("merida", "reacto", "2024"): "MER-REA-24",
    ("merida", "reacto", "2023"): "MER-REA-23",
    ("merida", "scultura", "2026"): "MER-SCU-26",
    ("merida", "scultura", "2025"): "MER-SCU-25",
    ("merida", "scultura", "2024"): "MER-SCU-24",
    ("merida", "scultura team", "2026"): "MER-SCT-26",
    ("merida", "mission cx", "2026"): "MER-MCX-26",
    ("giant", "tcr advanced", "2026"): "GIA-TCR-26",
    ("giant", "tcr advanced", "2025"): "GIA-TCR-25",
    ("giant", "tcr advanced", "2024"): "GIA-TCR-24",
    ("giant", "tcr advanced sl", "2026"): "GIA-TCS-26",
    ("giant", "propel advanced", "2026"): "GIA-PRO-26",
    ("giant", "propel advanced", "2025"): "GIA-PRO-25",
    ("giant", "defy advanced", "2026"): "GIA-DEF-26",
    ("giant", "defy advanced", "2025"): "GIA-DEF-25",
    ("trek", "madone slr", "2026"): "TRE-MAS-26",
    ("trek", "madone slr", "2025"): "TRE-MAS-25",
    ("trek", "emonda slr", "2026"): "TRE-EMS-26",
    ("trek", "emonda slr", "2025"): "TRE-EMS-25",
    ("trek", "domane slr", "2026"): "TRE-DOS-26",
    ("trek", "domane slr", "2025"): "TRE-DOS-25",
    ("specialized", "tarmac sl8", "2026"): "SPE-TS8-26",
    ("specialized", "tarmac sl8", "2025"): "SPE-TS8-25",
    ("specialized", "venge", "2024"): "SPE-VEN-24",
    ("specialized", "aethos", "2026"): "SPE-AET-26",
    ("canyon", "aeroad", "2026"): "CAN-AER-26",
    ("canyon", "aeroad", "2025"): "CAN-AER-25",
    ("canyon", "ultimate", "2026"): "CAN-ULT-26",
    ("canyon", "ultimate", "2025"): "CAN-ULT-25",
    ("canyon", "endurace", "2026"): "CAN-END-26",
    ("cervelo", "s5", "2026"): "CER-S05-26",
    ("cervelo", "s5", "2025"): "CER-S05-25",
    ("cervelo", "r5", "2026"): "CER-R05-26",
    ("cervelo", "caledonia", "2026"): "CER-CAL-26",
    ("pinarello", "dogma f", "2026"): "PIN-DOF-26",
    ("pinarello", "dogma f", "2025"): "PIN-DOF-25",
    ("pinarello", "prince", "2026"): "PIN-PRI-26",
    ("colnago", "v4rs", "2026"): "COL-V4R-26",
    ("colnago", "v4rs", "2025"): "COL-V4R-25",
    ("scott", "addict rc", "2026"): "SCO-ARC-26",
    ("scott", "addict rc", "2025"): "SCO-ARC-25",
    ("scott", "foil rc", "2026"): "SCO-FRC-26",
    ("bmc", "teammachine slr", "2026"): "BMC-TMS-26",
    ("bmc", "teammachine slr", "2025"): "BMC-TMS-25",
    ("orbea", "orca aero", "2026"): "ORB-OAR-26",
    ("orbea", "orca", "2026"): "ORB-ORC-26",
    ("factor", "one", "2026"): "FAC-ONE25",
    ("factor", "o2", "2026"): "FAC-O2-26",
}

# VelogicFit 完整 URL（含 app. subdomain）
VELOGICFIT_BASE = "https://app.velogicfit.com/frame-comparison"

genai.configure(api_key=GEMINI_API_KEY)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler       = WebhookHandler(LINE_CHANNEL_SECRET)
app           = Flask(__name__)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

conversation_history = {}
user_daily_count     = {}
DAILY_LIMIT          = 10
geo_states: dict     = {}

# 尺寸：自由輸入，不限制選項（各品牌格式不同）
SPACER_OPTIONS     = ["10", "15", "20", "25", "30", "35", "40", "45"]
STEM_LENGTH_OPTIONS = [str(x) for x in range(65, 155, 5)]  # 65-150mm 每 5mm

SYSTEM_PROMPT = '''你是 Orange Fruit 橙實設定的專業運動助理，名字叫小橙特助。請用專業但親切的口吻回答，使用台灣繁體中文。

你擅長：
- 單車 Bikefit 調整
- 運動伸展放鬆
- 騎乘肌群訓練
- 運動傷害預防

回答規則：
1. 當使用者描述不適或問題時，先簡短分析原因（3-5句即可），然後只問一個關鍵問題：
   「您目前比較想了解的是：
   A. 單車 Bikefit 調整建議
   B. 肌肉伸展與放鬆方法」

2. 根據使用者選擇 A 或 B，再進一步給建議，每次最多問 2-3 個問題。

3. 當使用者選擇 A（Bikefit）或表達想預約、想進一步評估、想知道費用時，回覆：
   「建議您前往我們的專業 Bikefit 預約頁面，填寫基本資料後我們會安排專人與您聯繫：
   https://orange-fruit-ai-bikefit.vercel.app/」

4. 回答長度適中，不要一次給太多資訊。

5. 反問時每個問題單獨一行，問題之間空一行，不使用任何符號或 Markdown。

6. 若問題與單車或運動完全無關，簡短回覆無法協助並引導回運動相關問題。

7. 絕對不要只是重複使用者說的話，要給出有意義的回應和建議。
'''

BASE_IMG_URL = "https://raw.githubusercontent.com/chenpu87/Line-bot/main/images"

IMAGE_DATABASE = {
    "#伸展放鬆": {
        "text": "🚴 騎車後的伸展非常重要！\n\n以下是背部伸展系列動作，每個動作維持 30 秒：",
        "images": [
            f"{BASE_IMG_URL}/back/stretch_back_full_back.jpg",
            f"{BASE_IMG_URL}/back/stretch_back_lower_back.jpg",
            f"{BASE_IMG_URL}/back/stretch_back_lumbar.jpg",
        ]
    },
    "#核心訓練": {
        "text": "💪 核心訓練對騎士非常重要！\n\n強健的核心肌群能提升踩踏效率、保護下背、維持良好騎姿。",
        "images": []
    },
    "#按摩球教學": {
        "text": "🎾 按摩球使用教學\n\n按摩球可以針對深層肌肉進行放鬆，特別適合處理激痛點。",
        "images": [
            f"{BASE_IMG_URL}/massage_ball/bikefit_massage_ball_1.jpg",
            f"{BASE_IMG_URL}/massage_ball/bikefit_massage_ball_2.jpg",
        ]
    },
    "#滾筒上半身": {
        "text": "🎯 滾筒放鬆上半身\n\n滾筒可以放鬆大面積肌肉，改善筋膜沾黏。",
        "images": [f"{BASE_IMG_URL}/foam_roller/form_roller_upper_body.jpg"]
    },
    "#滾筒下半身": {
        "text": "🎯 滾筒放鬆下半身\n\n大腿、小腿的肌肉放鬆能大幅改善騎乘舒適度。",
        "images": [f"{BASE_IMG_URL}/foam_roller/form_roller_bottom_body.jpg"]
    },
    "#花生球教學": {
        "text": "🥜 花生球放鬆下背部\n\n花生球特別適合脊椎兩側的肌肉放鬆，使用時請小心不要直接壓到脊椎。",
        "images": [
            f"{BASE_IMG_URL}/peanut_ball/peanut_ball_relax_pos_1.jpg",
            f"{BASE_IMG_URL}/peanut_ball/peanut_ball_relax_pos_2.jpg",
            f"{BASE_IMG_URL}/peanut_ball/peanut_ball_relax_pos_3.jpg",
        ]
    },
    "#髖關節": {
        "text": "🦵 髖關節伸展與訓練\n\n良好的髖關節活動度對騎車非常重要！",
        "images": [
            f"{BASE_IMG_URL}/hip_joint/hip_joint_training_pos_1.jpg",
            f"{BASE_IMG_URL}/hip_joint/hip_joint_training_pos_2.jpg",
            f"{BASE_IMG_URL}/hip_joint/hip_joint_training_pos_3.jpg",
        ]
    },
    "#Bikefit常識": {
        "text": "🚲 Bikefit 小常識\n\n正確的 Bikefit 能大幅提升騎乘舒適度和效率！",
        "images": [
            f"{BASE_IMG_URL}/bikefit/bikefit_saddle_fit.jpg",
            f"{BASE_IMG_URL}/bikefit/bikefit_cleat_fit.jpg",
            f"{BASE_IMG_URL}/bikefit/bikefit_the_hx_hy.jpg",
        ]
    },
    "#騎士重置": {
        "text": "🔄 騎士每日重置動作\n\n每天 5 分鐘，放鬆緊繃的肌肉，改善久坐造成的腰痠背痛！",
        "images": [
            f"{BASE_IMG_URL}/cyclist_reset/reset_warm_up_cool%20_down_1.jpg",
            f"{BASE_IMG_URL}/cyclist_reset/reset_warm_up_cool%20_down_2.jpg",
        ]
    },
}

KEYWORD_IMAGE_MAP = {
    "肩膀": [
        f"{BASE_IMG_URL}/shoulder/shoulder_upper_chest_shoulder.jpg",
        f"{BASE_IMG_URL}/shoulder/shoulder_upper_chest_back.jpg",
    ],
    "背部": [
        f"{BASE_IMG_URL}/back/stretch_back_full_back.jpg",
        f"{BASE_IMG_URL}/back/stretch_back_lower_back.jpg",
    ],
    "下背": [
        f"{BASE_IMG_URL}/back/stretch_back_lower_back.jpg",
        f"{BASE_IMG_URL}/back/stretch_back_lumbar.jpg",
    ],
    "髖關節": [f"{BASE_IMG_URL}/hip_joint/hip_joint_training_pos_1.jpg"],
    "bikefit": [f"{BASE_IMG_URL}/bikefit/bikefit_the_hx_hy.jpg"],
}

# ==========================================
# 工具函數
# ==========================================
def get_today():
    return datetime.date.today().isoformat()

def is_over_limit(user_id):
    today = get_today()
    if user_id not in user_daily_count:
        user_daily_count[user_id] = {"date": today, "count": 0}
    if user_daily_count[user_id]["date"] != today:
        user_daily_count[user_id] = {"date": today, "count": 0}
    return user_daily_count[user_id]["count"] >= DAILY_LIMIT

def add_count(user_id):
    user_daily_count[user_id]["count"] += 1

def is_service_hours():
    utc_now  = datetime.datetime.utcnow()
    tw_now   = utc_now + datetime.timedelta(hours=TZ_OFFSET)
    return SERVICE_START <= tw_now.hour < SERVICE_END

def _reply(reply_token, messages):
    try:
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(reply_token=reply_token, messages=messages)
            )
    except Exception as e:
        logger.error(f"Reply failed: {e}")

def _push(user_id, messages):
    try:
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).push_message(
                PushMessageRequest(to=user_id, messages=messages)
            )
    except Exception as e:
        logger.error(f"Push failed: {e}")

def _text(msg): return TextMessage(text=msg)
def _img(url):  return ImageMessage(original_content_url=url, preview_image_url=url)

def notify_owner(bike1: dict, bike2: dict, requester_user_id: str):
    if not NOTIFY_GROUP_ID:
        logger.warning("NOTIFY_GROUP_ID 未設定，無法發送通知")
        return
    tw_now = datetime.datetime.utcnow() + datetime.timedelta(hours=TZ_OFFSET)
    time_str = tw_now.strftime("%m/%d %H:%M")
    msg = (
        f"📐 車架對照圖需求\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ {time_str}\n"
        f"👤 User: {requester_user_id[:8]}...\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔵 Bike 1：{_bdisp(bike1)}\n"
        f"⚫ Bike 2：{_bdisp(bike2)}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"請至 BikeInsights 截圖後\n"
        f"回傳給客人 {requester_user_id[:8]}..."
    )
    _push(NOTIFY_GROUP_ID, [_text(msg)])
    logger.info(f"已通知群組：{NOTIFY_GROUP_ID}")

def handle_rich_menu_command(event, command):
    if command not in IMAGE_DATABASE:
        if command in ("#車架幾何", "#車架對照"):
            handle_geo_command(event, command)
        else:
            handle_ai_conversation(event, command)
        return
    data     = IMAGE_DATABASE[command]
    messages = [_text(data["text"])] + [_img(u) for u in data["images"]]
    _reply(event.reply_token, messages)

def handle_ai_conversation(event, user_text):
    user_id = event.source.user_id

    # 偵測疑似誤送的數值（純數字或帶 mm/°），提示重新開始
    if re.match(r"^-?\d+(\.\d+)?(mm|°|度)?$", user_text.strip()):
        _reply(event.reply_token, [_text(
            "😅 您是否要查詢車架幾何？\n\n"
            "請傳送以下指令開始：\n"
            "#車架幾何　→　計算 Bar X / Bar Y\n"
            "#車架對照　→　兩台車架幾何對照"
        )])
        return

    if is_over_limit(user_id):
        _reply(event.reply_token, [_text(
            "感謝您今日的諮詢！您今天的免費諮詢次數已用完。\n\n"
            "歡迎直接預約我們的專業 Bikefit 服務，讓教練為您進行完整評估：\n\n"
            "https://orange-fruit-ai-bikefit.vercel.app/"
        )]); return

    add_count(user_id)
    _reply(event.reply_token, [_text("🤔 小橙正在思考中...")])

    if user_id not in conversation_history:
        conversation_history[user_id] = []
    conversation_history[user_id].append({"role": "user", "parts": [user_text]})

    try:
        model      = genai.GenerativeModel(model_name='gemini-2.5-flash', system_instruction=SYSTEM_PROMPT)
        chat       = model.start_chat(history=conversation_history[user_id][:-1])
        reply_text = chat.send_message(user_text).text
        conversation_history[user_id].append({"role": "model", "parts": [reply_text]})
        if len(conversation_history[user_id]) > 20:
            conversation_history[user_id] = conversation_history[user_id][-20:]
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        reply_text = "抱歉，教練正在忙碌中，請稍後再試！"

    messages = [_text(reply_text)]
    for kw, imgs in KEYWORD_IMAGE_MAP.items():
        if kw in user_text.lower():
            messages += [_img(u) for u in imgs[:2]]; break

    _push(user_id, messages)

def handle_geo_command(event, command):
    user_id = event.source.user_id
    geo_states.pop(user_id, None)

    if command == "#車架幾何":
        geo_states[user_id] = {"mode": "velogicfit", "step": 1, "data": {}}
        _reply(event.reply_token, [_text(
            "🔢 Handlebar Position 計算\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "步驟 1／6　請輸入車架品牌\n"
            "例如：Merida、Giant、Trek、Canyon"
        )])

    elif command == "#車架對照":
        geo_states[user_id] = {"mode": "bikeinsights", "step": 1, "data": {}}
        _reply(event.reply_token, [_text(
            "📐 車架幾何對照\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "第一台車　請輸入：\n"
            "格式：品牌 車款 [年份] 尺寸\n\n"
            "範例：\n"
            "  Merida Reacto 2026 S\n"
            "  Giant TCR 2025 M\n\n"
            "（年份可省略）"
        )])

# ── VelogicFit 對話流程 ──────────────────────────────────────────────────────
def handle_velogicfit_flow(event, user_id, text):
    state = geo_states[user_id]
    step  = state["step"]
    data  = state["data"]

    if step == 1:
        data["brand"] = text; state["step"] = 2
        _reply(event.reply_token, [_text(
            f"品牌：{text} ✅\n\n步驟 2／6　請輸入車款型號\n"
            f"例如：Reacto、TCR、Madone"
        )])

    elif step == 2:
        # 若用戶把年份一起輸入（如「One 2026」），自動拆出年份
        _parts = text.strip().split()
        import re as _re
        if len(_parts) >= 2 and _re.match(r"^20\d{2}$", _parts[-1]):
            data["year"]  = _parts[-1]
            data["model"] = " ".join(_parts[:-1])
        else:
            data["model"] = text
            data.setdefault("year", "")
        state["step"] = 3
        _reply(event.reply_token, [_text(
            f"車款：{data['model']} ✅\n\n"
            f"步驟 3／6　請輸入尺寸\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"依照您的車架標示輸入即可：\n\n"
            f"英文尺寸：XXS / XS / S / M / L / XL\n"
            f"數字尺寸：47 / 50 / 52 / 54 / 56 / 58\n\n"
            f"📌 請直接輸入車架上的尺寸標示"
        )])

    elif step == 3:
        # 尺寸自由輸入：支援英文(S/M/L/XL)或數字(47/52/54/56/58)
        val = text.strip().upper()
        if not val:
            _reply(event.reply_token, [_text("❌ 請輸入尺寸")]); return
        data["size"] = val; state["step"] = 4
        _reply(event.reply_token, [_text(
            f"尺寸：{val} ✅\n\n步驟 4／6　請輸入龍頭長度（mm）\n\n"
            f"65 / 70 / 75 / 80 / 85 / 90 / 95 / 100 / 105\n"
            f"110 / 115 / 120 / 125 / 130 / 135 / 140 / 145 / 150"
        )])

    elif step == 4:
        val = text.replace("mm", "").strip()
        if val not in STEM_LENGTH_OPTIONS:
            _reply(event.reply_token, [_text(
                "❌ 請輸入有效龍頭長度（65-150mm，每 5mm）\n\n"
                "65 / 70 / 75 / 80 / 85 / 90 / 95 / 100 / 105\n"
                "110 / 115 / 120 / 125 / 130 / 135 / 140 / 145 / 150"
            )]); return
        data["stem_length"] = val; state["step"] = 5
        _reply(event.reply_token, [_text(
            f"龍頭長度：{val}mm ✅\n\n步驟 5／6　請選擇龍頭角度\n"
            f"請回覆：-6 / -8 / -10 / -12 / -17\n（不填寫預設 -8°）"
        )])

    elif step == 5:
        val = text.replace("°", "").strip()
        if not re.match(r"^-?\d+$", val): val = "-8"
        data["stem_angle"] = val; state["step"] = 6
        _reply(event.reply_token, [_text(
            f"龍頭角度：{val}° ✅\n\n步驟 6／6　請選擇墊片（Spacer）高度\n"
            f"請回覆：10 / 15 / 20 / 25 / 30 / 35 / 40 / 45（mm）"
        )])

    elif step == 6:
        val = text.replace("mm", "").strip()
        if val not in SPACER_OPTIONS:
            _reply(event.reply_token, [_text(
                "❌ 請輸入有效墊片高度：10 / 15 / 20 / 25 / 30 / 35 / 40 / 45（mm）"
            )]); return

        data["spacer"] = val
        geo_states.pop(user_id, None)

        # ★ 立即回覆確認，避免 LINE Webhook 5 秒超時
        _reply(event.reply_token, [_text(
            f"✅ 確認資料\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"品牌：{data['brand']}\n"
            f"車款：{data['model']} ({data.get('year', '')})\n"
            f"尺寸：{data['size']}\n"
            f"龍頭長度：{data['stem_length']}mm\n"
            f"龍頭角度：{data['stem_angle']}°\n"
            f"墊片高度：{data['spacer']}mm\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⏳ 計算中，請稍候約 30 秒..."
        )])

        # ★ 用背景 thread 執行 Playwright，避免佔用 webhook 回應時間
        def _run_in_background(uid, d):
            try:
                result = _run_velogicfit_api(d)
                bar_x  = result.get("bar_x", "")
                bar_y  = result.get("bar_y", "")
                link   = result.get("link", "")

                if bar_x and bar_y:
                    hx_hy_img = f"{BASE_IMG_URL}/bikefit/bikefit_the_hx_hy.jpg"
                    _push(uid, [
                        _text(
                            f"📊 Handlebar Position (HX / HY)\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"🔹 HX (Bar X) ：{bar_x} mm\n"
                            f"🔹 HY (Bar Y) ：{bar_y} mm\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"車款：{d['brand']} {d['model']} ({d['size']})\n"
                            f"龍頭：{d['stem_length']}mm ／ {d['stem_angle']}° ／ {d['spacer']}mm spacer\n\n"
                            f"輸入 #車架幾何 查詢其他車款"
                        ),
                        _img(hx_hy_img)
                    ])
                elif link:
                    hx_hy_img = f"{BASE_IMG_URL}/bikefit/bikefit_the_hx_hy.jpg"
                    _push(uid, [
                        _text(
                            f"🔗 已為您產生查詢連結\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"車款：{d['brand']} {d['model']} ({d['size']})\n"
                            f"龍頭：{d['stem_length']}mm ／ {d['stem_angle']}° ／ {d['spacer']}mm spacer\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"請點以下連結查看 HX / HY：\n\n"
                            f"{link}\n\n"
                            f"📌 開啟後請捲到「Handlebar position」區塊"
                        ),
                        _img(hx_hy_img)
                    ])
                else:
                    _push(uid, [_text(
                        f"⚠️ 找不到此車款\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"品牌：{d['brand']}\n"
                        f"車款：{d['model']}\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"請至以下網站手動搜尋：\n"
                        f"{VELOGICFIT_BASE}\n\n"
                        f"💡 提示：請確認英文拼寫正確\n"
                        f"例如：Giant TCR Advanced / Specialized Tarmac"
                    )])
            except Exception as e:
                logger.error(f"Background VelogicFit error: {e}")
                _push(uid, [_text("❌ 計算失敗，請輸入 #車架幾何 重試")])

        threading.Thread(target=_run_in_background, args=(user_id, data.copy()), daemon=True).start()

# ── BikeInsights 對話流程 ────────────────────────────────────────────────────
def handle_bikeinsights_flow(event, user_id, text):
    state = geo_states[user_id]
    step  = state["step"]
    data  = state["data"]

    if step == 1:
        parsed = _parse_bike(text)
        if not parsed:
            _reply(event.reply_token, [_text(
                "❌ 格式錯誤\n\n請輸入：品牌 車款 [年份] 尺寸\n"
                "例如：Merida Reacto 2026 S"
            )]); return
        data["bike1"] = parsed; state["step"] = 2
        _reply(event.reply_token, [_text(
            f"第一台：{_bdisp(parsed)} ✅\n\n"
            f"第二台車　請輸入：\n"
            f"格式：品牌 車款 [年份] 尺寸"
        )])

    elif step == 2:
        parsed = _parse_bike(text)
        if not parsed:
            _reply(event.reply_token, [_text(
                "❌ 格式錯誤\n\n請輸入：品牌 車款 [年份] 尺寸\n"
                "例如：Giant TCR 2025 M"
            )]); return

        data["bike2"] = parsed
        geo_states.pop(user_id, None)

        if is_service_hours():
            _reply(event.reply_token, [_text(
                f"✅ 已收到需求\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🔵 Bike 1：{_bdisp(data['bike1'])}\n"
                f"⚫ Bike 2：{_bdisp(data['bike2'])}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📸 專員正在為您製作對照圖\n"
                f"請稍候，將於服務時間內回覆！"
            )])
            notify_owner(data["bike1"], data["bike2"], user_id)
        else:
            _reply(event.reply_token, [_text(
                f"✅ 已收到您的對照需求\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🔵 Bike 1：{_bdisp(data['bike1'])}\n"
                f"⚫ Bike 2：{_bdisp(data['bike2'])}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⏰ 車架對照圖服務時間：\n"
                f"每天 09:00 - 12:00\n\n"
                f"您的需求已記錄，\n"
                f"明天服務時間開始後將為您回覆！"
            )])
            notify_owner(data["bike1"], data["bike2"], user_id)

# ==========================================
# VelogicFit：Playwright 自動抓 Bar X / Bar Y
# ==========================================
def _scrape_bar_values(url: str) -> dict:
    """
    用 Playwright 開啟 VelogicFit 頁面，等待 Handlebar position 出現後抓值。
    回傳 {"bar_x": "xxx", "bar_y": "xxx"} 或 {"error": "..."}
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.warning("Playwright 未安裝，回傳連結模式")
        return {"error": "playwright_not_installed"}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page    = browser.new_page()
            page.goto(url, timeout=30000)

            # 等待 Handlebar position 區塊渲染（最多 20 秒）
            try:
                page.wait_for_selector("text=Handlebar position", timeout=20000)
                page.wait_for_timeout(2000)  # 等數值填入
            except PWTimeout:
                browser.close()
                return {"error": "timeout_waiting_for_handlebar"}

            # 抓 Bar X / Bar Y 數值
            # VelogicFit 的結構：label 旁邊是數值 td
            bar_x = bar_y = ""
            rows = page.query_selector_all("tr")
            for row in rows:
                text = row.inner_text()
                if "Bar X" in text or "Handlebar X" in text:
                    tds = row.query_selector_all("td")
                    for td in tds:
                        val = td.inner_text().strip()
                        if re.match(r"^-?\d+\.?\d*$", val):
                            bar_x = val; break
                if "Bar Y" in text or "Handlebar Y" in text or "Stack" in text and "Handlebar" in text:
                    tds = row.query_selector_all("td")
                    for td in tds:
                        val = td.inner_text().strip()
                        if re.match(r"^-?\d+\.?\d*$", val):
                            bar_y = val; break

            # 備用：用頁面文字 parse
            if not (bar_x and bar_y):
                full_text = page.inner_text("body")
                bx = re.search(r"Bar X[^\d-]*(-?\d+\.?\d*)", full_text)
                by = re.search(r"Bar Y[^\d-]*(-?\d+\.?\d*)", full_text)
                if bx: bar_x = bx.group(1)
                if by: bar_y = by.group(1)

            browser.close()

            if bar_x and bar_y:
                return {"bar_x": bar_x, "bar_y": bar_y}
            else:
                logger.warning(f"Bar X/Y not found on page: {url}")
                return {"error": "values_not_found"}

    except Exception as e:
        logger.error(f"Playwright scrape error: {e}")
        return {"error": str(e)[:100]}


def _run_velogicfit_api(data: dict) -> dict:
    """
    1. 從對照表 / 自動生成取得 fm/fg 代碼
    2. 組出完整 URL（含 &hb=&hm=&hw=）
    3. 用 Playwright 抓 Bar X / Bar Y 數值
    回傳 {"bar_x":..., "bar_y":..., "link":...} 或 {"link":...} 或 {"link": None}
    """
    brand       = data["brand"]
    model       = data["model"]
    year        = data.get("year", "")
    size        = data["size"]
    stem_length = data["stem_length"]
    stem_angle  = data["stem_angle"]
    spacer      = data["spacer"]

    logger.info(f"VelogicFit: {brand} {model} {year} {size} sl={stem_length} sa={stem_angle} sp={spacer}")

    # 1. 查代碼對照表（完全匹配）
    key     = (brand.lower(), model.lower(), year)
    fm_code = FRAME_CODE_MAP.get(key, "")

    # 1b. 年份不符 → 找同車款最新年份
    if not fm_code and year:
        for y in ["2026", "2025", "2024", "2023"]:
            alt_key = (brand.lower(), model.lower(), y)
            if alt_key in FRAME_CODE_MAP:
                fm_code = FRAME_CODE_MAP[alt_key]
                logger.info(f"Year fallback: {year} → {y}, code={fm_code}")
                break

    # 2. 對照表找不到 → 自動生成代碼
    if not fm_code:
        year_short = year[-2:] if year and len(year) >= 2 else "26"
        fm_code = _guess_frame_code(brand, model, year_short)

    if not fm_code:
        return {"link": None}

    fg_code = f"{fm_code}-{size}"
    link = (
        f"{VELOGICFIT_BASE}"
        f"?fm={fm_code}&fg={fg_code}"
        f"&sl={stem_length}&sa={stem_angle}&sp={spacer}"
        f"&hb=&hm=&hw="
    )
    logger.info(f"Generated link: {link}")

    # 3. 用 Playwright 直接抓數值
    scraped = _scrape_bar_values(link)
    if scraped.get("bar_x") and scraped.get("bar_y"):
        return {"bar_x": scraped["bar_x"], "bar_y": scraped["bar_y"], "link": link}

    # Playwright 失敗 → 回傳連結讓客人自己點
    logger.warning(f"Scrape failed ({scraped.get('error')}), returning link only")
    return {"link": link}


def _guess_frame_code(brand: str, model: str, year_short: str) -> str:
    """嘗試自動生成 VelogicFit 車款代碼（品牌3碼-車款3碼-年份2碼）"""
    brand_map = {
        "merida": "MER", "giant": "GIA", "trek": "TRE",
        "specialized": "SPE", "canyon": "CAN", "cervelo": "CER",
        "pinarello": "PIN", "colnago": "COL", "scott": "SCO",
        "bmc": "BMC", "orbea": "ORB", "wilier": "WIL",
        "look": "LOO", "time": "TIM", "factor": "FAC",
        "cannondale": "CAN", "bianchi": "BIA", "ridley": "RID",
        "focus": "FOC", "rose": "ROS", "cube": "CUB",
    }
    brand_code  = brand_map.get(brand.lower(), brand[:3].upper())
    model_clean = re.sub(r'[^a-zA-Z0-9]', '', model).upper()
    model_code  = model_clean[:3]
    if len(model_code) < 3:
        return ""
    return f"{brand_code}-{model_code}-{year_short}"


# ==========================================
# 解析車款輸入
# ==========================================
def _parse_bike(text):
    parts = text.strip().split()
    if len(parts) < 3: return None
    size = parts[-1].upper()
    if size not in SIZE_OPTIONS: return None
    remaining = parts[:-1]; year = ""
    if remaining and re.match(r"^20\d{2}$", remaining[-1]):
        year = remaining[-1]; remaining = remaining[:-1]
    if len(remaining) < 2: return None
    return {"brand": remaining[0], "model": " ".join(remaining[1:]), "year": year, "size": size}

def _bdisp(bike):
    year = f" {bike['year']}" if bike.get("year") else ""
    return f"{bike['brand']} {bike['model']}{year} ({bike['size']})"

# ==========================================
# 路由
# ==========================================
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body      = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@app.route("/", methods=['GET'])
def home():
    return "Orange Fruit LINE Bot is running! 🍊"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = event.message.text.strip()
    user_id   = event.source.user_id
    group_id  = getattr(event.source, "group_id", None)
    app.logger.info(f"收到訊息: {user_text} | user={user_id} | group={group_id}")

    if user_id in geo_states:
        mode = geo_states[user_id].get("mode")
        if mode == "velogicfit":
            handle_velogicfit_flow(event, user_id, user_text)
        elif mode == "bikeinsights":
            handle_bikeinsights_flow(event, user_id, user_text)
        return

    if user_text.startswith('#'):
        handle_rich_menu_command(event, user_text)
    else:
        handle_ai_conversation(event, user_text)

# ==========================================
# 啟動
# ==========================================
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
