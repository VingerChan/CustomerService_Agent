import json
import os
import re
import logging

logger = logging.getLogger(__name__)

# =============================================
# 输入层注入检测正则
# =============================================
INJECTION_PATTERNS = [
    # 人格篡改
    r'(?i)ignore\s+(all\s+)?(previous|prior|above|earlier)\s+instructions',
    r'(?i)忽略(之前|以前|上面)(的)?(所有|全部)?(指令|规则|提示词|设定)',
    r'(?i)(你|您)(现在)?(是|变成|作为)(一个|一位)?',
    r'(?i)从现在起(你|您)',
    r'(?i)(忘记|忘掉)(你|您)(之前|以前)的(所有|全部)?',
    r'(?i)扮演',
    r'(?i)override\s+(system|instructions|rules)',
    r'(?i)forget\s+(everything|all|your)',
    # System Prompt 提取
    r'(?i)(print|output|show|reveal|display|tell|give)\s+(your|the)\s+(system\s*prompt|instructions|rules|config)',
    r'(?i)system\s*prompt',
    r'(?i)(你的|您的)(系统提示词|初始指令|配置信息|工作规则)',
    # 分隔符注入
    r'(?i)system\s*:\s*',
    r'(?i)new\s+system\s*prompt',
    r'```.*system',
    r'<!--.*-->',
    # 工具调用劫持
    r'/api/(admin|internal|system|debug|config|management)',
]

# =============================================
# 记忆内容清洗正则（比输入层宽松，只移除真正危险的）
# =============================================
MEMORY_INJECTION_PATTERNS = [
    r'(?i)ignore\s+(all\s+)?(previous|prior|above)\s+instructions',
    r'(?i)忽略(之前|以前|上面)(的)?(所有|全部)?(指令|规则)',
    r'(?i)system\s*:\s*',
    r'(?i)new\s+system\s*prompt',
    r'```.*system',
    r'<!--.*-->',
]

# =============================================
# 动态加载 API 白名单（从 api_docs.json 自动派生）
# =============================================
_api_whitelist: list[str] = []
_http_methods: set[str] = set()


def _load_api_whitelist():
    """从 api_docs.json 加载合法的 API 路径前缀和 HTTP 方法"""
    global _api_whitelist, _http_methods
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        api_docs_path = os.path.join(base_dir, 'data', 'api_docs.json')
        with open(api_docs_path, 'r', encoding='utf-8') as f:
            api_docs = json.load(f)

        prefixes = set()
        methods = set()
        for doc in api_docs:
            endpoint = doc.get('endpoint', '')
            method = doc.get('method', 'GET')
            clean_endpoint = re.sub(r'\{[^}]+\}', '', endpoint).rstrip('/')
            if clean_endpoint:
                prefixes.add(clean_endpoint)
            methods.add(method.upper())

        _api_whitelist = sorted(prefixes)
        _http_methods = methods
        logger.warning(f"[Sanitizer] 已加载 API 白名单: {_api_whitelist}")
    except Exception as e:
        logger.error(f"[Sanitizer] 加载 API 白名单失败: {e}")
        _api_whitelist = []
        _http_methods = {'GET', 'POST'}


_load_api_whitelist()


def detect_injection(text: str) -> tuple[bool, str]:
    """
    检测输入是否包含注入模式
    :return: (是否注入, 匹配到的模式)
    """
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text):
            return True, pattern
    return False, ""


def sanitize_input(text: str) -> str:
    """输入清洗：移除零宽字符和控制字符"""
    text = re.sub(r'[\u200b-\u200f\u2028-\u202f\u2060-\u2064\ufeff]', '', text)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text


def sanitize_memory_content(content: str) -> str:
    """清洗记忆内容：移除注入模式，保留完整上下文"""
    for pattern in MEMORY_INJECTION_PATTERNS:
        content = re.sub(pattern, '[已过滤]', content)
    return content


def validate_api_path(api: str) -> bool:
    """验证 API 路径是否在白名单内（前缀匹配）"""
    clean_api = re.sub(r'\{[^}]+\}', '', api).rstrip('/')
    return any(clean_api.startswith(prefix) for prefix in _api_whitelist)


def validate_http_method(method: str) -> bool:
    """验证 HTTP 方法是否合法"""
    return method.upper() in _http_methods


def strip_urls_from_message(text: str) -> str:
    """从用户消息中移除 URL 路径模式，防止 RAG 被路径名污染"""
    return re.sub(r'/api/\S+', '', text).strip()
