from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from app.utils.api_caller import call_api
from app.schemas.tools import ProductSearchParams

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

@tool
async def get_browse_history(api: str, method: str, config: RunnableConfig) -> str:
    """
    获取用户的浏览历史记录。

    当需要了解用户浏览偏好、分析用户兴趣时使用此工具。
    返回格式化的浏览记录，按日期分组显示浏览过的商品。
    最多返回5天的浏览记录，每天最多显示5个商品。

    Args:
        api: API端点路径，从map_user_intent获取，例如 "/api/browse/"
        method: HTTP请求方法，从map_user_intent获取，例如 "POST"
        config: RunnableConfig，包含用户认证token
    """
    token = config.get('configurable', {}).get('token')
    try:
        result = await call_api(api, token=token, method=method)
        if not result:
            return "暂无浏览记录"
        browse_list = []
        for record in result[:5]:
            date = record.get('date', '未知')
            skus = record.get('skus', [])
            sku_list = []
            for sku in skus[:5]:    # 每天最多显示5个商品
                name = sku.get('name', '未知商品')
                price = sku.get('price', 0)
                sku_list.append(f"  - {name} ({price}元)")
            if len(skus) > 5:
                sku_list.append(f"  ...等{len(skus)}件商品")
            browse_list.append(f"{date}:\n" + "\n".join(sku_list))
        return "浏览记录：\n" + "\n".join(browse_list)
    except Exception as e:
        return f"获取浏览记录失败：{str(e)}"

@tool
async def search_products(api: str, method: str, params: ProductSearchParams, config: RunnableConfig) -> str:
    """
    搜索商品信息。

    当用户请求推荐商品、查找特定商品时使用此工具。
    支持关键词搜索、价格区间筛选和多种排序方式。
    返回格式化的商品列表，包含名称、价格、销量和评论数。

    Args:
        api: API端点路径，从map_user_intent获取，例如 "/api/search/"
        method: HTTP请求方法，从map_user_intent获取，例如 "GET"
        params: ProductSearchParams模型，包含以下可选参数：
            - keyword: 搜索关键词（如"手机"、"笔记本"
            - category: 商品分类（如"手机"、"电脑"）
            - ordering: 排序方式（comments-评论数, sales-销量, price-价格）
            - min_price: 最低价格（如250
            - max_price: 最高价格（如350）
            - page: 页码（默认1）
            - page_size: 每页数量（默认20）
        config: RunnableConfig，包含用户认证token
    """
    token = config.get('configurable', {}).get('token')
    try:
        # 将模型实例转换为查询参数字典，跳过使用默认值的字段。
        query_params = params.model_dump(exclude_unset=True)
        result = await call_api(api, token=token, params=query_params)
        skus = result.get('skus', [])
        if not skus:
            return "未找到相关商品"
        skus_list = []
        for sku in skus[:10]:    # 最多显示10个
            skus_list.append(
                f"- {sku.get('name', '未知商品')}\n"
                f"  价格: {sku.get('price', 0)}元\n"
                f"  销量: {sku.get('sales', 0)}\n"
                f"  评论数: {sku.get('comments', 0)}"
            )
        total = result.get('total', len(skus))
        return f"共找到{total}件商品：\n" + "\n".join(skus_list)
    except Exception as e:
        return f"搜索商品失败：{str(e)}"


@tool
async def get_order_detail(api: str, method: str, config: RunnableConfig) -> str:
    """
    获取单个订单的详细信息。

    当用户询问特定订单状态、订单详情时使用此工具。
    返回格式化的订单详情，包含订单号、状态、支付方式、金额、时间、地址和商品列表。

    Args:
        api: API端点路径，从map_user_intent获取，例如 "/api/orders/{order_id}/"
        method: HTTP请求方法，从map_user_intent获取，例如 "GET"
        config: RunnableConfig，包含用户认证token
    """
    token = config.get('configurable', {}).get('token')
    try:
        result = await call_api(api, token=token)

        order = result
        if not order or 'order_id' not in order:
            return "未找到订单信息"

        amount = order.get('final_amount', 0)
        status_text = order.get('status_text', '未知')
        pay_method = order.get('pay_method_text', '未知')

        # 格式化商品列表
        skus = order.get('skus', [])
        sku_list = []
        for sku in skus:
            sku_list.append(
                f"  - {sku.get('sku_name', '未知商品')}\n"
                f"    数量: {sku.get('count', 1)}\n"
                f"    单价: {sku.get('price', 0)}元"
            )

        output = (
                f"订单号: {order.get('order_id', '未知')}\n"
                f"状态: {status_text}\n"
                f"支付方式: {pay_method}\n"
                f"总金额: {amount}元\n"
                f"下单时间: {order.get('create_time', '未知')}\n"
                f"收货地址: {order.get('receiver_address', '未知')}\n"
                f"商品列表:\n" + "\n".join(sku_list)
        )

        return output
    except Exception as e:
        return f"获取订单详情失败: {str(e)}"

@tool
async def get_product_detail(api: str, method: str, config: RunnableConfig) -> str:
    """
    获取单个商品的详细信息。

    当用户询问特定商品详情、规格参数时使用此工具。
    返回格式化的商品详情，包含名称、系列、价格、库存、销量和规格参数。

    Args:
        api: API端点路径，从map_user_intent获取，例如 "/api/goods/{sku_id}/"
        method: HTTP请求方法，从map_user_intent获取，例如 "GET"
        config: RunnableConfig，包含用户认证token
    """
    token = config.get('configurable', {}).get('token')
    try:
        result = await call_api(api, token=token, method=method)

        product = result
        if not product or 'name' not in product:
            return "未找到商品信息"

        price = product.get('price', 0)
        stock = product.get('stock', 0)

        # 格式化规格信息
        specs = product.get('specs', [])
        spec_list = []
        for spec in specs:
            options = [opt['value'] for opt in spec.get('options', [])]
            spec_list.append(f"  {spec.get('name', '未知')}: {'/'.join(options)}")

        # SPU信息
        spu = product.get('spu', {})
        spu_name = spu.get('name', '未知')

        output = (
                f"商品名称: {product.get('name', '未知')}\n"
                f"系列: {spu_name}\n"
                f"价格: {price}元\n"
                f"库存: {stock}件\n"
                f"销量: {product.get('sales', 0)}\n"
                f"规格参数:\n" + "\n".join(spec_list)
        )

        return output
    except Exception as e:
        return f"获取商品详情失败: {str(e)}"