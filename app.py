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
import google.generativeai as genai
from flask import Flask, request, abort, send_file
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
NOTIFY_GROUP_ID           = os.getenv('NOTIFY_GROUP_ID', '')   # C 開頭的群組 ID
OWNER_USER_ID             = os.getenv('OWNER_USER_ID', '')     # U 開頭的你的 User ID

# 服務時間：台灣時間 09:00 - 12:00
SERVICE_START = 9
SERVICE_END   = 12
TZ_OFFSET     = 8   # UTC+8

# ==========================================
# VelogicFit 車款代碼對照表
# 格式：fm=品牌-車款-年份, fg=fm-尺寸
# 規律：MER-REA-26 = Merida Reacto 2026
# ==========================================
FRAME_CODE_MAP = {
    # Merida
    ("merida", "reacto", "2026"): "MER-REA-26",
    ("merida", "reacto", "2025"): "MER-REA-25",
    ("merida", "reacto", "2024"): "MER-REA-24",
    ("merida", "reacto", "2023"): "MER-REA-23",
    ("merida", "scultura", "2026"): "MER-SCU-26",
    ("merida", "scultura", "2025"): "MER-SCU-25",
    ("merida", "scultura", "2024"): "MER-SCU-24",
    ("merida", "scultura team", "2026"): "MER-SCT-26",
    ("merida", "mission cx", "2026"): "MER-MCX-26",
    # Giant
    ("giant", "tcr advanced", "2026"): "GIA-TCR-26",
    ("giant", "tcr advanced", "2025"): "GIA-TCR-25",
    ("giant", "tcr advanced", "2024"): "GIA-TCR-24",
    ("giant", "tcr advanced sl", "2026"): "GIA-TCS-26",
    ("giant", "propel advanced", "2026"): "GIA-PRO-26",
    ("giant", "propel advanced", "2025"): "GIA-PRO-25",
    ("giant", "defy advanced", "2026"): "GIA-DEF-26",
    ("giant", "defy advanced", "2025"): "GIA-DEF-25",
    # Trek
    ("trek", "madone slr", "2026"): "TRE-MAS-26",
    ("trek", "madone slr", "2025"): "TRE-MAS-25",
    ("trek", "emonda slr", "2026"): "TRE-EMS-26",
    ("trek", "emonda slr", "2025"): "TRE-EMS-25",
    ("trek", "domane slr", "2026"): "TRE-DOS-26",
    ("trek", "domane slr", "2025"): "TRE-DOS-25",
    # Specialized
    ("specialized", "tarmac sl8", "2026"): "SPE-TS8-26",
    ("specialized", "tarmac sl8", "2025"): "SPE-TS8-25",
    ("specialized", "venge", "2024"): "SPE-VEN-24",
    ("specialized", "aethos", "2026"): "SPE-AET-26",
    # Canyon
    ("canyon", "aeroad", "2026"): "CAN-AER-26",
    ("canyon", "aeroad", "2025"): "CAN-AER-25",
    ("canyon", "ultimate", "2026"): "CAN-ULT-26",
    ("canyon", "ultimate", "2025"): "CAN-ULT-25",
    ("canyon", "endurace", "2026"): "CAN-END-26",
    # Cervélo
    ("cervelo", "s5", "2026"): "CER-S05-26",
    ("cervelo", "s5", "2025"): "CER-S05-25",
    ("cervelo", "r5", "2026"): "CER-R05-26",
    ("cervelo", "caledonia", "2026"): "CER-CAL-26",
    # Pinarello
    ("pinarello", "dogma f", "2026"): "PIN-DOF-26",
    ("pinarello", "dogma f", "2025"): "PIN-DOF-25",
    ("pinarello", "prince", "2026"): "PIN-PRI-26",
    # Colnago
    ("colnago", "v4rs", "2026"): "COL-V4R-26",
    ("colnago", "v4rs", "2025"): "COL-V4R-25",
    # Scott
    ("scott", "addict rc", "2026"): "SCO-ARC-26",
    ("scott", "addict rc", "2025"): "SCO-ARC-25",
    ("scott", "foil rc", "2026"): "SCO-FRC-26",
    # BMC
    ("bmc", "teammachine slr", "2026"): "BMC-TMS-26",
    ("bmc", "teammachine slr", "2025"): "BMC-TMS-25",
    # Orbea
    ("orbea", "orca aero", "2026"): "ORB-OAR-26",
    ("orbea", "orca", "2026"): "ORB-ORC-26",
    # Factor
    
    ("factor", "One", "2026"): "FAC-ONE25",
    ("factor", "O2", "2026"): "FAC-O2-26",

}

