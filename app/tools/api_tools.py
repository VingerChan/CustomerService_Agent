from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from app.utils.api_caller import call_api

@tool
async def get_orders(api: str, method: str, config: RunnableConfig) -> str:
    """
    获取用户的历史订单列表。

    当需要了解用户购买历史、分析用户偏好时使用此工具。
    返回格式化的订单列表，包含订单号、状态和商品摘要。
    最多返回10条订单记录。

    Args:
        api: API端点路径，从map_user_intent获取，例如 "/api/orders/"
        method: HTTP请求方法，从map_user_intent获取，例如"GET"
        config: RunnableConfig，包含用户认证token
    """
    token = config.get('configurable', {}).get('token')
    try:
        result = await call_api(api, token=token, method=method)
        orders = result.get('orders', [])
        if not orders:
            return "暂无订单记录"
        order_list = []
        for order in orders[:10]:    # 最多显示10个
            order_id = order.get('order_id', '未知')
            status_text = order.get('status_text', '未知')
            # 格式化商品列表
            skus = order.get('skus', [])
            sku_names = [sku.get('sku_name', '未知商品') for sku in skus]
            sku_summary = ','.join(sku_names[:3])    # 每个订单最多完整显示3个商品
            if len(sku_names) > 3:
                sku_summary += f"等{len(sku_names)}件商品"
            order_list.append(
                f"- 订单号：{order_id}\n"
                f"  状态：{status_text}\n"
                f"  商品：{sku_summary}"
            )
        total = result.get('total', len(orders))
        return f"订单列表 (共{total}条)： \n" + "\n".join(order_list)
    except Exception as e:
        return f"获取订单列表失败：{str(e)}"