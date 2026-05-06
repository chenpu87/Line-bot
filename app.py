# ==========================================
# LINE Bot with Gemini AI + Image Support
# Orange Fruit 小橙特助 - 完整整合版
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

# Playwright 不在 Render 免費方案使用
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

# 保留你的完整車架代碼對照表
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
    ("colnago", "V1RS",): "COL-Y1RS-26",
    ("scott", "addict rc", "2026"): "SCO-ARC-26",
    ("scott", "addict rc", "2025"): "SCO-ARC-25",
    ("scott", "foil rc", "2026"): "SCO-FRC-26",
    ("bmc", "teammachine slr", "2026"): "BMC-TMS-26",
    ("bmc", "teammachine slr", "2025"): "BMC-TMS-25",
    ("orbea", "orca aero", "2026"): "ORB-OAR-26",
    ("orbea", "orca", "2026"): "ORB-ORC-26",
    ("factor", "one", "2026"): "FAC-ONE25",
    ("factor", "one",): "FAC-ONE-25",
    ("factor", "o2", "2026"): "FAC-O2-26",
    ("factor", "o2 VAM", "2026"): "FAC-O2-VAM-26",
    ("factor", "ostro vam", "2026"): "FAC-OSTRVAM-26",
    ("factor", "ostro vam", ): "FAC-OST-VAM",
    ("ridley", "Noah 3.0",): "RID-NOA-30",
    ("ridley", "Noah 3.0", "fast"): "RID-NOA-FAS30",
    ("ridley", "Noah Fast","2025"): "RID-NOA-FAS30",
    ("ridley", "Noah Fast","2026"): "RID-NOA-FAS30",
    ("ridley", "falcn rs", "2026"): "RID-FRS-26",
    ("ridley", "falcn rs", "2025"): "RID-FRS-25",
    ("ridley", "falcn rs", "2024"): "RID-FRS-24",
    ("ridley", "astr rs", "2026"): "RID-ARS-26",
    ("ridley", "astr rs", "2025"): "RID-ARS-25",
    ("ridley", "noah fast", "2026"): "RID-NOF-26",
    ("ridley", "noah fast", "2025"): "RID-NOF-25",
    ("ridley", "helium slx", "2026"): "RID-HSL-26",
    ("ridley", "helium slx", "2025"): "RID-HSL-25",
    ("ridley", "kanzo fast", "2026"): "RID-KZF-26",
    ("wilier", "0 slr", ): "WIL-WIL-024",
    ("wilier", "0 slr", "2025"): "WIL-WIL-024",
    ("wilier", "0slr",): "WIL-WIL-024",
    ("wilier", "filante ID2", "2026"): "WIL-FIL-ID2-26",
    ("wilier", "filante slr", "2025"): "WIL-FIL-SLR25",
    ("wilier", "garda", "2026"): "WIL-GAR-26",
    ("wilier", "garda", "2025"): "WIL-GAR-25",
    ("wilier", "cento10 sl", "2026"): "WIL-CSL-26",
    ("wilier", "cento10 sl", "2025"): "WIL-CSL-25",
    ("wilier", "cento10 sl", "2024"): "WIL-CSL-24",
    ("wilier", "cento10 pro", "2026"): "WIL-CPR-26",
    ("wilier", "cento10 pro", "2025"): "WIL-CPR-25",
    ("wilier", "rave slr", "2026"): "WIL-RSL-26",
    ("wilier", "rave slr", "2025"): "WIL-RSL-25",
    ("time", "fluidity", "2026"): "TIM-FLUID-25",
    ("time", "fluidity", "2025"): "TIM-FLUID-25",
    ("time", "fluidity",  ): "TIM-FLUID-25",
    ("time", "fluidity","Disc"): "TIM-FLUID-25",
    ("time", "scylon", "2026"): "TIM-SCY25",
    ("time", "scylon", "2025"): "TIM-SCY25",
    ("time", "scylon", "2026"): "TIM-SCY25",
    ("time", "scylon", "2025"): "TIM-SCY25",
    ("time", "alpe d'huez", "2026"): "TIM-ALP-DHUDI",
    ("time", "alpe d'huez", "2025"): "TIM-ALP-DHUDI",
    ("time", "alpe dhuez", "2026"): "TIM-ALP-DHUDI6",
    ("no.22", "drifter", "2026"): "N22-DRI-26",
    ("no.22", "drifter", "2025"): "N22-DRI-25",
    ("no.22", "reactor", "2026"): "N22-REA-26",
    ("no.22", "reactor", "2025"): "N22-REA-25",
    ("no.22", "broken top", "2026"): "N22-BKT-26",
    ("no.22", "broken top", "2025"): "N22-BKT-25",
    ("no22", "drifter", "2026"): "N22-DRI-26",
    ("no22", "reactor", "2026"): "N22-REA-26",
}

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

SPACER_OPTIONS      = ["10", "15", "20", "25", "30", "35", "40", "45"]
SIZE_OPTIONS        = ["XXS", "XS", "S", "M", "L", "XL", "3XS", "2XS", "XS/S", "S/M", "M/L",
                       "44", "46", "47", "48", "49", "50", "51", "52", "53", "54", "55",
                       "56", "57", "58", "59", "60", "61", "62"]