# ==========================================
# 初始化
# ==========================================
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

SIZE_OPTIONS   = ["XXS", "XS", "S", "M", "L", "XL"]
SPACER_OPTIONS = ["10", "15", "20", "25", "30", "35", "40", "45"]

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
    """判斷目前是否在服務時間（台灣時間 09:00-12:00）"""
    utc_now  = datetime.datetime.utcnow()
    tw_now   = utc_now + datetime.timedelta(hours=TZ_OFFSET)
    return SERVICE_START <= tw_now.hour < SERVICE_END

def _reply(reply_token, messages):
    """回覆訊息"""
    try:
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(reply_token=reply_token, messages=messages)
            )
    except Exception as e:
        logger.error(f"Reply failed: {e}")

def _push(user_id, messages):
    """推播訊息給指定用戶或群組"""
    try:
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).push_message(
                PushMessageRequest(to=user_id, messages=messages)
            )
    except Exception as e:
        logger.error(f"Push failed: {e}")

def _text(msg): return TextMessage(text=msg)
def _img(url):  return ImageMessage(original_content_url=url, preview_image_url=url)

# ==========================================
# 通知老闆（推播到群組）
# ==========================================
def notify_owner(bike1: dict, bike2: dict, requester_user_id: str):
    """有客人需要車架對照圖時，通知老闆群組"""
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

# ==========================================
# 原有功能：Rich Menu & AI 對話
# ==========================================
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
    if is_over_limit(user_id):
        _reply(event.reply_token, [_text(
            "感謝您今日的諮詢！您今天的免費諮詢次數已用完。\n\n"
            "歡迎直接預約我們的專業 Bikefit 服務，讓教練為您進行完整評估：\n\n"
            "https://orange-fruit-ai-bikefit.vercel.app/"
        )]); return

    add_count(user_id)

    # 先立即 reply「思考中」避免 token 過期
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

    # 用 push 發送實際回覆
    _push(user_id, messages)

