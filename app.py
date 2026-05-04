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
from playwright.sync_api import sync_playwright

# ==========================================
# 環境變數
# ==========================================
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET       = os.getenv('LINE_CHANNEL_SECRET')
GEMINI_API_KEY            = os.getenv('GEMINI_API_KEY')
IMGUR_CLIENT_ID           = os.getenv('IMGUR_CLIENT_ID', '')
BASE_URL                  = os.getenv('BASE_URL', '')

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
_image_cache: dict   = {}

SIZE_OPTIONS   = ["XXS", "XS", "S", "M", "L", "XL"]
SPACER_OPTIONS = ["10", "15", "20", "25", "30", "35", "40", "45"]
STEM_ANGLES    = ["-6", "-8", "-10", "-12", "-17"]

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
def get_today(): return datetime.date.today().isoformat()

def is_over_limit(user_id):
    today = get_today()
    if user_id not in user_daily_count:
        user_daily_count[user_id] = {"date": today, "count": 0}
    if user_daily_count[user_id]["date"] != today:
        user_daily_count[user_id] = {"date": today, "count": 0}
    return user_daily_count[user_id]["count"] >= DAILY_LIMIT

def add_count(user_id): user_daily_count[user_id]["count"] += 1

def _reply(reply_token, messages):
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=messages))

def _push(user_id, messages):
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).push_message(
            PushMessageRequest(to=user_id, messages=messages))

def _text(msg): return TextMessage(text=msg)
def _img(url):  return ImageMessage(original_content_url=url, preview_image_url=url)

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
    data = IMAGE_DATABASE[command]
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
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    conversation_history[user_id].append({"role": "user", "parts": [user_text]})
    try:
        model = genai.GenerativeModel(model_name='gemini-2.5-flash', system_instruction=SYSTEM_PROMPT)
        chat  = model.start_chat(history=conversation_history[user_id][:-1])
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
    _reply(event.reply_token, messages)

# ==========================================
# 新增功能：車架幾何
# ==========================================
def handle_geo_command(event, command):
    user_id = event.source.user_id
    geo_states.pop(user_id, None)
    if command == "#車架幾何":
        geo_states[user_id] = {"mode": "velogicfit", "step": 1, "data": {}}
        _reply(event.reply_token, [_text(
            "🔢 Handlebar Position 計算\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "步驟 1／6　請輸入車架品牌\n"
            "例如：Merida、Giant、Trek、Canyon"
        )])
    elif command == "#車架對照":
        geo_states[user_id] = {"mode": "bikeinsights", "step": 1, "data": {}}
        _reply(event.reply_token, [_text(
            "📐 車架幾何對照\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "第一台車　請輸入：\n格式：品牌 車款 [年份] 尺寸\n\n"
            "範例：\n  Merida Reacto 2026 S\n  Giant TCR 2025 M\n\n（年份可省略）"
        )])

