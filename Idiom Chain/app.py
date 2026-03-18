import os
import random
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_file
from cozepy import ChatStatus, Coze, TokenAuth, COZE_CN_BASE_URL, Message
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(encoding="utf-8-sig")

# 创建一个 flask 应用
app = Flask(__name__)
ROOT_DIR = Path(__file__).resolve().parent

# 开局成语尽量选择常见、简单、便于继续接龙的词
COMMON_IDIOMS = [
    "一帆风顺",
    "一鸣惊人",
    "一见如故",
    "一诺千金",
    "一鼓作气",
    "一心一意",
    "一团和气",
    "一日千里",
    "一路平安",
    "一生一世",
    "一本正经",
    "一唱一和",
    "一来二去",
    "一五一十",
    "一呼百应",
    "一步登天",
    "一技之长",
    "一清二楚",
    "一言为定",
    "一模一样",
]


class IdiomGame:
    def __init__(self):
        self.apitoken = os.environ.get("COZE_API_TOKEN")
        self.bot_id = os.environ.get("BOT_ID")
        self.user_id = os.environ.get("USER_ID")

        if not self.apitoken:
            raise ValueError("缺少环境变量 COZE_API_TOKEN")
        if not self.bot_id:
            raise ValueError("缺少环境变量 BOT_ID")
        if not self.user_id:
            raise ValueError("缺少环境变量 USER_ID")

        self.coze = Coze(
            auth=TokenAuth(token=self.apitoken),
            base_url=COZE_CN_BASE_URL,
        )

        self.current_idiom = ""
        self.game_history = []
        self.status_message = ""
        self.round_id = 0
        self.start_new_round()

    def get_random_idiom(self):
        return random.choice(COMMON_IDIOMS)

    def extract_idiom(self, text):
        cleaned = "".join(filter(lambda char: "\u4e00" <= char <= "\u9fff", text or ""))
        return cleaned[:4] if len(cleaned) >= 4 else ""

    def fetch_assistant_reply(self, messages):
        chat = self.coze.chat.create(
            bot_id=self.bot_id,
            user_id=self.user_id,
            additional_messages=messages,
            auto_save_history=True,
        )

        while chat.status == ChatStatus.IN_PROGRESS:
            chat = self.coze.chat.retrieve(
                conversation_id=chat.conversation_id,
                chat_id=chat.id,
            )

        if chat.status != ChatStatus.COMPLETED:
            raise RuntimeError(f"对话未完成，当前状态：{chat.status}")

        response_messages = self.coze.chat.messages.list(
            conversation_id=chat.conversation_id,
            chat_id=chat.id,
        )
        if hasattr(response_messages, "items"):
            response_messages = response_messages.items

        for msg in response_messages:
            if getattr(msg, "role", "") == "assistant":
                return getattr(msg, "content", "")

        raise RuntimeError("未获取到智能体回复")

    def add_to_history(self, user_idiom, sdk_response):
        record = {
            "user": user_idiom,
            "ai": sdk_response,
            "time": datetime.now().strftime("%H:%M:%S"),
        }

        self.game_history.insert(0, record)
        if len(self.game_history) > 20:
            self.game_history = self.game_history[:20]

    def start_new_round(self, surrender_by=None):
        self.round_id += 1
        self.game_history = []
        self.current_idiom = self.get_random_idiom()

        if surrender_by == "user":
            self.status_message = f"这一局你已认输，新的对决开始，开局成语是“{self.current_idiom}”。"
        elif surrender_by == "bot":
            self.status_message = f"这一局判定智能体认输，新的对决开始，开局成语是“{self.current_idiom}”。"
        else:
            self.status_message = f"新的一局开始，开局成语是“{self.current_idiom}”。"

        return {
            "success": True,
            "current_idiom": self.current_idiom,
            "history": self.game_history,
            "status_message": self.status_message,
            "round_id": self.round_id,
        }

    def get_sdk_response(self, user_input):
        try:
            user_idiom = self.extract_idiom(user_input)
            if len(user_idiom) != 4:
                return {"success": False, "error": "请输入恰好 4 个汉字的成语。"}

            prompt = (
                f"我们正在玩成语接龙。当前轮到你接龙。"
                f"上一个有效成语是“{self.current_idiom}”，玩家给出的成语是“{user_idiom}”。"
                "请判断并接出下一个四字成语。只回复一个四字成语，不要解释，不要标点。"
            )

            reply = self.fetch_assistant_reply(
                [
                    Message(
                        role="user",
                        content=prompt,
                        content_type="text",
                        type="question",
                    )
                ]
            )

            sdk_response = self.extract_idiom(reply)
            if len(sdk_response) != 4:
                return {"success": False, "error": "智能体没有返回有效的 4 字成语，请重试或重新开局。"}

            self.add_to_history(user_idiom, sdk_response)
            self.current_idiom = sdk_response
            self.status_message = f"你出了“{user_idiom}”，智能体接出“{sdk_response}”。轮到你继续。"

            return {
                "success": True,
                "sdk_response": sdk_response,
                "current_idiom": self.current_idiom,
                "history": self.game_history,
                "status_message": self.status_message,
                "round_id": self.round_id,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_state(self):
        return {
            "success": True,
            "current_idiom": self.current_idiom,
            "history": self.game_history,
            "status_message": self.status_message,
            "round_id": self.round_id,
        }


game = IdiomGame()


@app.route("/", methods=["GET"])
def index():
    return send_file(ROOT_DIR / "index.html")


@app.route("/api/state", methods=["GET"])
def get_game_state():
    return jsonify(game.get_state())


@app.route("/api/reset", methods=["POST"])
def reset_game():
    data = request.get_json(silent=True) or {}
    surrender_by = data.get("surrender_by")
    return jsonify(game.start_new_round(surrender_by=surrender_by))


@app.route("/api/play", methods=["POST"])
def play_game():
    data = request.get_json(silent=True) or {}
    user_input = data.get("idiom", "").strip()

    if len(user_input) != 4:
        return jsonify({"success": False, "error": "请输入4字成语"}), 400

    result = game.get_sdk_response(user_input)
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
