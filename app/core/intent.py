from app.core.updater import get_updater
from app.core.retriever import get_retriever
from typing import Optional

class IntentMapper:
    """
    意图映射模块：
    · 通过Updater将API文档向量化存入ChromaDB
    · 通过Retriever根据用户查询检索匹配的API文档
    """
    COLLECTION_NAME = 'api_docs'
    def __init__(self):
        self.updater = get_updater()
        self.retriever = get_retriever()
    async def load_api_docs(self, docs: list[dict]) -> int:
        """
        加载API文档到向量数据库
        :param docs: API文档列表
        :return: 成功加载的文档数量
        """
        if not docs:
            return 0
        documents = [doc['description'] for doc in docs]
        metadatas = [
            {
                'endpoint': doc['endpoint'],
                'method': doc['method'],
            }
            for doc in docs
        ]
        ids = [doc['id'] for doc in docs]
        # 委托给Updater执行全量更新
        await self.updater.full_update(self.COLLECTION_NAME, documents, metadatas, ids)
        return len(ids)
    async def map_intent(self, query: str, n_results: int = 3) -> dict:
        """
        异步意图检索：根据用户查询匹配API文档
        :param query:
        :param n_results:
        :return:
        """
        return await self.retriever.hybrid_search(self.COLLECTION_NAME, query, n_results)
    async def get_api_endpoints(self, query: str, n_results: int = 3) -> list[dict]:
        """
        获取匹配的API端点列表(格式化输出)，将ChromaDB原始结果转换为友好的字典列表
        {'ids':[[]],'metadatas':[[]],'documents':[[]],'scores':[[]]}
        :param query: 用户查询文本
        :param n_results: 返回数量
        :return: API端点列表
        """
        results = await self.map_intent(query, n_results)
        endpoints = []
        if results and results.get('metadatas'):
            for i, metadata in enumerate(results['metadatas'][0]):
                endpoints.append({
                    'id': results['ids'][0][i],
                    'endpoint': metadata['endpoint'],
                    'method': metadata['method'],
                    'description': results['documents'][0][i],
                    'score': results['scores'][0][i] if results.get('scores') else None,
                })
        return endpoints

_intent_mapper_instance: Optional[IntentMapper] = None

def get_intent_mapper() -> IntentMapper:
    """获取IntentMapper单例实例"""
    global _intent_mapper_instance
    if _intent_mapper_instance is None:
        _intent_mapper_instance = IntentMapper()
    return _intent_mapper_instance