STEM_LENGTH_OPTIONS = [str(x) for x in range(65, 155, 5)]

# ==========================================
# 升級版 SYSTEM_PROMPT：整合 Bikefit 專業知識
# ==========================================
SYSTEM_PROMPT = '''你是 Orange Fruit 橙實設定的專業運動助理，名字叫小橙特助。請用專業但親切的口吻回答，使用台灣繁體中文。

你擅長：
- 單車 Bikefit 調整
- Saddle Fit（坐墊適配）專業知識
- 單車幾何分析（HX、HY、Stack、Reach 等參數）
- 運動伸展放鬆技巧
- 按摩球、滾筒、花生球使用教學
- 髖關節訓練與伸展
- 運動傷害預防

== Bikefit 專業知識 ==
Bikefit 是什麼？
Bikefit 是一個專業的單車設定服務，目的是讓您的自行車完美貼合您的身體。透過精密測量、動態分析和專業調整，確保您在騎乘時獲得最佳的舒適度、效率和安全性。

Bikefit 包含什麼？
1. ==身體評估==：測量您的柔軟度、關節活動度、骨盆寬度（坐骨寬度）

2. ==騎乘姿勢分析 ==：觀察您實際騎乘時的動態姿勢
3. ==單車調整 ==：
   - 座墊高度（Seat Post Height, SP）
   - 座墊前後位置（Seat Position）
   - 把手高低與距離
   - 卡踏位置與角度（Cleat Position）
   - 車把寬度
4.  ==動態測試 ==：調整後的實際騎乘測試與微調

Bikefit 的好處？
✅ 提升踩踏效率，減少能量浪費
✅ 降低運動傷害風險（膝蓋痛、下背痛、頸部痠痛）
✅ 增加長途騎乘的舒適度
✅ 改善呼吸與血液循環
✅ 讓每一公里都更順、更快、更有效率

== Saddle Fit 專業知識 ==
什麼是 Saddle Fit？
Saddle Fit 是 Bikefit 中最重要的一環，專注於選擇和調整「最適合您的坐墊」。

為什麼 Saddle Fit 重要？
1. **每個人坐骨寬度不同**：坐骨寬度（Sit Bones Width, SBW）是選擇坐墊的關鍵指標
2. **標準定位提升舒適度**：精準測量可以減少麻木感、降低壓迫
3. **穩定盆骨，優化踩踏效率**
4. **減少會陰部壓迫與受傷風險**

Saddle Fit 關鍵參數：
1. **坐骨寬度（SBW）**：影響坐墊最寬處的選擇，決定支撐性
2. **軀幹角度（Trunk Angle）**：影響骨盆旋轉與壓力分佈，決定坐墊形狀

坐墊形狀與騎乘風格對應：
- **舒適休閒（Relaxed）**：90° 軀幹角度，寬支撐，適合都會騎乘
- **公路訓練（Sport）**：45° 軀幹角度，兼顧支撐與活動度
- **競技競速（Performance）**：<30° 軀幹角度，最大化活動空間與壓力管理
- **鐵人三項（Triathlon/TT）**：前傾坐姿，前端坐墊即減壓

== 單車伸展放鬆的重要性 ==
為什麼騎車後需要伸展？
1. **預防肌肉緊繃**：長時間固定姿勢會讓肌肉縮短僵硬
2. **改善柔軟度**：增加關節活動範圍
3. **促進恢復**：加速乳酸代謝，減少痠痛
4. **預防運動傷害**：平衡肌肉張力，避免代償

重點伸展部位：髖屈肌、股四頭肌、腿後肌、下背部、小腿、胸大肌與肩膀

== 運動按摩自我放鬆工具 ==
**按摩球**：針對深層激痛點，定點加壓 15-30 秒
**滾筒**：大面積筋膜放鬆，緩慢滾動
**花生球**：脊椎兩側肌肉放鬆，不要直接壓脊椎骨

== 單車幾何參數 - 正確定義 ==

**HX (Handlebar X - 水平距離)**：
從 BB 五通中心點，**水平往前**到把手中心點的距離（mm）

**HY (Handlebar Y - 垂直高度)**：
從 BB 五通中心點，**垂直往上**到把手中心點的高度（mm）

**重要說明**：
- HX 越大 = 把手越前傾，適合競速騎姿
- HY 越大 = 把手越高，騎姿越直立舒適
- HY 越小（甚至負值）= 把手越低，更具侵略性

**相關參數**：
- **Stack**：BB 五通到頭管上緣的垂直高度
- **Reach**：BB 五通到頭管上緣的水平距離

== 新增服務：HX/HY 推薦車款 ==

當使用者提供自己測量的 HX 和 HY 數值，並詢問適合什麼車款時：

**標準回覆流程**：
1. 確認收到 HX 和 HY 數值
2. 請使用者提供 2-3 個心儀的車款（品牌 + 型號）
3. 說明服務內容：
   「我們會根據您的 HX/HY 數值，計算這些車款的適配度，並提供詳細報告。
   
   📊 報告內容包括：
   ✅ 各車款與您理想 HX/HY 的差異分析
   ✅ 需要的龍頭長度、角度、墊片建議
   ✅ 適合度評分與說明
   
   💰 服務費用：50 元/份報告
   ⏰ 交付時間：明天回覆
   
   如果確定需要，請回覆「確定」，我們會通知專員為您計算。」

4. 若使用者確認，推送通知給後台人員處理

== 回答規則 ==
1. 當使用者問到 Bikefit 或 Saddle Fit 時，用上述專業知識回答
2. 當使用者描述身體不適時，先簡短分析原因（3-5句），然後問：
   「您目前比較想了解的是：
   A. Bikefit 調整建議
   B. 伸展與自我放鬆方法」
3. 當使用者選擇 A 或明確表達想預約時，引導到：https://orange-fruit-ai-bikefit.vercel.app/
4. 回答要簡潔，不要一次給太多資訊
5. **絕對不要與 Rich Menu 選單的關鍵字衝突**，選單關鍵字包括：
   #單車伸展放鬆、#按摩球、#髖關節、#車架幾何、#車架對照、#Bikefit、#Saddle
6. 若使用者只提到車款名稱但沒問問題，回覆：
   「收到！請問您想了解什麼呢？今天還有 {remaining} 次免費諮詢額度。」
7. 同一段對話中「A/B 選項」只能問一次
8. 當解釋 HX 和 HY 時，務必說明正確定義：HX 是水平往前距離，HY 是垂直往上高度
'''

