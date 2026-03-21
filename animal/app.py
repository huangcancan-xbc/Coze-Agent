import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file
from cozepy import ChatStatus, Coze, Message, TokenAuth, COZE_CN_BASE_URL


# 统一使用当前文件所在目录作为资源根目录。
ROOT_DIR = Path(__file__).resolve().parent

# 兼容带 BOM 的 .env 文件。
load_dotenv(ROOT_DIR / ".env", encoding="utf-8-sig")

app = Flask(__name__)

# 如果 .env 中 BOT_ID 不可用，则按这个名称自动查找真正可调用的 Bot。
TARGET_BOT_NAME = "动物视频生成"
DEFAULT_USER_ID = os.environ.get("USER_ID", "animal_video_web_user")

# 这个智能体更适合短描述，太长的输入更容易触发工作流插件报错。
MAX_PROMPT_LENGTH = 120


def create_coze_client():
    """创建 Coze 客户端，并检查必要的 token 是否存在。"""
    api_token = os.environ.get("COZE_API_TOKEN")
    if not api_token:
        raise ValueError("缺少环境变量 COZE_API_TOKEN")

    return Coze(
        auth=TokenAuth(token=api_token),
        base_url=COZE_CN_BASE_URL,
    )


def resolve_bot_id(coze):
    """
    获取最终可调用的 bot_id。

    优先使用 .env 中的 BOT_ID；
    如果没填或填错，则遍历当前账号可访问的工作空间，按名称查找目标智能体。
    """
    env_bot_id = os.environ.get("BOT_ID", "").strip()

    spaces = coze.workspaces.list()
    spaces = spaces.items if hasattr(spaces, "items") else spaces
    matched_name_bot_id = ""

    for space in spaces:
        bots = coze.bots.list(space_id=space.id)
        bots = bots.items if hasattr(bots, "items") else bots

        for bot in bots:
            if env_bot_id and getattr(bot, "id", "") == env_bot_id:
                return env_bot_id
            if getattr(bot, "name", "") == TARGET_BOT_NAME:
                matched_name_bot_id = bot.id

    if matched_name_bot_id:
        return matched_name_bot_id

    raise ValueError(f"未找到可访问的智能体：{TARGET_BOT_NAME}")


def wait_for_chat(coze, conversation_id, chat_id):
    """轮询等待 Coze 对话完成。"""
    chat = coze.chat.retrieve(conversation_id=conversation_id, chat_id=chat_id)
    while chat.status == ChatStatus.IN_PROGRESS:
        chat = coze.chat.retrieve(conversation_id=conversation_id, chat_id=chat_id)
    return chat


def get_chat_messages(coze, conversation_id, chat_id):
    """把 SDK 返回的消息对象统一转换为列表。"""
    messages = coze.chat.messages.list(conversation_id=conversation_id, chat_id=chat_id)
    return messages.items if hasattr(messages, "items") else messages


def extract_message_content(messages, message_type):
    """按消息类型提取第一条匹配的 content。"""
    for message in messages:
        if getattr(message, "type", "") == message_type:
            return getattr(message, "content", "") or ""
    return ""


def extract_follow_ups(messages):
    """提取智能体给出的追问建议。"""
    items = []
    for message in messages:
        if getattr(message, "type", "") == "follow_up":
            text = (getattr(message, "content", "") or "").strip()
            if text:
                items.append(text)
    return items[:3]


def extract_urls(text):
    """从普通文本或 Markdown 中提取全部链接。"""
    return re.findall(r"https?://[^\s)>\"]+", text or "")


def parse_tool_payload(tool_response_text):
    """
    尝试把 tool_response 解析成 JSON。

    这个智能体在成功时，tool_response 很可能是 JSON 字符串；
    在失败时，则可能直接是 'biz error: ...' 这种纯文本。
    """
    try:
        return json.loads(tool_response_text or "{}")
    except json.JSONDecodeError:
        return {}


def classify_tool_error(tool_response_text, answer_text, user_text):
    """
    识别插件层错误，并转换为更友好的中文提示。

    特别处理两类问题：
    1. 请求过大
    2. 服务繁忙 / 访问量过大
    """
    text = (tool_response_text or "").lower()
    answer = (answer_text or "").lower()
    original = tool_response_text or ""

    large_request_signals = [
        "请求过大",
        "payload too large",
        "too large",
        "413",
    ]
    busy_signals = [
        "访问量过大",
        "服务繁忙",
        "稍后再试",
        "status_code=429",
        "code=1305",
    ]

    if len(user_text) > MAX_PROMPT_LENGTH:
        return "当前请求过大，请稍后再试"

    if any(signal in text for signal in large_request_signals):
        return "当前请求过大，请稍后再试"

    # 某些大请求会被工作流插件折叠成“系统错误”，这里也做温和兜底。
    if "系统错误" in original and len(user_text) > 60:
        return "当前请求过大，请稍后再试"

    if any(signal in answer for signal in busy_signals):
        return "当前视频生成服务繁忙，请稍后再试"

    if any(signal in text for signal in busy_signals):
        return "当前视频生成服务繁忙，请稍后再试"

    if original.startswith("biz error:"):
        return "视频生成失败，请稍后重试"

    return ""