# ==========================================
# 新功能：車架幾何
# ==========================================
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
        data["model"] = text; state["step"] = 3
        _reply(event.reply_token, [_text(
            f"車款：{text} ✅\n\n步驟 3／6　請選擇尺寸\n"
            f"請回覆：XXS / XS / S / M / L / XL"
        )])

    elif step == 3:
        val = text.upper()
        if val not in SIZE_OPTIONS:
            _reply(event.reply_token, [_text("❌ 請輸入有效尺寸：XXS / XS / S / M / L / XL")]); return
        data["size"] = val; state["step"] = 4
        _reply(event.reply_token, [_text(
            f"尺寸：{val} ✅\n\n步驟 4／6　請輸入龍頭長度（mm）\n"
            f"常見：80 / 90 / 100 / 110 / 120"
        )])

    elif step == 4:
        val = text.replace("mm", "").strip()
        if not re.match(r"^\d{2,3}$", val):
            _reply(event.reply_token, [_text("❌ 請輸入數字（例如：100）")]); return
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
            f"⏳ 計算中，請稍候..."
        )])

        result = _run_velogicfit_api(data)

        bar_x = result.get("bar_x", "")
        bar_y = result.get("bar_y", "")
        link  = result.get("link", "")

        if bar_x and bar_y:
            # 成功取得數值
            _push(user_id, [_text(
                f"📊 Handlebar Position\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🔹 Bar X ：{bar_x} mm\n"
                f"🔹 Bar Y ：{bar_y} mm\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"車款：{data['brand']} {data['model']} ({data['size']})\n"
                f"龍頭：{data['stem_length']}mm ／ {data['stem_angle']}° ／ {data['spacer']}mm spacer\n\n"
                f"輸入 #車架幾何 查詢其他車款"
            )])
        elif link:
            # 有連結但沒有數值，讓客人自己點
            _push(user_id, [_text(
                f"🔗 已為您產生查詢連結\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"車款：{data['brand']} {data['model']} ({data['size']})\n"
                f"龍頭：{data['stem_length']}mm ／ {data['stem_angle']}° ／ {data['spacer']}mm spacer\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"請點以下連結查看 Bar X / Bar Y：\n\n"
                f"{link}\n\n"
                f"📌 開啟後請捲到「Handlebar position」區塊"
            )])
        else:
            # 找不到車款，給 VelogicFit 搜索連結
            search_link = (
                f"https://app.velogicfit.com/frame-comparison"
            )
            _push(user_id, [_text(
                f"⚠️ 找不到此車款\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"品牌：{data['brand']}\n"
                f"車款：{data['model']}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"請至以下網站手動搜尋：\n"
                f"{search_link}\n\n"
                f"💡 提示：請確認英文拼寫正確\n"
                f"例如：Giant TCR Advanced / Specialized Tarmac"
            )])

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

        # 判斷是否在服務時間
        if is_service_hours():
            # 服務時間內：直接告知並通知老闆
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
            # 非服務時間：告知時間並通知老闆
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
# VelogicFit：產生查詢連結 + 嘗試 API
# ==========================================
def _run_velogicfit_api(data: dict) -> dict:
    """
    直接呼叫 VelogicFit 的 API 取得 Bar X / Bar Y
    URL 格式：?fm=<model>&fg=<frame>&sl=<stem_len>&sa=<stem_angle>&sp=<spacer>
    """
    brand       = data["brand"]
    model       = data["model"]
    year        = data.get("year", "")
    size        = data["size"]
    stem_length = data["stem_length"]
    stem_angle  = data["stem_angle"]
    spacer      = data["spacer"]

    logger.info(f"VelogicFit: {brand} {model} {year} {size} sl={stem_length} sa={stem_angle} sp={spacer}")

    # VelogicFit 使用 Blazor + SignalR，無法直接用 requests 取得數值
    # 從代碼對照表找到 fm/fg 代碼，直接產生帶參數的連結

    # 1. 先查對照表（完全匹配）
    year_short = year[-2:] if year and len(year) >= 2 else ""
    key = (brand.lower(), model.lower(), year)
    fm_code = FRAME_CODE_MAP.get(key, "")

    # 2. 對照表找不到，嘗試自動生成代碼
    if not fm_code and year_short:
        fm_code = _guess_frame_code(brand, model, year_short)

    if fm_code:
        fg_code = f"{fm_code}-{size}"
        link = (
            f"https://app.velogicfit.com/frame-comparison"
            f"?fm={fm_code}&fg={fg_code}"
            f"&sl={stem_length}&sa={stem_angle}&sp={spacer}"
        )
        logger.info(f"Generated link: {link}")
        return {"link": link, "fm": fm_code, "fg": fg_code}

    # 3. 完全找不到，回傳空
    return {"link": None}