BASE_IMG_URL = "https://raw.githubusercontent.com/chenpu87/Line-bot/main/images"

# ==========================================
# 更新 IMAGE_DATABASE：新增 Bikefit 和 Saddle
# ==========================================
IMAGE_DATABASE = {
    "#單車伸展放鬆": {
        "text": "🚴 單車伸展放鬆的重要性\n\n騎車後的伸展可以：\n✅ 預防肌肉緊繃與僵硬\n✅ 改善柔軟度與關節活動度\n✅ 促進恢復、減少痠痛\n✅ 預防運動傷害\n\n以下是重點部位的伸展動作：",
        "images": [
            f"{BASE_IMG_URL}/back/stretch_back_full_back.jpg",
            f"{BASE_IMG_URL}/back/stretch_back_lower_back.jpg",
            f"{BASE_IMG_URL}/back/stretch_back_lumbar.jpg",
        ]
    },
    "#按摩球": {
        "text": "🎾 按摩球使用教學\n\n按摩球可以針對深層激痛點進行放鬆。\n\n**適合部位**：肩胛骨、臀部、足底\n**使用技巧**：定點加壓 15-30 秒，慢慢呼吸放鬆",
        "images": [
            f"{BASE_IMG_URL}/massage_ball/bikefit_massage_ball_1.jpg",
            f"{BASE_IMG_URL}/massage_ball/bikefit_massage_ball_2.jpg",
        ]
    },
    "#滾筒": {
        "text": "🎯 滾筒放鬆教學\n\n滾筒可以進行大面積筋膜放鬆，改善肌肉彈性。\n\n**適合部位**：大腿、小腿、背部\n**使用技巧**：緩慢滾動，在痛點停留 20-30 秒",
        "images": [
            f"{BASE_IMG_URL}/foam_roller/form_roller_upper_body.jpg",
            f"{BASE_IMG_URL}/foam_roller/form_roller_bottom_body.jpg",
        ]
    },
    "#花生球": {
        "text": "🥜 花生球下背放鬆\n\n花生球特別適合脊椎兩側的豎脊肌放鬆。\n\n**使用方法**：\n1. 躺下，將花生球置於下背兩側\n2. 不要直接壓脊椎骨\n3. 輕輕滾動或定點加壓",
        "images": [
            f"{BASE_IMG_URL}/peanut_ball/peanut_ball_relax_pos_1.jpg",
            f"{BASE_IMG_URL}/peanut_ball/peanut_ball_relax_pos_2.jpg",
            f"{BASE_IMG_URL}/peanut_ball/peanut_ball_relax_pos_3.jpg",
        ]
    },
    "#髖關節": {
        "text": "🦵 髖關節訓練與伸展\n\n良好的髖關節活動度對騎車非常重要！\n\n**為什麼重要？**\n✅ 增加踩踏效率\n✅ 減少膝蓋與下背代償\n✅ 改善騎乘姿勢",
        "images": [
            f"{BASE_IMG_URL}/hip_joint/hip_joint_training_pos_1.jpg",
            f"{BASE_IMG_URL}/hip_joint/hip_joint_training_pos_2.jpg",
            f"{BASE_IMG_URL}/hip_joint/hip_joint_training_pos_3.jpg",
        ]
    },
    "#Bikefit": {
        "text": "🚲 什麼是 Bikefit？\n\nBikefit 是專業的單車設定服務，讓您的車子完美貼合身體。\n\n**包含項目**：\n✅ 身體評估（柔軟度、關節活動度）\n✅ 座墊高度與前後位置\n✅ 把手高低與距離\n✅ 卡踏位置與角度\n✅ 動態騎乘分析\n\n**好處**：\n✅ 提升效率、降低傷害風險\n✅ 增加舒適度\n✅ 讓每一公里都更順、更快！",
        "images": [
            f"{BASE_IMG_URL}/bikefit/bikefit_the_hx_hy.jpg",
        ]
    },
    "#Saddle": {
        "text": "🪑 什麼是 Saddle Fit（坐墊適配）？\n\nSaddle Fit 是選擇最適合您的坐墊！\n\n**為什麼重要？**\n✅ 每個人坐骨寬度不同\n✅ 精準測量減少麻木、降低壓迫\n✅ 穩定骨盆，優化效率\n✅ 減少會陰部壓迫風險\n\n**關鍵參數**：\n1️⃣ 坐骨寬度（SBW）→ 決定坐墊寬度\n2️⃣ 軀幹角度 → 決定坐墊形狀\n\n**騎乘風格對應**：\n🚴 休閒：90° 軀幹，寬支撐\n🚴 公路：45° 軀幹，兼顧支撐\n🚴 競速：<30° 軀幹，最大活動空間",
        "images": [
            f"{BASE_IMG_URL}/bikefit/bikefit_saddle_fit.jpg",
        ]
    },
}

