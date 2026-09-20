import asyncio
from typing import Optional
from app.rag.embedding import get_embedding_service
from app.rag.rag import get_vector_db
import jieba
from rank_bm25 import BM25Okapi

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
    async def keyword_search(self, collection_name: str, query: str,n_results:int = 5) -> dict:
        """
        关键词检索：获取所有文档——>jieba分词——>BM25计算得分——>返回top-N
        :param collection_name: 集合名称
        :param query: 查询文本
        :param n_results: 返回的结果数量
        :return:
        """
        def _sync_search():
            # 获取集合中所有的文档
            collection = self.vector_db.get_or_create_collection(collection_name)
            all_docs = collection.get()
            # jieba中文分词
            tokenized_query = list(jieba.cut(query))    # 对query文本进行分词
            tokenized_docs = [list(jieba.cut(doc)) for doc in all_docs['documents']]    # 对文档分词
            # BM25检索
            bm25 = BM25Okapi(tokenized_docs)    # 创建BM25索引
            scores = bm25.get_scores(tokenized_query)    # 计算query与每个文档的相关性得分
            # 返回top-N结果(按得分降序排列)
            top_indices = scores.argsort()[-n_results:][::-1]    # argsort()升序，[::-1]反转为降序
            return {
                'ids': [all_docs['ids'][i] for i in top_indices],
                'documents' : [all_docs['documents'][i] for i in top_indices],
                'metadatas' : [all_docs['metadatas'][i] for i in top_indices],
                'scores' : [float(scores[i]) for i in top_indices]
            }
        return await asyncio.to_thread(_sync_search)
    async def hybrid_search(self, collection_name: str, query: str, n_results: int = 5, vector_weight: float = 0.6, keyword_weight: float = 0.4) -> dict:
        """
        混合检索
        :param collection_name: 集合名称
        :param query: 查询文本
        :param n_results: 返回数量
        :param vector_weight: 向量检索权重 语义相似度结果占70%
        :param keyword_weight: 关键词检索权重 BM25关键词匹配结果占30%
        :return: top-N
        """
        # 并发执行两种检索，获取更多候选结果(2倍)
        vector_results, keyword_results = await asyncio.gather(
            self.vector_search(collection_name, query, n_results * 2),
            self.keyword_search(collection_name, query, n_results * 2)
        )
        # 归一化得分 到 [0, 1]区间
        def normalize(scores: list[float]) -> list[float]:
            if not scores:
                return []
            max_score = max(scores)
            if max_score == 0:
                return [0.0] * len(scores)
            return [score / max_score for score in scores]
        # 将ChromaDB返回的距离转换为相似度，再归一化
        raw_distances = vector_results.get('distances', [[]])[0] if vector_results.get(
            'distances') else [1.0] * n_results * 2
        vector_similarities = [1.0 - d / 2.0 for d in raw_distances]
        vector_scores = normalize(vector_similarities)
        keyword_scores = normalize(keyword_results.get('scores', []))
        """向量检索结果"""
        doc_scores = {}
        # 向量检索结果
        for i, doc_id in enumerate(vector_results.get('ids',[[]])[0]):
            doc_scores[doc_id] = {
                'score': vector_weight * vector_scores[i],
                'document': vector_results['documents'][0][i],
                'metadata': vector_results['metadatas'][0][i],
                'id': doc_id
            }
        # 关键词检索结果（累加得分）
        for i, doc_id in enumerate(keyword_results.get('ids', [])):
            if doc_id in doc_scores:    # 如果文档已被向量检索，那么关键词检索累加，使得分更高
                doc_scores[doc_id]['score'] += keyword_weight * keyword_scores[i]
            else:
                doc_scores[doc_id] = {
                    'score': keyword_weight * keyword_scores[i],
                    'document': keyword_results['documents'][i],
                    'metadata': keyword_results['metadatas'][i],
                    'id': doc_id,
                }
        # 4. 按融合得分降序排列，返回top-N
        sorted_docs = sorted(doc_scores.values(), key=lambda x: x['score'], reverse=True)[:n_results]
        return {
            'documents': [doc['document'] for doc in sorted_docs],
            'metadatas': [doc['metadata'] for doc in sorted_docs],
            'scores': [doc['score'] for doc in sorted_docs],
            'ids': [doc['id'] for doc in sorted_docs],
        }
# 全局单例实例
_retriever_instance: Optional[HybridRetriever] = None

def get_retriever() -> HybridRetriever:
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = HybridRetriever()
    return _retriever_instance