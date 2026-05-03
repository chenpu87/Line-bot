# ==========================================
# LINE Bot with Gemini AI + Image Support
# Orange Fruit 小橙特助
# ==========================================
import os
import datetime
import google.generativeai as genai
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    ImageMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# ==========================================
# 環境變數
# ==========================================
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# ==========================================
# 初始化
# ==========================================
genai.configure(api_key=GEMINI_API_KEY)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
app = Flask(__name__)

conversation_history = {}
user_daily_count = {}
DAILY_LIMIT = 10

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

# ==========================================
# 圖片資料庫
# ==========================================
BASE_URL = "https://raw.githubusercontent.com/chenpu87/Line-bot/main/images"

IMAGE_DATABASE = {
    "#伸展放鬆": {
        "text": "🚴 騎車後的伸展非常重要！\n\n以下是背部伸展系列動作，每個動作維持 30 秒：",
        "images": [
            f"{BASE_URL}/back/stretch_back_full_back.jpg",
            f"{BASE_URL}/back/stretch_back_lower_back.jpg",
            f"{BASE_URL}/back/stretch_back_lumbar.jpg",
        ]
    },
    "#核心訓練": {
        "text": "💪 核心訓練對騎士非常重要！\n\n強健的核心肌群能提升踩踏效率、保護下背、維持良好騎姿。",
        "images": []  # 如果之後有核心訓練圖，可以加在這裡
    },
    "#按摩球教學": {
        "text": "🎾 按摩球使用教學\n\n按摩球可以針對深層肌肉進行放鬆，特別適合處理激痛點。",
        "images": [
            f"{BASE_URL}/massage_ball/bikefit_massage_ball_1.jpg",
            f"{BASE_URL}/massage_ball/bikefit_massage_ball_2.jpg",
        ]
    },
    "#滾筒上半身": {
        "text": "🎯 滾筒放鬆上半身\n\n滾筒可以放鬆大面積肌肉，改善筋膜沾黏。",
        "images": [
            f"{BASE_URL}/foam_roller/form_roller_upper_body.jpg",
        ]
    },
    "#滾筒下半身": {
        "text": "🎯 滾筒放鬆下半身\n\n大腿、小腿的肌肉放鬆能大幅改善騎乘舒適度。",
        "images": [
            f"{BASE_URL}/foam_roller/form_roller_bottom_body.jpg",
        ]
    },
    "#花生球教學": {
        "text": "🥜 花生球放鬆下背部\n\n花生球特別適合脊椎兩側的肌肉放鬆，使用時請小心不要直接壓到脊椎。",
        "images": [
            f"{BASE_URL}/peanut_ball/peanut_ball_relax_pos_1.jpg",
            f"{BASE_URL}/peanut_ball/peanut_ball_relax_pos_2.jpg",
            f"{BASE_URL}/peanut_ball/peanut_ball_relax_pos_3.jpg",
        ]
    },
    "#髖關節": {
        "text": "🦵 髖關節伸展與訓練\n\n良好的髖關節活動度對騎車非常重要！",
        "images": [
            f"{BASE_URL}/hip_joint/hip_joint_training_pos_1.jpg",
            f"{BASE_URL}/hip_joint/hip_joint_training_pos_2.jpg",
            f"{BASE_URL}/hip_joint/hip_joint_training_pos_3.jpg",
        ]
    },
    "#Bikefit常識": {
        "text": "🚲 Bikefit 小常識\n\n正確的 Bikefit 能大幅提升騎乘舒適度和效率！",
        "images": [
            f"{BASE_URL}/bikefit/bikefit_saddle_fit.jpg",
            f"{BASE_URL}/bikefit/bikefit_cleat_fit.jpg",
            f"{BASE_URL}/bikefit/bikefit_the_hx_hy.jpg",
        ]
    },
    "#騎士重置": {
        "text": "🔄 騎士每日重置動作\n\n每天 5 分鐘，放鬆緊繃的肌肉，改善久坐造成的腰痠背痛！",
        "images": [
            f"{BASE_URL}/cyclist_reset/reset_warm_up_cool%20_down_1.jpg",
            f"{BASE_URL}/cyclist_reset/reset_warm_up_cool%20_down_2.jpg",
        ]
    },
}