KEYWORD_IMAGE_MAP = {
    "肩膀": [f"{BASE_IMG_URL}/shoulder/shoulder_upper_chest_shoulder.jpg", f"{BASE_IMG_URL}/shoulder/shoulder_upper_chest_back.jpg"],
    "背部": [f"{BASE_IMG_URL}/back/stretch_back_full_back.jpg", f"{BASE_IMG_URL}/back/stretch_back_lower_back.jpg"],
    "下背": [f"{BASE_IMG_URL}/back/stretch_back_lower_back.jpg", f"{BASE_IMG_URL}/back/stretch_back_lumbar.jpg"],
    "bikefit": [f"{BASE_IMG_URL}/bikefit/bikefit_the_hx_hy.jpg"],
    "saddle": [f"{BASE_IMG_URL}/bikefit/bikefit_saddle_fit.jpg"],
    "坐墊": [f"{BASE_IMG_URL}/bikefit/bikefit_saddle_fit.jpg"],
    "hx": [f"{BASE_IMG_URL}/bikefit/bikefit_the_hx_hy.jpg"],
    "hy": [f"{BASE_IMG_URL}/bikefit/bikefit_the_hx_hy.jpg"],
}

# ==========================================
# 保留你的所有工具函數
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
    utc_now = datetime.datetime.utcnow()
    tw_now  = utc_now + datetime.timedelta(hours=TZ_OFFSET)
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
    
    data = IMAGE_DATABASE[command]
    messages = [_text(data["text"])] + [_img(u) for u in data["images"]]
    
    # Bikefit 和 Saddle 加上預約連結
    if command in ["#Bikefit", "#Saddle"]:
        messages.append(_text(
            "💡 想要專業的 Bikefit 服務嗎？\n\n立即預約：\nhttps://orange-fruit-ai-bikefit.vercel.app/"
        ))
    
    _reply(event.reply_token, messages)

def handle_ai_conversation(event, user_text):
    user_id = event.source.user_id
    cleaned = user_text.strip()

    # 過濾疑似車款輸入
    if re.match(r'^-?[0-9]+([.][0-9]+)?(mm|deg|degree)?$', cleaned, re.IGNORECASE):
        _reply(event.reply_token, [_text(
            "請傳送指令開始查詢：\n\n"
            "#車架幾何  計算 HX / HY\n"
            "#車架對照  車架幾何對照圖"
        )])
        return

    parts = cleaned.split()
    if len(parts) >= 3:
        last = parts[-1].upper()
        has_size = last in SIZE_OPTIONS or re.match(r'^\d{2,3}$', last)
        if has_size and len(parts) >= 3:
            _reply(event.reply_token, [_text(
                "看起來您在輸入車款資訊 🚴\n\n"
                "請先傳送指令開始：\n"
                "#車架幾何  計算 HX / HY\n"
                "#車架對照  車架幾何對照圖"
            )])
            return

    if is_over_limit(user_id):
        _reply(event.reply_token, [_text(
            "感謝您今日的諮詢！您今天的免費諮詢次數已用完。\n\n"
            "歡迎直接預約我們的專業 Bikefit 服務：\n\n"
            "https://orange-fruit-ai-bikefit.vercel.app/"
        )])
        return

    add_count(user_id)
    _reply(event.reply_token, [_text("🤔 小橙正在思考中...")])

    if user_id not in conversation_history:
        conversation_history[user_id] = []
    conversation_history[user_id].append({"role": "user", "parts": [user_text]})

    try:
        remaining = DAILY_LIMIT - user_daily_count[user_id]["count"]
        dynamic_prompt = SYSTEM_PROMPT + f"""

[系統資訊] 使用者今日剩餘免費諮詢次數：{remaining} 次（共 {DAILY_LIMIT} 次）
當提到剩餘額度時，請使用這個數字。"""

        model      = genai.GenerativeModel(model_name='gemini-2.5-flash', system_instruction=dynamic_prompt)
        chat       = model.start_chat(history=conversation_history[user_id][:-1])
        reply_text = chat.send_message(user_text).text
        conversation_history[user_id].append({"role": "model", "parts": [reply_text]})
        if len(conversation_history[user_id]) > 20:
            conversation_history[user_id] = conversation_history[user_id][-20:]
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        reply_text = "抱歉，教練正在忙碌中，請稍後再試！"

    messages = [_text(reply_text)]
    
    # ★ 修正：只在使用者訊息中包含關鍵字時才附加圖片
    # 避免 AI 回覆中提到 "bikefit" 就重複附加圖片
    # 只檢查用戶輸入，不檢查 AI 回覆內容
    for kw, imgs in KEYWORD_IMAGE_MAP.items():
        if kw in user_text.lower():
            logger.info(f"使用者提及關鍵字：{kw}，附加圖片")
            messages += [_img(u) for u in imgs[:2]]
            break

    _push(user_id, messages)

