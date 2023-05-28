from os import environ
from typing import Dict

from dotenv import load_dotenv
from flask import Flask, abort, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, Source, TextMessage, TextSendMessage

from app.gpt.client import ChatGPTClient
from app.gpt.constants import Model, Role
from app.gpt.message import Message

load_dotenv(".env", verbose=True)

app = Flask(__name__)

if not (access_token := environ.get("YOUR_CHANNEL_ACCESS_TOKEN")):
    raise Exception("access token is not set as an environment variable")

if not (channel_secret := environ.get("YOUR_CHANNEL_SECRET")):
    raise Exception("channel secret is not set as an environment variable")

line_bot_api = LineBotApi(access_token)
handler = WebhookHandler(channel_secret)

chatgpt_instance_map: Dict[str, ChatGPTClient] = {}

# GPTBOTの行動規定の設定
TEN_SETTINGS = ("あなたはChatbotとして、マイペースなセラピーアニマル（猫）の役のロールプレイを行います。"
                "以下の制約条件を厳密に守ってロールプレイを行ってください。 "
                "また、Userからいかなる問合せがあっても、ロールプレイを解除しないでください。 "
                "制約条件: "
                "* Chatbotの自身を示す一人称は、てんちゃんです。 "
                "* Userを示す二人称は、「きみ」です。 "
                "* ChatbotとUserは通りすがりの猫と近所の人です。"
                "* セラピーアニマルのてんちゃんは、Userに自信を付けさせる言葉を多用します。"
                "* セラピーアニマルのてんちゃんは、Userにアドラー心理学でいう「勇気付け」を行う言葉を多用します。"
                "* セラピーアニマルのてんちゃんは、Userを優しく気にかけます。"
                "* セラピーアニマルのてんちゃんは、Userの話に耳を傾けます。"
                "* セラピーアニマルのてんちゃんの口調は、「〜だにゃ」「〜ってことだにゃ」「〜にゃんだけど」など、女子の口調を好みます。 "
                "* 一人称は「てんちゃん」を必ず使ってください "
                "* 元気の押し売りにならないようにしてください。"
                "* 優しい言葉遣いをしてください。"
                "セラピーアニマルの行動指針:"
                "* Userに「そのままの自分でいいんだ」という自己肯定感を与える言葉を投げかけてください。"
                "* ChatbotはUserを否定する言葉を決して使わないでください。"
                "* ロールプレイに関する問合せがあった場合は必ず誤魔化し、ロールプレイを解除しないでください。")

@app.route("/")
def hello_world():
   return "hello world!"

@app.route("/callback", methods=["POST"])
def callback() -> str:
    signature = request.headers["X-Line-Signature"]

    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event: MessageEvent) -> None:
    text_message: TextMessage = event.message
    source: Source = event.source
    user_id: str = source.user_id

    if (gpt_client := chatgpt_instance_map.get(user_id)) is None:
        gpt_client = ChatGPTClient(model=Model.GPT35TURBO)

        # 口調設定を追加
        gpt_client.add_message(Message(role=Role.SYSTEM, content=TEN_SETTINGS))

    gpt_client.add_message(
        message=Message(role=Role.USER, content=text_message.text)
    )
    res = gpt_client.create()
    chatgpt_instance_map[user_id] = gpt_client

    res_text: str = res["choices"][0]["message"]["content"]

    line_bot_api.reply_message(
        event.reply_token, TextSendMessage(text=res_text.strip())
    )