import httpx

_client: httpx.AsyncClient | None = None

# 连接池配置
_LIMITS = httpx.Limits(
    max_connections=100,    # 最大连接数
    max_keepalive_connections=20,    # 保持活跃连接数
    keepalive_expiry=30,    # 保持活跃连接超时(秒)
)

_TIMEOUT = httpx.Timeout(30.0)    # 请求超时30秒

def get_http_client() -> httpx.AsyncClient:
    """
    获取全局共享的httpx客户端(单例)
    利用连接池复用TCP连接，避免每次请求都创建新连接
    :return: httpx.AsyncClient实例
    """
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=_TIMEOUT,
            limits=_LIMITS,
        )
    return _client

async def close_http_client():
    """应用关闭时释放HTTP连接池"""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None