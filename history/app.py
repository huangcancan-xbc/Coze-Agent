import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file
from cozepy import ChatStatus, Coze, Message, TokenAuth, COZE_CN_BASE_URL


# 以当前文件所在目录作为项目根目录，方便后续读取 .env 和 index.html。
ROOT_DIR = Path(__file__).resolve().parent

# 兼容 Windows 下带 BOM 的 .env 文件。
load_dotenv(ROOT_DIR / ".env", encoding="utf-8-sig")

app = Flask(__name__)

# 如果 .env 里的 BOT_ID 没填或者填错，就回退到按名称查找。
TARGET_BOT_NAME = "历史海报制作"

# Coze 的 user_id 由调用方自己定义，用来隔离不同用户的对话上下文。
DEFAULT_USER_ID = os.environ.get("USER_ID", "history_poster_web_user")


def create_coze_client():
    """
    创建 Coze SDK 客户端。

    这里单独封装成函数，主要是为了：
    1. 让主流程代码更短、更好读
    2. 集中处理 token 缺失这类初始化错误
    """
    api_token = os.environ.get("COZE_API_TOKEN")
    if not api_token:
        raise ValueError("缺少环境变量 COZE_API_TOKEN")

    return Coze(
        auth=TokenAuth(token=api_token),
        base_url=COZE_CN_BASE_URL,
    )


