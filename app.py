# ==========================================
# LINE Bot with Gemini AI for Render
# 使用 google-generativeai (舊版穩定 SDK)
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
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# ==========================================
# 從環境變數讀取金鑰
# ==========================================
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# ==========================================
# 初始化服務
# ==========================================
genai.configure(api_key=GEMINI_API_KEY)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
app = Flask(__name__)

conversation_history = {}
user_daily_count = {}
DAILY_LIMIT = 6

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

    # 加入使用者訊息
    conversation_history[user_id].append({
        "role": "user",
        "parts": [user_text]
    })

    try:
        app.logger.info("呼叫 Gemini API...")
        
        # 建立模型
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            system_instruction=SYSTEM_PROMPT
        )
        
        # 開始對話
        chat = model.start_chat(history=conversation_history[user_id][:-1])
        
        # 發送訊息
        response = chat.send_message(user_text)
        reply_text = response.text
        
        app.logger.info(f"Gemini 回應: {reply_text}")

        # 儲存 AI 的回應到對話歷史
        conversation_history[user_id].append({
            "role": "model",
            "parts": [reply_text]
        })

        # 保持對話歷史在合理長度
        if len(conversation_history[user_id]) > 20:
            conversation_history[user_id] = conversation_history[user_id][-20:]

    except Exception as e:
        app.logger.error(f"Gemini API 錯誤: {str(e)}")
        reply_text = "抱歉，教練正在幫客戶調整車位，請稍後再試！如果問題持續，歡迎直接預約：https://orange-fruit-ai-bikefit.vercel.app/"

    # 回覆訊息
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
        app.logger.info("訊息已成功回覆")
    except Exception as e:
        app.logger.error(f"LINE 回覆錯誤: {str(e)}")

# ==========================================
# 啟動應用程式
# ==========================================
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)