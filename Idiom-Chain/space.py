# 导入功能模块
import os
from cozepy import Coze, TokenAuth, COZE_CN_BASE_URL
# 加载环境变量
from dotenv import load_dotenv

# 兼容 Windows 下可能保存成 UTF-8 BOM 的 .env 文件
load_dotenv(encoding="utf-8-sig")


# 获取工作空间的列表
def get_space_list():

    # 声明访问令牌
    api_token = os.environ.get('COZE_API_TOKEN')

    if not api_token:
        print("请先设置个人令牌")
        return

    # 初始化 coze 的客户端
    coze = Coze(
        # 声明令牌
        auth = TokenAuth(token = api_token),
        # 声明域名
        base_url = COZE_CN_BASE_URL

    )

    # 创建coze客户端之后就能进行调用了
    try:
        spaces = coze.workspaces.list()
        
        if hasattr(spaces, "items"):
            spaces = spaces.items

        print(spaces)


    except Exception as e:
        print(f"调用访问空间列表SDK失败：{str(e)}")


if __name__ == '__main__':
    get_space_list()