def handle_velogicfit_flow(event, user_id, text):
    state = geo_states[user_id]; step = state["step"]; data = state["data"]

    if step == 1:
        data["brand"] = text; state["step"] = 2
        _reply(event.reply_token, [_text(f"品牌：{text} ✅\n\n步驟 2／6　請輸入車款型號\n例如：Reacto、TCR、Madone")])

    elif step == 2:
        data["model"] = text; state["step"] = 3
        _reply(event.reply_token, [_text(f"車款：{text} ✅\n\n步驟 3／6　請選擇尺寸\n請回覆：XXS / XS / S / M / L / XL")])

    elif step == 3:
        val = text.upper()
        if val not in SIZE_OPTIONS:
            _reply(event.reply_token, [_text("❌ 請輸入有效尺寸：XXS / XS / S / M / L / XL")]); return
        data["size"] = val; state["step"] = 4
        _reply(event.reply_token, [_text(f"尺寸：{val} ✅\n\n步驟 4／6　請輸入龍頭長度（mm）\n常見：80 / 90 / 100 / 110 / 120")])

    elif step == 4:
        val = text.replace("mm", "").strip()
        if not re.match(r"^\d{2,3}$", val):
            _reply(event.reply_token, [_text("❌ 請輸入數字（例如：100）")]); return
        data["stem_length"] = val; state["step"] = 5
        _reply(event.reply_token, [_text(
            f"龍頭長度：{val}mm ✅\n\n步驟 5／6　請選擇龍頭角度\n請回覆：-6 / -8 / -10 / -12 / -17\n（不填寫預設 -8°）"
        )])

    elif step == 5:
        val = text.replace("°", "").strip()
        if not re.match(r"^-?\d+$", val): val = "-8"
        data["stem_angle"] = val; state["step"] = 6
        _reply(event.reply_token, [_text(
            f"龍頭角度：{val}° ✅\n\n步驟 6／6　請選擇墊片（Spacer）高度\n請回覆：10 / 15 / 20 / 25 / 30 / 35 / 40 / 45（mm）"
        )])

    elif step == 6:
        val = text.replace("mm", "").strip()
        if val not in SPACER_OPTIONS:
            _reply(event.reply_token, [_text("❌ 請輸入有效墊片高度：10 / 15 / 20 / 25 / 30 / 35 / 40 / 45（mm）")]); return
        data["spacer"] = val
        geo_states.pop(user_id, None)
        _reply(event.reply_token, [_text(
            f"✅ 確認資料\n━━━━━━━━━━━━━━━━━━━━\n"
            f"品牌：{data['brand']}\n車款：{data['model']}\n尺寸：{data['size']}\n"
            f"龍頭長度：{data['stem_length']}mm\n龍頭角度：{data['stem_angle']}°\n墊片高度：{data['spacer']}mm\n"
            f"━━━━━━━━━━━━━━━━━━━━\n⏳ 計算中，請稍候（約 15 秒）..."
        )])
        result = _run_velogicfit(data)
        if result.get("error"):
            _push(user_id, [_text(f"❌ 查詢失敗\n{result['error']}\n\n輸入 #車架幾何 重試")])
        else:
            _push(user_id, [_text(
                f"📊 Handlebar Position\n━━━━━━━━━━━━━━━━━━━━\n"
                f"🔹 Bar X ：{result['bar_x']} mm\n🔹 Bar Y ：{result['bar_y']} mm\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"車款：{data['brand']} {data['model']} ({data['size']})\n"
                f"龍頭：{data['stem_length']}mm ／ {data['stem_angle']}° ／ {data['spacer']}mm spacer\n\n"
                f"輸入 #車架幾何 查詢其他車款"
            )])