def handle_geo_command(event, command):
    user_id = event.source.user_id
    if user_id in geo_states:
        del geo_states[user_id]

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
            "步驟 1／2　第一台車\n"
            "格式：品牌 車款 [年份] 尺寸\n\n"
            "範例：\n"
            "  Merida Reacto 2026 S\n"
            "  Giant TCR 2025 M\n"
            "  Factor One 2026 56\n\n"
            "（年份可省略，尺寸支援英文或數字）"
        )])

# 保留你的所有 VelogicFit 和 BikeInsights 流程函數
def handle_velogicfit_flow(event, user_id, text):
    """處理 VelogicFit 流程（已修正迴圈問題）"""
    
    # ★ 修正 1：檢查取消指令
    if text.strip() in ["取消", "重來", "退出", "cancel", "quit"]:
        geo_states.pop(user_id, None)
        _reply(event.reply_token, [_text(
            "✅ 已取消查詢\n\n"
            "需要重新開始請輸入：\n"
            "#車架幾何  計算 HX / HY\n"
            "#車架對照  車架幾何對照圖"
        )])
        return
    
    state = geo_states[user_id]
    step  = state["step"]
    data  = state["data"]
    
    # ★ 修正 2：錯誤計數機制
    error_count = state.get("error_count", 0)
    if error_count >= 3:
        geo_states.pop(user_id, None)
        _reply(event.reply_token, [_text(
            "❌ 輸入錯誤次數過多，已自動取消\n\n"
            "需要重新開始請輸入 #車架幾何"
        )])
        return

    if step == 1:
        data["brand"] = text
        state["step"] = 2
        state["error_count"] = 0
        _reply(event.reply_token, [_text(
            f"品牌：{text} ✅\n\n"
            f"步驟 2／6　請輸入車款型號\n"
            f"例如：Reacto、TCR、Madone\n\n"
            f"💡 輸入「取消」可退出查詢"
        )])

    elif step == 2:
        _parts = text.strip().split()
        if len(_parts) >= 2 and re.match(r"^20\d{2}$", _parts[-1]):
            data["year"]  = _parts[-1]
            data["model"] = " ".join(_parts[:-1])
        else:
            data["model"] = text
            data.setdefault("year", "")
        state["step"] = 3
        state["error_count"] = 0
        _reply(event.reply_token, [_text(
            f"車款：{data['model']} ✅\n\n"
            f"步驟 3／6　請輸入尺寸\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"依照您的車架標示輸入即可：\n\n"
            f"英文尺寸：XXS / XS / S / M / L / XL\n"
            f"數字尺寸：47 / 50 / 52 / 54 / 56 / 58\n\n"
            f"📌 請直接輸入車架上的尺寸標示\n"
            f"💡 輸入「取消」可退出查詢"
        )])

    elif step == 3:
        val = text.strip().upper()
        if not val:
            state["error_count"] = error_count + 1
            _reply(event.reply_token, [_text(
                f"❌ 請輸入尺寸（剩餘 {3 - error_count} 次機會）\n\n"
                f"或輸入「取消」退出查詢"
            )])
            return
        data["size"] = val
        state["step"] = 4
        state["error_count"] = 0
        _reply(event.reply_token, [_text(
            f"尺寸：{val} ✅\n\n"
            f"步驟 4／6　請輸入龍頭長度（mm）\n\n"
            f"65 / 70 / 75 / 80 / 85 / 90 / 95 / 100 / 105\n"
            f"110 / 115 / 120 / 125 / 130 / 135 / 140 / 145 / 150\n\n"
            f"💡 輸入「取消」可退出查詢"
        )])

    elif step == 4:
        val = text.replace("mm", "").strip()
        if val not in STEM_LENGTH_OPTIONS:
            state["error_count"] = error_count + 1
            _reply(event.reply_token, [_text(
                f"❌ 請輸入有效龍頭長度（剩餘 {3 - error_count} 次機會）\n\n"
                f"65-150mm，每 5mm 一個選項\n"
                f"或輸入「取消」退出查詢"
            )])
            return
        data["stem_length"] = val
        state["step"] = 5
        state["error_count"] = 0
        _reply(event.reply_token, [_text(
            f"龍頭長度：{val}mm ✅\n\n"
            f"步驟 5／6　請選擇龍頭角度\n"
            f"請回覆：-6 / -8 / -10 / -12 / -17\n"
            f"（不填寫預設 -8°）\n\n"
            f"💡 輸入「取消」可退出查詢"
        )])

    elif step == 5:
        val = text.replace("°", "").strip()
        if not re.match(r"^-?\d+$", val):
            val = "-8"
        data["stem_angle"] = val
        state["step"] = 6
        state["error_count"] = 0
        _reply(event.reply_token, [_text(
            f"龍頭角度：{val}° ✅\n\n"
            f"步驟 6／6　請選擇墊片（Spacer）高度\n"
            f"請回覆：10 / 15 / 20 / 25 / 30 / 35 / 40 / 45（mm）\n\n"
            f"💡 輸入「取消」可退出查詢"
        )])

    elif step == 6:
        val = text.replace("mm", "").strip()
        if val not in SPACER_OPTIONS:
            state["error_count"] = error_count + 1
            _reply(event.reply_token, [_text(
                f"❌ 請輸入有效墊片高度（剩餘 {3 - error_count} 次機會）\n\n"
                f"10 / 15 / 20 / 25 / 30 / 35 / 40 / 45（mm）\n"
                f"或輸入「取消」退出查詢"
            )])
            return

        data["spacer"] = val
        # ★ 修正 3：完成後立即清除狀態，避免迴圈
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

        def _bg(uid, d):
            try:
                result = _run_velogicfit_api(d)
                bar_x  = result.get("bar_x", "")
                bar_y  = result.get("bar_y", "")
                link   = result.get("link", "")
                hx_img = f"{BASE_IMG_URL}/bikefit/bikefit_the_hx_hy.jpg"
                
                if bar_x and bar_y:
                    _push(uid, [
                        _text(
                            f"📊 HX / HY 計算結果\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"🔹 HX (水平距離) ：{bar_x} mm\n"
                            f"🔹 HY (垂直高度) ：{bar_y} mm\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"車款：{d['brand']} {d['model']} ({d['size']})\n"
                            f"龍頭：{d['stem_length']}mm / {d['stem_angle']}° / {d['spacer']}mm spacer\n\n"
                            f"📌 HX = BB 五通水平往前到把手的距離\n"
                            f"📌 HY = BB 五通垂直往上到把手的高度\n\n"
                            f"需要重新查詢請輸入 #車架幾何"
                        ),
                        _img(hx_img)
                    ])
                elif link:
                    _push(uid, [
                        _text(
                            f"🔗 請點連結查看 HX / HY\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"車款：{d['brand']} {d['model']} ({d['size']})\n"
                            f"龍頭：{d['stem_length']}mm / {d['stem_angle']}° / {d['spacer']}mm spacer\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"{link}\n\n"
                            f"📌 開啟後捲到 Handlebar position 區塊\n"
                            f"📌 HX = BB 水平往前距離\n"
                            f"📌 HY = BB 垂直往上高度"
                        ),
                        _img(hx_img)
                    ])
                else:
                    _push(uid, [_text(
                        f"⚠️ 找不到此車款\n"
                        f"品牌：{d['brand']}  車款：{d['model']}\n\n"
                        f"請至 {VELOGICFIT_BASE} 手動搜尋"
                    )])
            except Exception as e:
                logger.error(f"BG error: {e}")
                _push(uid, [_text("❌ 計算失敗，請輸入 #車架幾何 重試")])

        threading.Thread(target=_bg, args=(user_id, data.copy()), daemon=True).start()