def _guess_frame_code(brand: str, model: str, year_short: str) -> str:
    """
    嘗試自動生成 VelogicFit 車款代碼
    規律：品牌3碼-車款3碼-年份2碼
    例如：Merida Reacto 2026 → MER-REA-26
    """
    brand_map = {
        "merida": "MER", "giant": "GIA", "trek": "TRE",
        "specialized": "SPE", "canyon": "CAN", "cervelo": "CER",
        "pinarello": "PIN", "colnago": "COL", "scott": "SCO",
        "bmc": "BMC", "orbea": "ORB", "wilier": "WIL",
        "look": "LOO", "time": "TIM", "factor": "FAC",
        "cannondale": "CAN", "bianchi": "BIA", "ridley": "RID",
        "focus": "FOC", "rose": "ROS", "cube": "CUB",
    }
    brand_code = brand_map.get(brand.lower(), brand[:3].upper())

    # 車款名取前3個字母（去掉空格和特殊字符）
    model_clean = re.sub(r'[^a-zA-Z0-9]', '', model).upper()
    model_code  = model_clean[:3]

    if len(model_code) < 3:
        return ""

    return f"{brand_code}-{model_code}-{year_short}"


def _velogicfit_url_method(data: dict) -> dict:
    """
    備用方式：直接 GET 頁面 HTML 並 parse Bar X / Bar Y
    （模擬已知 URL 格式 ?fm=MER-REA-26&fg=MER-REA-26-S&sl=100&sa=-8&sp=20）
    """
    brand       = data["brand"]
    model       = data["model"]
    size        = data["size"]
    stem_length = data["stem_length"]
    stem_angle  = data["stem_angle"]
    spacer      = data["spacer"]

    try:
        # 先搜索取得正確的 frame code
        search_url = "https://app.velogicfit.com/api/frames"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://app.velogicfit.com/frame-comparison"
        }

        resp = requests.get(
            search_url,
            params={"search": f"{brand} {model}", "page": 1, "pageSize": 5},
            headers=headers,
            timeout=15
        )
        logger.info(f"Frame search status: {resp.status_code}")
        logger.info(f"Frame search response: {resp.text[:500]}")

        if resp.status_code == 200:
            data_json = resp.json()
            # 嘗試各種可能的 response 格式
            items = (
                data_json if isinstance(data_json, list)
                else data_json.get("data", data_json.get("items", data_json.get("frames", [])))
            )

            if items:
                first = items[0]
                fm    = first.get("modelCode") or first.get("code") or first.get("id") or ""
                geos  = first.get("geometries") or first.get("frameGeometries") or []

                fg = ""
                for g in geos:
                    s = g.get("size") or g.get("sizeName") or ""
                    if s.upper() == size.upper():
                        fg = g.get("code") or g.get("id") or ""
                        break
                if not fg and geos:
                    fg = geos[0].get("code") or geos[0].get("id") or ""

                if fm and fg:
                    return _fetch_bar_values(fm, fg, stem_length, stem_angle, spacer, headers)

        return {"error": "無法取得車款資料，請確認品牌與車款名稱是否正確"}

    except Exception as e:
        logger.error(f"URL method failed: {e}")
        return {"error": str(e)[:150]}


def _fetch_bar_values(fm, fg, sl, sa, sp, headers) -> dict:
    """用已知的 frame code 取得 Bar X/Y"""
    try:
        url = "https://app.velogicfit.com/api/frame/position"
        resp = requests.get(
            url,
            params={"fm": fm, "fg": fg, "sl": sl, "sa": sa, "sp": sp},
            headers=headers,
            timeout=15
        )
        logger.info(f"Position API status: {resp.status_code}, body: {resp.text[:300]}")

        if resp.status_code == 200:
            r    = resp.json()
            barx = str(r.get("barX") or r.get("bar_x") or r.get("Bar X") or "")
            bary = str(r.get("barY") or r.get("bar_y") or r.get("Bar Y") or "")
            if barx and bary:
                return {"bar_x": barx, "bar_y": bary}

        return {"error": "計算結果取得失敗，請稍後再試"}

    except Exception as e:
        return {"error": str(e)[:150]}


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

    # 車架幾何流程進行中 → 優先處理
    if user_id in geo_states:
        mode = geo_states[user_id].get("mode")
        if mode == "velogicfit":
            handle_velogicfit_flow(event, user_id, user_text)
        elif mode == "bikeinsights":
            handle_bikeinsights_flow(event, user_id, user_text)
        return

    # 一般指令 or AI 對話
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