def handle_bikeinsights_flow(event, user_id, text):
    state = geo_states[user_id]; step = state["step"]; data = state["data"]

    if step == 1:
        parsed = _parse_bike(text)
        if not parsed:
            _reply(event.reply_token, [_text("❌ 格式錯誤\n\n請輸入：品牌 車款 [年份] 尺寸\n例如：Merida Reacto 2026 S")]); return
        data["bike1"] = parsed; state["step"] = 2
        _reply(event.reply_token, [_text(
            f"第一台：{_bdisp(parsed)} ✅\n\n第二台車　請輸入：\n格式：品牌 車款 [年份] 尺寸"
        )])

    elif step == 2:
        parsed = _parse_bike(text)
        if not parsed:
            _reply(event.reply_token, [_text("❌ 格式錯誤\n\n請輸入：品牌 車款 [年份] 尺寸\n例如：Giant TCR 2025 M")]); return
        data["bike2"] = parsed
        geo_states.pop(user_id, None)
        _reply(event.reply_token, [_text(
            f"✅ 確認資料\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🔵 Bike 1：{_bdisp(data['bike1'])}\n⚫ Bike 2：{_bdisp(data['bike2'])}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n⏳ 生成對照圖中（約 20 秒）..."
        )])
        result = _run_bikeinsights(data["bike1"], data["bike2"], user_id)
        if result.get("error"):
            _push(user_id, [_text(f"❌ 對照圖生成失敗\n{result['error']}\n\n輸入 #車架對照 重試")])
        else:
            url = result.get("image_url", "")
            msgs = ([_img(url)] if url else []) + [_text(
                f"📐 車架幾何對照完成\n━━━━━━━━━━━━━━━━━━━━\n"
                f"🔵 {_bdisp(data['bike1'])}\n⚫ {_bdisp(data['bike2'])}\n\n輸入 #車架對照 再次查詢"
            )]
            _push(user_id, msgs)

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
# Playwright：VelogicFit
# ==========================================
def _run_velogicfit(data):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page    = browser.new_page(viewport={"width": 1920, "height": 1080})
            page.goto("https://app.velogicfit.com/frame-comparison", timeout=60000)
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(2000)
            search = page.locator("input.sf-dropdown-input").first
            search.click()
            search.fill(f"{data['brand']} {data['model']}")
            page.wait_for_timeout(2000)
            sug = page.locator("li.e-list-item").first
            if sug.is_visible(): sug.click()
            else: search.press("Enter")
            page.wait_for_timeout(1500)
            _set_combo(page, 0, data["size"]); page.wait_for_timeout(800)
            _set_combo(page, 1, f"{data['stem_length']}mm"); page.wait_for_timeout(500)
            _set_combo(page, 2, f"{data['stem_angle']}°"); page.wait_for_timeout(500)
            _set_combo(page, 3, f"{data['spacer']}mm"); page.wait_for_timeout(2000)
            bar_x, bar_y = _extract_bars(page)
            browser.close()
            if not bar_x or not bar_y:
                return {"error": "找不到 Bar X / Bar Y，請確認車款及尺寸"}
            return {"bar_x": bar_x, "bar_y": bar_y}
    except Exception as e:
        logger.error(f"VelogicFit error: {e}", exc_info=True)
        return {"error": str(e)[:200]}

def _set_combo(page, index, value):
    try:
        inp = page.locator('[role="combobox"]').nth(index).locator("input").first
        inp.click(); inp.fill(value); page.wait_for_timeout(400)
        item = page.locator("li.e-list-item").first
        if item.is_visible(): item.click()
        else: inp.press("Enter")
    except Exception as e:
        logger.warning(f"Combo {index} failed: {e}")

def _extract_bars(page):
    try:
        r = page.evaluate("""() => {
            const out = {};
            Array.from(document.querySelectorAll('td'))
                 .filter(td => ['Bar X','Bar Y'].includes(td.textContent.trim()))
                 .forEach(td => {
                     const vals = Array.from(td.closest('tr').querySelectorAll('td'))
                                      .slice(1).map(c=>c.textContent.trim())
                                      .filter(t=>/^\\d+$/.test(t));
                     if (vals.length) out[td.textContent.trim()] = vals[0];
                 });
            return out;
        }""")
        return r.get("Bar X",""), r.get("Bar Y","")
    except: return "", ""

# ==========================================
# Playwright：BikeInsights
# ==========================================
def _run_bikeinsights(bike1, bike2, user_id):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page    = browser.new_page(viewport={"width": 1200, "height": 780})
            page.goto("https://bikeinsights.com/compare", timeout=60000)
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(2000)
            if not _bi_pick(page, bike1):
                browser.close(); return {"error": f"找不到 {_bdisp(bike1)}"}
            page.wait_for_timeout(2000)
            if not _bi_pick(page, bike2):
                browser.close(); return {"error": f"找不到 {_bdisp(bike2)}"}
            page.wait_for_timeout(3000)
            img_path = _bi_screenshot(page, user_id)
            browser.close()
            if not img_path: return {"error": "截圖失敗"}
            return {"image_url": _upload_image(img_path), "image_path": img_path}
    except Exception as e:
        logger.error(f"BikeInsights error: {e}", exc_info=True)
        return {"error": str(e)[:200]}

