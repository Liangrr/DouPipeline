import asyncio
import os
from browser_use import Agent
from browser_use.llm.openai.chat import ChatOpenAI

# 1. 配置大模型 API Key 和 Base URL
os.environ["OPENAI_API_KEY"] = "tp-c1g7nehvjiv148ml2rsiv09eanuee3culvm2nkudmr4it3fc"
BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"

async def main():
    # 2. 初始化大模型
    llm = ChatOpenAI(model="mimo-v2.5", base_url=BASE_URL)
    
    # 3. 创建 Agent，并用“大白话”直接下达任务
    agent = Agent(
        task="去 Github 搜索 'browser-use' 仓库，告诉我它现在有多少个 Star，并把网页截个图。",
        llm=llm,
    )
    
    # 4. 让 AI 开始在浏览器里狂飙
    result = await agent.run()
    print(result)

# 运行异步主函数
asyncio.run(main())