def choose_video_url(tool_payload, answer_text):
    """从 tool_response 和 answer 中提取最可能的视频链接。"""
    url_candidates = []

    for key in ("url", "output", "video_url", "videos"):
        value = tool_payload.get(key, [])
        if isinstance(value, list):
            url_candidates.extend(value)
        elif isinstance(value, str):
            url_candidates.append(value)

    url_candidates.extend(extract_urls(answer_text))

    for url in url_candidates:
        if isinstance(url, str) and any(token in url.lower() for token in (".mp4", ".mov", ".m3u8", ".webm", "video")):
            return url
    return ""


def build_prompt(user_text):
    """构造发给智能体的最终提示词。"""
    return (
        "请根据以下动物描述生成一个适合展示的短视频，"
        "只需要围绕动物动作、场景和风格来生成："
        f"{user_text}"
    )


def generate_animal_video(user_text):
    """
    调用 Coze 智能体生成动物视频。

    返回统一结构给前端，避免前端自己理解 Coze 的消息格式。
    """
    if not user_text:
        raise ValueError("请输入动物相关描述。")

    if len(user_text) > MAX_PROMPT_LENGTH:
        raise ValueError("当前请求过大，请稍后再试")

    coze = create_coze_client()
    bot_id = resolve_bot_id(coze)

    chat = coze.chat.create(
        bot_id=bot_id,
        user_id=DEFAULT_USER_ID,
        additional_messages=[
            Message(
                role="user",
                content=build_prompt(user_text),
                content_type="text",
                type="question",
            )
        ],
        auto_save_history=True,
    )

    chat = wait_for_chat(coze, chat.conversation_id, chat.id)
    if chat.status != ChatStatus.COMPLETED:
        raise RuntimeError(f"对话未完成，当前状态：{chat.status}")

    messages = get_chat_messages(coze, chat.conversation_id, chat.id)
    tool_response_text = extract_message_content(messages, "tool_response")
    answer_text = extract_message_content(messages, "answer")
    follow_ups = extract_follow_ups(messages)

    friendly_error = classify_tool_error(tool_response_text, answer_text, user_text)
    if friendly_error:
        raise ValueError(friendly_error)

    tool_payload = parse_tool_payload(tool_response_text)
    video_url = choose_video_url(tool_payload, answer_text)
    if not video_url:
        raise RuntimeError("智能体已返回结果，但未解析到可播放的视频链接。")

    return {
        "success": True,
        "bot_id": bot_id,
        "prompt": user_text,
        "video_url": video_url,
        "answer_text": answer_text or "视频已生成完成。",
        "follow_ups": follow_ups,
        "share_url": "https://www.coze.cn/store/agent/7619592811435982889?from=store_search_suggestion&bid=6jfi6shrs200r",
    }


@app.route("/")
def index():
    """返回前端页面。"""
    return send_file(ROOT_DIR / "index.html")


@app.route("/styles.css")
def styles():
    """返回独立 CSS 文件。"""
    return send_file(ROOT_DIR / "styles.css")


@app.route("/app.js")
def script():
    """返回独立 JS 文件。"""
    return send_file(ROOT_DIR / "app.js")


@app.route("/api/config")
def get_config():
    """给前端提供初始化信息和示例输入。"""
    return jsonify(
        {
            "success": True,
            "bot_name": TARGET_BOT_NAME,
            "share_url": "https://www.coze.cn/store/agent/7619592811435982889?from=store_search_suggestion&bid=6jfi6shrs200r",
            "max_prompt_length": MAX_PROMPT_LENGTH,
            "examples": [
                "一只小猫在花园里追蝴蝶",
                "一只熊猫抱着竹子慢慢进食",
            ],
        }
    )


@app.route("/favicon.ico")
def favicon():
    return ("", 204)


@app.route("/api/generate-video", methods=["POST"])
def generate_video():
    """生成动物视频的主接口。"""
    try:
        data = request.get_json(silent=True) or {}
        user_text = (data.get("prompt") or "").strip()

        result = generate_animal_video(user_text)
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