def _bi_pick(page, bike):
    page.evaluate("""() => {
        const b = Array.from(document.querySelectorAll('button'))
                       .find(b => b.textContent.trim().includes('Choose Bike'));
        if (b) b.click();
    }""")
    page.wait_for_timeout(1500)
    search = page.locator('input[placeholder="Search bikes"]')
    search.click(); search.fill(f"{bike['brand']} {bike['model']}"); page.wait_for_timeout(500)
    try: page.locator('button:has(svg)').last.click()
    except: search.press("Enter")
    page.wait_for_timeout(2500)
    anchors = page.locator("a"); year = bike.get("year",""); size = bike["size"]
    for i in range(anchors.count()):
        try:
            a = anchors.nth(i)
            if a.inner_text(timeout=300).strip() != size: continue
            if year:
                if year not in a.evaluate("el => el.closest('div')?.textContent || ''"): continue
            a.click(); page.wait_for_timeout(2000)
            if "geometries=" in page.url: return True
        except: continue
    for i in range(anchors.count()):
        try:
            a = anchors.nth(i)
            if a.inner_text(timeout=300).strip() == size:
                a.click(); page.wait_for_timeout(2000)
                return "geometries=" in page.url
        except: continue
    return False

def _bi_screenshot(page, user_id):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png", prefix=f"bi_{user_id}_")
    path = tmp.name; tmp.close()
    try:
        s = page.locator("text=BIKE-ON-BIKE").locator("xpath=ancestor::div[3]").first
        if s.is_visible(): s.screenshot(path=path); _image_cache[os.path.basename(path)] = path; return path
    except: pass
    page.screenshot(path=path, clip={"x": 280, "y": 0, "width": 760, "height": 430})
    _image_cache[os.path.basename(path)] = path; return path

def _upload_image(image_path):
    if IMGUR_CLIENT_ID:
        try:
            with open(image_path,"rb") as f: img_b64 = base64.b64encode(f.read()).decode()
            data = urllib.parse.urlencode({"image": img_b64, "type":"base64"}).encode()
            req  = urllib.request.Request("https://api.imgur.com/3/image", data=data,
                                          headers={"Authorization": f"Client-ID {IMGUR_CLIENT_ID}"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())["data"]["link"].replace("http://","https://")
        except Exception as e: logger.error(f"Imgur upload failed: {e}")
    if BASE_URL:
        fname = os.path.basename(image_path); _image_cache[fname] = image_path
        return f"{BASE_URL.rstrip('/')}/img/{fname}"
    return ""

# ==========================================
# 路由
# ==========================================
@app.route("/img/<filename>")
def serve_image(filename):
    path = _image_cache.get(filename)
    if not path or not os.path.exists(path): abort(404)
    return send_file(path, mimetype="image/png")

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body      = request.get_data(as_text=True)
    try: handler.handle(body, signature)
    except InvalidSignatureError: abort(400)
    return 'OK'

@app.route("/", methods=['GET'])
def home(): return "Orange Fruit LINE Bot is running! 🍊"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = event.message.text.strip()
    user_id   = event.source.user_id
    app.logger.info(f"收到訊息: {user_text} from {user_id}")

    # 車架幾何流程進行中 → 優先處理
    if user_id in geo_states:
        mode = geo_states[user_id].get("mode")
        if mode == "velogicfit":   handle_velogicfit_flow(event, user_id, user_text)
        elif mode == "bikeinsights": handle_bikeinsights_flow(event, user_id, user_text)
        return

    # 一般指令 or AI 對話
    if user_text.startswith('#'): handle_rich_menu_command(event, user_text)
    else: handle_ai_conversation(event, user_text)

# ==========================================
# 啟動
# ==========================================
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
