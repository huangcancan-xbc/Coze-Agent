# Coze Idiom Duel Demo

一个使用 Coze Python SDK 和 Flask 搭建的成语接龙智能体 Demo。

项目特点：
- 智能体参与成语接龙
- 单文件前端页面 `index.html`
- Flask 后端接口驱动
- 支持重开一局和回合记录展示

## 运行环境

- Python 3.10+
- Coze API Token
- Coze Bot ID

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置环境变量

复制 `.env.example` 为 `.env`，然后填写你自己的配置：

```env
COZE_API_TOKEN=your_token_here
BOT_ID=your_bot_id_here
USER_ID=test_user_001
```

说明：
- `COZE_API_TOKEN`：Coze OpenAPI 个人访问令牌
- `BOT_ID`：你的 Coze 智能体 ID
- `USER_ID`：你自己定义的用户标识，用来区分对话

## 启动项目

```bash
python app.py
```

浏览器打开：

```text
http://127.0.0.1:5000
```