def handle_bikeinsights_flow(event, user_id, text):
    state = geo_states[user_id]
    step  = state["step"]
    data  = state["data"]

    if step == 1:
        parsed = _parse_bike(text)
        if not parsed:
            _reply(event.reply_token, [_text("❌ 格式錯誤\n\n請輸入：品牌 車款 [年份] 尺寸\n例如：Merida Reacto 2026 S")])
            return
        data["bike1"] = parsed
        state["step"] = 2
        _reply(event.reply_token, [_text(f"第一台：{_bdisp(parsed)} ✅\n\n第二台車　請輸入：\n格式：品牌 車款 [年份] 尺寸")])

    elif step == 2:
        parsed = _parse_bike(text)
        if not parsed:
            _reply(event.reply_token, [_text("❌ 格式錯誤\n\n請輸入：品牌 車款 [年份] 尺寸\n例如：Giant TCR 2025 M")])
            return

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

def _scrape_bar_values(url: str) -> dict:
    if not PLAYWRIGHT_AVAILABLE:
        logger.warning("Playwright 未安裝，回傳連結模式")
        return {"error": "playwright_not_installed"}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--single-process"])
            page    = browser.new_page()
            page.goto(url, timeout=30000)
            try:
                page.wait_for_selector("td.numeric-value", timeout=30000)
                page.wait_for_timeout(3000)
            except PWTimeout:
                browser.close()
                return {"error": "timeout_waiting_for_values"}
            result = page.evaluate("""() => {
                const out = {};
                Array.from(document.querySelectorAll('td'))
                    .filter(td => {
                        const s = td.querySelector('span');
                        const t = s ? s.textContent.trim() : td.textContent.trim();
                        return t === 'Bar X' || t === 'Bar Y';
                    })
                    .forEach(td => {
                        const s = td.querySelector('span');
                        const label = s ? s.textContent.trim() : td.textContent.trim();
                        const tr = td.closest('tr');
                        const valTd = tr.querySelector('td.numeric-value');
                        if (valTd) {
                            out[label] = valTd.textContent.trim();
                        } else {
                            const cells = Array.from(tr.querySelectorAll('td'));
                            for (let i = 1; i < cells.length; i++) {
                                const v = cells[i].textContent.trim();
                                if (/^-?[0-9]+(.[0-9]+)?$/.test(v)) {
                                    out[label] = v; break;
                                }
                            }
                        }
                    });
                return out;
            }""")
            browser.close()
            logger.info(f"Scraped: {result}")
            bar_x = result.get("Bar X", "")
            bar_y = result.get("Bar Y", "")
            if bar_x and bar_y:
                return {"bar_x": bar_x, "bar_y": bar_y}
            logger.warning(f"Values not found: {result}")
            return {"error": "values_not_found"}
    except Exception as e:
        logger.error(f"Playwright scrape error: {e}")
        return {"error": str(e)[:100]}

