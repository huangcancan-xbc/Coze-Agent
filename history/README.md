# Coze History Poster Demo

一个使用 Coze Python SDK 和 Flask 搭建的历史海报生成 Demo。

项目特点：
- 输入历史人物、事件或典故，生成对应海报
- 后端通过 Coze SDK 调用“历史海报制作”智能体
- 单文件前端页面 `index.html`
- 返回海报图片、标题、历史信息总结和追问建议

## 运行环境

- Python 3.10+
- Coze API Token
- Coze Bot ID（可选）

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置环境变量

在项目目录下创建 `.env`，填写你的配置：

```env
COZE_API_TOKEN=your_token_here
BOT_ID=your_bot_id_here
USER_ID=history_poster_demo
```

说明：
- `COZE_API_TOKEN`：Coze OpenAPI 个人访问令牌
- `BOT_ID`：历史海报智能体的 Bot ID
- `USER_ID`：你自己定义的用户标识，用来隔离对话上下文

补充：
- 当前代码已经做了兜底处理
- 如果 `.env` 里的 `BOT_ID` 缺失或填错，程序会尝试按智能体名称“历史海报制作”自动查找

## 启动项目

```bash
python app.py
```

浏览器打开：

```text
http://127.0.0.1:5000
```

## 接入智能体

- Coze 分享链接：https://www.coze.cn/s/2WE1oD02fmY/
- 默认目标智能体名称：`历史海报制作`

## 项目结构

- `app.py`：Flask 后端与 Coze SDK 调用逻辑
- `index.html`：前端页面，包含 HTML / CSS / JS
- `requirements.txt`：Python 依赖
- `演示效果.mp4`：本地演示视频

## 接口说明

### `GET /api/config`

返回前端初始化所需配置：
- 智能体名称
- Coze 分享链接
- 示例历史主题

### `POST /api/generate-poster`

请求示例：

```json
{
  "topic": "岳飞精忠报国"
}
```

返回内容：
- 海报图片链接
- 海报标题
- 历史信息总结
- 后续追问建议