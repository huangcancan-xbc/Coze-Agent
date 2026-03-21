# Coze Animal Video Demo

一个使用 Coze Python SDK 和 Flask 搭建的动物视频生成 Demo。

项目特点：
- 输入动物相关描述，生成对应视频
- 后端通过 Coze SDK 调用“动物视频生成”智能体
- 前端拆分为 `index.html`、`styles.css`、`app.js`
- 支持返回视频链接、补充说明和追问建议
- 对“大请求”和“服务繁忙”做了友好提示

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
USER_ID=animal_video_demo
```

说明：
- `COZE_API_TOKEN`：Coze OpenAPI 个人访问令牌
- `BOT_ID`：动物视频生成智能体的 Bot ID
- `USER_ID`：你自己定义的用户标识，用来隔离对话上下文

补充：
- 当前代码已经做了兜底处理
- 如果 `.env` 里的 `BOT_ID` 缺失或填错，程序会尝试按智能体名称“动物视频生成”自动查找

## 启动项目

```bash
python app.py
```

浏览器打开：

```text
http://127.0.0.1:5000
```

## 接入智能体

- Coze 页面链接：https://www.coze.cn/store/agent/7619592811435982889?from = store_search_suggestion&bid = 6jfi6shrs200r
- 默认目标智能体名称：`动物视频生成`

## 项目结构

- `app.py`：Flask 后端与 Coze SDK 调用逻辑
- `index.html`：前端页面结构
- `styles.css`：前端样式
- `app.js`：前端交互逻辑
- `requirements.txt`：Python 依赖
- `演示效果.mp4`：本地演示视频

## 错误处理

当前项目对以下常见问题做了明确提示：

- 输入为空：提示用户先输入描述
- 请求过大：返回 `当前请求过大，请稍后再试`
- 服务繁忙：返回 `当前视频生成服务繁忙，请稍后再试`
- 其他插件错误：返回通用失败提示

>**重要事项说明：如果运行失败是正常现象！也不知道怎么回事，早上 12:00 前测试还是没什么问题，做了多次测试都是正常且能预览到视频的，但是中午及以后总是失败，就如视频演示的那样，在工作流中用于生成视频的插件访问量太大（`{  "$error": "status_code=429, body={\"error\":{\"code\":\"1305\",\"message\":\"该模型当前访问量过大，请您稍后再试\"}}" }`），导致我后续的测试中总是失败，所以发布的应用和 SDK 的 web 应用没有经过测试，可能存在 bug，但是发布的智能体是正常的（可以正常使用，但也还是受限访问，测试不多）。**