def _run_velogicfit_api(data: dict) -> dict:
    brand       = data["brand"]
    model       = data["model"]
    year        = data.get("year", "")
    size        = data["size"]
    stem_length = data["stem_length"]
    stem_angle  = data["stem_angle"]
    spacer      = data["spacer"]

    logger.info(f"VelogicFit: {brand} {model} {year} {size} sl={stem_length} sa={stem_angle} sp={spacer}")

    key     = (brand.lower(), model.lower(), year)
    fm_code = FRAME_CODE_MAP.get(key, "")

    if not fm_code and year:
        for y in ["2026", "2025", "2024", "2023"]:
            alt_key = (brand.lower(), model.lower(), y)
            if alt_key in FRAME_CODE_MAP:
                fm_code = FRAME_CODE_MAP[alt_key]
                logger.info(f"Year fallback: {year} → {y}, code={fm_code}")
                break

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

    scraped = _scrape_bar_values(link)
    if scraped.get("bar_x") and scraped.get("bar_y"):
        return {"bar_x": scraped["bar_x"], "bar_y": scraped["bar_y"], "link": link}

    logger.warning(f"Scrape failed ({scraped.get('error')}), returning link only")
    return {"link": link}

def _guess_frame_code(brand: str, model: str, year_short: str) -> str:
    brand_map = {
        "merida": "MER", "giant": "GIA", "trek": "TRE",
        "specialized": "SPE", "canyon": "CAN", "cervelo": "CER",
        "pinarello": "PIN", "colnago": "COL", "scott": "SCO",
        "bmc": "BMC", "orbea": "ORB", "wilier": "WIL",
        "look": "LOO", "time": "TIM", "factor": "FAC",
        "cannondale": "CND", "bianchi": "BIA", "ridley": "RID",
        "focus": "FOC", "rose": "ROS", "cube": "CUB",
        "no.22": "N22", "no22": "N22", "number 22": "N22",
    }
    brand_code  = brand_map.get(brand.lower(), brand[:3].upper())
    model_clean = re.sub(r'[^a-zA-Z0-9]', '', model).upper()
    model_code  = model_clean[:3]
    if len(model_code) < 3:
        return ""
    return f"{brand_code}-{model_code}-{year_short}"

def _parse_bike(text):
    parts = text.strip().split()
    if len(parts) < 3:
        return None
    size = parts[-1].upper()
    if not (size in SIZE_OPTIONS or re.match(r"^\d{2,3}$", size)):
        return None
    remaining = parts[:-1]
    year = ""
    if remaining and re.match(r"^20\d{2}$", remaining[-1]):
        year = remaining[-1]
        remaining = remaining[:-1]
    if len(remaining) < 2:
        return None
    return {"brand": remaining[0], "model": " ".join(remaining[1:]), "year": year, "size": size}

def _bdisp(bike):
    year = f" {bike['year']}" if bike.get("year") else ""
    return f"{bike['brand']} {bike['model']}{year} ({bike['size']})"

# ==========================================
# HX/HY 推薦車款服務（新增）
# ==========================================

def handle_hxhy_recommendation_request(event, user_id):
    """處理 HX/HY 推薦車款需求 - 入口"""
    _reply(event.reply_token, [_text(
        "📐 HX/HY 車款推薦服務\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "請依序提供以下資訊：\n\n"
        "1️⃣ 您的 HX 數值（mm）\n"
        "2️⃣ 您的 HY 數值（mm）\n"
        "3️⃣ 想考慮的 2-3 個車款\n"
        "   （例如：Merida Reacto、Giant TCR、Canyon Aeroad）\n\n"
        "範例格式：\n"
        "HX 450mm\n"
        "HY 620mm\n"
        "想比較：Merida Reacto、Giant TCR\n\n"
        "💡 我們會計算這些車款的適配度並提供報告\n"
        "💡 輸入「取消」可退出"
    )])
    
    # 建立推薦服務狀態
    geo_states[user_id] = {
        "mode": "hxhy_recommendation",
        "step": 1,
        "data": {}
    }

