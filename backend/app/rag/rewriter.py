from openai import AsyncOpenAI
from app.config import settings

SYSTEM_PROMPT = (
    "你是一个查询改写助手。将用户关于 EVE Online 市场的口语化查询改写为可搜索的关键词。"
    "规则: 1. 保留所有物品名称、星系名称等专有名词 "
    "2. 补充隐含的上下文（如物品所属类别、交易用途）"
    "3. 只用中文关键词，空格分隔 4. 只输出改写后的查询，不要解释"
)


async def rewrite_query(user_query: str, context: str = "") -> str:
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if context:
        messages.append({"role": "user", "content": f"上下文: {context}\n用户查询: {user_query}"})
    else:
        messages.append({"role": "user", "content": f"用户查询: {user_query}"})
    response = await client.chat.completions.create(
        model="gpt-4o-mini", messages=messages, max_tokens=100, temperature=0.1,
    )
    return response.choices[0].message.content.strip()
