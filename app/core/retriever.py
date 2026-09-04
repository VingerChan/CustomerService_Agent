import asyncio
from typing import Optional
from app.core.embedding import get_embedding_service
from app.core.rag import get_vector_db

class HybridRetriever:
    def __init__(self):
        self.vector_db = get_vector_db()
        self.embedding_service = get_embedding_service()
    async def vector_search(self, collection_name: str , query: str, n_results: int = 5) -> dict:
        """
        异步向量检索：基于语义相似度。用Embedding模型将query转换为更加精准的向量，再在向量数据库查询
        :param collection_name: 集合名称
        :param query:
        :param n_results: 返回的结果数量，默认5
        :return:
        """
        def _sync_search():
            # 获取或创建集合
            collection = self.vector_db.get_or_create_collection(collection_name)
            # 将查询文本向量化
            query_embedding = self.embedding_service.embed_query(query)
            # 在ChromaDB中查询相似向量
            return self.vector_db.query(collection=collection, query_embedding=query_embedding, n_results=n_results)
        # 将同步操作放到线程池执行，不阻塞事件循环
        return await asyncio.to_thread(_sync_search)

# 全局单例实例
_retriever_instance: Optional[HybridRetriever] = None

def get_retriever() -> HybridRetriever:
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = HybridRetriever()
    return _retriever_instance