def resolve_bot_id(coze):
    """
    确定当前应该调用哪个智能体。

    优先级：
    1. 使用 .env 中配置的 BOT_ID
    2. 如果 BOT_ID 无效，则遍历当前 token 可访问的工作空间，
       按智能体名称“历史海报制作”自动查找
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
    """
    轮询等待 Coze 对话完成。

    Coze chat.create 返回后，对话可能还在处理中，
    所以这里持续 retrieve，直到状态不再是 IN_PROGRESS。
    """
    chat = coze.chat.retrieve(conversation_id=conversation_id, chat_id=chat_id)
    while chat.status == ChatStatus.IN_PROGRESS:
        chat = coze.chat.retrieve(conversation_id=conversation_id, chat_id=chat_id)
    return chat


def get_chat_messages(coze, conversation_id, chat_id):
    """
    获取当前对话的全部消息。

    SDK 返回值有时是带 items 的分页对象，所以这里统一展开成列表。
    """
    messages = coze.chat.messages.list(conversation_id=conversation_id, chat_id=chat_id)
    return messages.items if hasattr(messages, "items") else messages


def extract_tool_payload(messages):
    """
    提取工作流 / 工具调用返回的数据。

    这个历史海报智能体的消息里通常会有一条 type=tool_response，
    里面包含 output/url 等字段，海报图片链接通常就在这里。
    """
    for message in messages:
        if getattr(message, "type", "") != "tool_response":
            continue
        try:
            return json.loads(getattr(message, "content", "") or "{}")
        except json.JSONDecodeError:
            return {}
    return {}


def extract_answer_markdown(messages):
    """
    提取智能体最终输出的正文答案。

    这部分通常包含：
    - 海报标题
    - 历史信息总结
    - Markdown 形式的图片链接
    """
    for message in messages:
        if getattr(message, "type", "") == "answer":
            return getattr(message, "content", "") or ""
    return ""


def extract_follow_ups(messages):
    """
    提取智能体给出的后续追问建议。

    前端会把这些建议渲染成可点击按钮，方便用户继续生成相关内容。
    """
    suggestions = []
    for message in messages:
        if getattr(message, "type", "") == "follow_up":
            text = (getattr(message, "content", "") or "").strip()
            if text:
                suggestions.append(text)
    return suggestions[:3]


def extract_links_from_markdown(text):
    """
    从 Markdown / 普通文本中抓取 URL。

    有些图片链接不一定只出现在 tool_response 里，也可能出现在 answer 文本里，
    所以这里作为第二层兜底解析。
    """
    return re.findall(r"https?://[^\s)>\"]+", text or "")


def choose_poster_url(tool_payload, answer_markdown):
    """
    从工具返回结果和正文中挑出最像“海报图片”的链接。

    优先从 tool_response 中的 url / output 字段取，
    如果没有，再从 answer_markdown 里提取图片 URL。
    """
    url_candidates = []

    for key in ("url", "output"):
        value = tool_payload.get(key, [])
        if isinstance(value, list):
            url_candidates.extend(value)
        elif isinstance(value, str):
            url_candidates.append(value)

    url_candidates.extend(extract_links_from_markdown(answer_markdown))

    for url in url_candidates:
        if isinstance(url, str) and url.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            return url
    return ""


def extract_title(answer_markdown, topic):
    """
    从智能体正文里提取海报标题。

    由于模型输出格式不完全固定，这里做了两层处理：
    1. 先找明确写了“海报标题”的行
    2. 再回退到 Markdown 的 ### 标题行
    3. 如果还是拿不到，就用“主题 + 历史海报”兜底
    """
    lines = [line.strip() for line in (answer_markdown or "").splitlines() if line.strip()]

    for line in lines:
        if "海报标题" in line:
            clean = line.replace("**", "")
            clean = re.sub(r"^#+\s*", "", clean)
            clean = clean.replace("海报标题", "").replace("：", "").replace(":", "").strip()
            if clean:
                return clean

    for line in lines:
        if line.startswith("###"):
            clean = re.sub(r"^#+\s*", "", line)
            clean = clean.replace("**", "").replace("海报标题", "").replace("：", "").replace(":", "").strip()
            if clean and clean not in ("历史海报展示", "海报展示") and "核心历史信息总结" not in clean and "历史海报资源" not in clean:
                return clean

    return f"{topic} 历史海报"


def build_user_prompt(topic):
    """
    统一构造给智能体的用户提示词。

    这里把需求写清楚：既要生成海报，也要给出标题和历史总结。
    """
    return (
        "请根据以下历史人物、事件或典故生成一张历史海报，"
        "并给出一个简短标题以及几条核心历史信息总结："
        f"{topic}"
    )


def generate_history_poster(topic):
    """
    生成历史海报的主流程。

    这也是整个后端的核心函数，步骤：
    1. 创建 Coze 客户端
    2. 确定要调用的 bot_id
    3. 发送用户输入给智能体
    4. 等待对话完成
    5. 解析图片、标题、正文总结、追问建议
    6. 返回前端需要的统一结构
    """
    coze = create_coze_client()
    bot_id = resolve_bot_id(coze)

    chat = coze.chat.create(
        bot_id=bot_id,
        user_id=DEFAULT_USER_ID,
        additional_messages=[
            Message(
                role="user",
                content=build_user_prompt(topic),
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
    tool_payload = extract_tool_payload(messages)
    answer_markdown = extract_answer_markdown(messages)
    follow_ups = extract_follow_ups(messages)
    poster_url = choose_poster_url(tool_payload, answer_markdown)

    if not poster_url:
        raise RuntimeError("智能体已返回结果，但未解析到海报图片链接。")

    return {
        "success": True,
        "bot_id": bot_id,
        "topic": topic,
        "title": extract_title(answer_markdown, topic),
        "poster_url": poster_url,
        "answer_markdown": answer_markdown,
        "follow_ups": follow_ups,
        "share_url": "https://www.coze.cn/s/2WE1oD02fmY/",
    }


@app.route("/")
def index():
    # 直接返回单文件前端页面。
    return send_file(ROOT_DIR / "index.html")


@app.route("/api/config")
def get_config():
    """
    给前端提供静态配置：
    - 智能体名称
    - 智能体分享链接
    - 几个可直接点击的输入示例
    """
    return jsonify(
        {
            "success": True,
            "bot_name": TARGET_BOT_NAME,
            "share_url": "https://www.coze.cn/s/2WE1oD02fmY/",
            "examples": [
                "岳飞精忠报国",
                "郑和下西洋",
                "丝绸之路的开辟",
                "玄奘西行取经",
            ],
        }
    )


@app.route("/api/generate-poster", methods=["POST"])
def generate_poster():
    """
    前端生成海报时调用的主接口。

    请求体：
    {
      "topic": "岳飞精忠报国"
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        topic = (data.get("topic") or "").strip()

        if not topic:
            return jsonify({"success": False, "error": "请输入历史人物、事件或典故。"}), 400

        result = generate_history_poster(topic)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