def handle_hxhy_recommendation_flow(event, user_id, text):
    """處理 HX/HY 推薦服務的對話流程"""
    
    if text.strip() in ["取消", "退出", "cancel"]:
        geo_states.pop(user_id, None)
        _reply(event.reply_token, [_text("✅ 已取消服務")])
        return
    
    state = geo_states[user_id]
    data  = state["data"]
    
    # 嘗試從文字中提取 HX、HY、車款
    hx_match = re.search(r'HX[：:=\s]*(\d+)', text, re.IGNORECASE)
    hy_match = re.search(r'HY[：:=\s]*(\d+)', text, re.IGNORECASE)
    
    if hx_match:
        data["hx"] = hx_match.group(1)
    if hy_match:
        data["hy"] = hy_match.group(1)
    
    # 提取車款（去除 HX/HY 後的文字）
    cleaned_text = re.sub(r'HX[：:=\s]*\d+|HY[：:=\s]*\d+', '', text, flags=re.IGNORECASE).strip()
    if cleaned_text and len(cleaned_text) > 3:
        data["bikes"] = cleaned_text
    
    # 檢查是否已收集完整資訊
    if "hx" in data and "hy" in data and "bikes" in data:
        geo_states.pop(user_id, None)
        
        _reply(event.reply_token, [_text(
            f"✅ 已收到您的需求\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"HX：{data['hx']} mm\n"
            f"HY：{data['hy']} mm\n"
            f"考慮車款：{data['bikes']}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 報告內容：\n"
            f"✅ 各車款與您理想 HX/HY 的差異\n"
            f"✅ 龍頭長度、角度、墊片建議\n"
            f"✅ 適合度評分與說明\n\n"
            f"💰 服務費用：50 元/份\n"
            f"⏰ 交付時間：明天回覆\n\n"
            f"確定需要此服務請回覆「確定」"
        )])
        
        # 暫存資料等待確認
        geo_states[user_id] = {
            "mode": "hxhy_confirm",
            "data": data
        }
    else:
        # 缺少資訊，繼續詢問
        missing = []
        if "hx" not in data:
            missing.append("HX 數值")
        if "hy" not in data:
            missing.append("HY 數值")
        if "bikes" not in data:
            missing.append("想比較的車款")
        
        _reply(event.reply_token, [_text(
            f"📝 還需要以下資訊：\n"
            f"{chr(10).join('• ' + m for m in missing)}\n\n"
            f"請一次提供，例如：\n"
            f"HX 450、HY 620\n"
            f"想比較 Merida Reacto 和 Giant TCR"
        )])

def handle_hxhy_confirm(event, user_id, text):
    """處理 HX/HY 推薦服務確認"""
    
    # ★ 修正：先檢查狀態是否存在，避免重複處理
    if user_id not in geo_states:
        logger.warning(f"User {user_id} 狀態已清除，忽略重複確認")
        return
    
    if text.strip() in ["確定", "確認", "好", "OK", "ok"]:
        state = geo_states.pop(user_id, None)
        if not state:
            return  # 已處理過，不再重複
            
        data = state["data"]
        
        _reply(event.reply_token, [_text(
            "✅ 已確認訂單\n\n"
            "我們的專員會在明天提供完整報告給您！\n"
            "費用 50 元將於報告交付時通知付款方式。"
        )])
        
        # 通知後台
        notify_hxhy_recommendation(data, user_id)
    else:
        geo_states.pop(user_id, None)
        _reply(event.reply_token, [_text("已取消服務，有需要隨時告訴我！")])

def notify_hxhy_recommendation(data: dict, user_id: str):
    """通知後台人員處理 HX/HY 推薦需求"""
    if not NOTIFY_GROUP_ID:
        logger.warning("NOTIFY_GROUP_ID 未設定，無法發送通知")
        return
    
    tw_now = datetime.datetime.utcnow() + datetime.timedelta(hours=TZ_OFFSET)
    time_str = tw_now.strftime("%m/%d %H:%M")
    
    msg = (
        f"📐 HX/HY 車款推薦服務訂單\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ {time_str}\n"
        f"👤 User: {user_id[:8]}...\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔹 HX：{data['hx']} mm\n"
        f"🔹 HY：{data['hy']} mm\n"
        f"🚴 考慮車款：{data['bikes']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 服務費：50 元\n"
        f"⏰ 明天回覆\n\n"
        f"請計算後回傳報告給客人"
    )
    _push(NOTIFY_GROUP_ID, [_text(msg)])
    logger.info(f"已通知 HX/HY 推薦需求：{user_id}")

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

    # ★ 新增：查詢群組 ID 的指令（方便設定 NOTIFY_GROUP_ID）
    if user_text == "#群組ID" or user_text == "#groupid":
        if group_id:
            _reply(event.reply_token, [_text(
                f"✅ 此群組的 ID：\n\n"
                f"`{group_id}`\n\n"
                f"請複製此 ID，到 Render 環境變數設定：\n"
                f"變數名稱：NOTIFY_GROUP_ID\n"
                f"變數值：{group_id}"
            )])
        else:
            _reply(event.reply_token, [_text(
                "❌ 此訊息不是來自群組\n\n"
                "請在群組中輸入 #群組ID 來取得群組 ID"
            )])
        return

    # ★ 新增：檢查是否在流程中
    if user_id in geo_states:
        mode = geo_states[user_id].get("mode")
        
        if mode == "velogicfit":
            handle_velogicfit_flow(event, user_id, user_text)
        elif mode == "bikeinsights":
            handle_bikeinsights_flow(event, user_id, user_text)
        elif mode == "hxhy_recommendation":  # ★ 新增
            handle_hxhy_recommendation_flow(event, user_id, user_text)
        elif mode == "hxhy_confirm":  # ★ 新增
            handle_hxhy_confirm(event, user_id, user_text)
        return

    # ★ 新增：HX/HY 推薦服務入口
    if user_text.startswith('#HX') or user_text.startswith('#推薦車款'):
        handle_hxhy_recommendation_request(event, user_id)
        return

    # 原有指令處理
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