# ==========================================
# 關鍵字對應圖片（AI 智能判斷）
# ==========================================
KEYWORD_IMAGE_MAP = {
    "肩膀": [
        f"{BASE_URL}/shoulder/shoulder_upper_chest_shoulder.jpg",
        f"{BASE_URL}/shoulder/shoulder_upper_chest_back.jpg",
    ],
    "背部": [
        f"{BASE_URL}/back/stretch_back_full_back.jpg",
        f"{BASE_URL}/back/stretch_back_lower_back.jpg",
    ],
    "下背": [
        f"{BASE_URL}/back/stretch_back_lower_back.jpg",
        f"{BASE_URL}/back/stretch_back_lumbar.jpg",
    ],
    "髖關節": [
        f"{BASE_URL}/hip_joint/hip_joint_training_pos_1.jpg",
    ],
    "bikefit": [
        f"{BASE_URL}/bikefit/bikefit_the_hx_hy.jpg",
    ],
}

# ==========================================
# 限流函數
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

# ==========================================
# Rich Menu 指令處理
# ==========================================
def handle_rich_menu_command(event, command):
    """處理 Rich Menu 按鈕指令"""
    
    if command not in IMAGE_DATABASE:
        return handle_ai_conversation(event, command)
    
    data = IMAGE_DATABASE[command]
    messages = []
    
    # 加入文字說明
    messages.append(TextMessage(text=data["text"]))
    
    # 加入圖片
    for img_url in data["images"]:
        messages.append(ImageMessage(
            original_content_url=img_url,
            preview_image_url=img_url
        ))
    
    # 回傳訊息
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=messages
            )
        )
    
    app.logger.info(f"已回傳 Rich Menu 指令：{command}")

# ==========================================
# AI 對話處理（含智能圖片判斷）
# ==========================================
def handle_ai_conversation(event, user_text):
    """處理 AI 對話，並智能判斷是否需要圖片"""
    
    user_id = event.source.user_id
    
    # 限流檢查
    if is_over_limit(user_id):
        reply_text = "感謝您今日的諮詢！您今天的免費諮詢次數已用完。\n\n歡迎直接預約我們的專業 Bikefit 服務，讓教練為您進行完整評估：\n\nhttps://orange-fruit-ai-bikefit.vercel.app/"
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
        return
    
    # 計數 +1
    add_count(user_id)
    
    # 建立對話記憶
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    
    conversation_history[user_id].append({
        "role": "user",
        "parts": [user_text]
    })
    
    try:
        app.logger.info("呼叫 Gemini API...")
        
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            system_instruction=SYSTEM_PROMPT
        )
        
        chat = model.start_chat(history=conversation_history[user_id][:-1])
        response = chat.send_message(user_text)
        reply_text = response.text
        
        app.logger.info(f"Gemini 回應: {reply_text}")
        
        conversation_history[user_id].append({
            "role": "model",
            "parts": [reply_text]
        })
        
        if len(conversation_history[user_id]) > 20:
            conversation_history[user_id] = conversation_history[user_id][-20:]
        
    except Exception as e:
        app.logger.error(f"Gemini API 錯誤: {str(e)}")
        reply_text = "抱歉，教練正在忙碌中，請稍後再試！如果問題持續，歡迎直接預約：https://orange-fruit-ai-bikefit.vercel.app/"
    
    # 智能判斷是否需要附加圖片
    messages = [TextMessage(text=reply_text)]
    
    for keyword, images in KEYWORD_IMAGE_MAP.items():
        if keyword in user_text.lower():
            app.logger.info(f"偵測到關鍵字：{keyword}，附加示範圖")
            for img_url in images[:2]:  # 最多附加 2 張
                messages.append(ImageMessage(
                    original_content_url=img_url,
                    preview_image_url=img_url
                ))
            break
    
    # 回傳訊息
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=messages
            )
        )
    
    app.logger.info("訊息已成功回覆")

# ==========================================
# Webhook 路由
# ==========================================
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("Invalid signature")
        abort(400)
    
    return 'OK'

@app.route("/", methods=['GET'])
def home():
    return "Orange Fruit LINE Bot is running! 🍊"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = event.message.text
    user_id = event.source.user_id
    
    app.logger.info(f"收到訊息: {user_text} from {user_id}")
    
    # 判斷是 Rich Menu 指令還是一般對話
    if user_text.startswith('#'):
        handle_rich_menu_command(event, user_text)
    else:
        handle_ai_conversation(event, user_text)

# ==========================================
# 啟動應用程式
# ==========================================
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
