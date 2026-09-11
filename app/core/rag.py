import os
from typing import Optional
from dotenv import load_dotenv
import chromadb

load_dotenv()

class VectorDB:
    """
    向量数据库封装类
    职责：
    · 初始化ChromaDB客户端
    · 创建和管理集合(Collection)
    · 提供文档添加和查询借口
    设计决策：
    · 使用PersistentClient：数据持久化到磁盘，服务重启后数据不丢失
    · 单例模式：全局只有一个VectorDB实例，避免重复初始化
    """
    def __init__(self):
        # PersistentClient会将数据写入磁盘，而Client仅在内存中，服务重启后数据丢失
        self.client = chromadb.PersistentClient(path=os.getenv('CHROMADB_PATH'))
    def get_or_create_collection(self, name: str, metadata: Optional[dict] = None) -> chromadb.Collection:    # ChromaDB中的Collection相当于关系型数据库中的表
        """
        获取或创建集合
        :param name: 集合名称，如products、api_docs
        :param metadata: 集合元数据，可指定距离
        :return:
        """
        if metadata is None:
            # 指定HNSW索引的距离算法
            # cosine：余弦相似度，适合文本语义匹配  l2：欧氏距离，适合数据特征  ip：内积，适合推荐系统
            metadata = {'hnsw:space': 'cosine'}
        return self.client.get_or_create_collection(name=name, metadata=metadata)
    def add_documents(self,collection: chromadb.Collection, documents: list[str], metadatas: list[dict], ids: list[str], embeddings: Optional[list[list[float]]] = None):
        """
        向集合中添加文档
        :param collection: 目标集合
        :param documents: 文档内容列表，如商品描述
        :param metadatas: 元数据列表，如商品价格、分类
        :param ids: 文档ID列表，必须唯一
        :param embeddings: 预计算的向量(可选)，不传则自动计算
        :return:
        """
        add_kwargs = {
            'documents': documents,
            'metadatas': metadatas,
            'ids': ids,
        }
        # 如果提供了预计算的embedding
        if embeddings is not None:
            add_kwargs['embeddings'] = embeddings
        collection.add(**add_kwargs)
    def query(self,collection: chromadb.Collection, query_text: Optional[str] = None, query_embedding: Optional[list[float]] = None, n_results: int = 5, where: Optional[dict] = None, where_document: Optional[dict] = None) -> dict:
        """
        查询相似文档
        :param collection: 目标集合
        :param query_text: 查询文本(会自动embedding)
        :param query_embedding: 预计算的查询向量
        :param n_results: 返回的结果数量，默认5
        :param where: 元数据过滤条件
        :param where_document: 文档过滤内容
        :return: distances，便于判断结果质量
        """
        query_kwargs = {
            'n_results': n_results,
        }
        # 查询方式：文本或向量
        if query_text is not None:
            query_kwargs['query_texts'] = [query_text]
        elif query_embedding is not None:
            query_kwargs['query_embeddings'] = [query_embedding]
        else:    # 两个参数二选一
            raise ValueError('必须提供query_text或query_embedding')
        # 元数据过滤
        if where is not None:
            query_kwargs['where'] = where
        # 文档内容过滤
        if where_document is not None:
            query_kwargs['where_document'] = where_document
        return collection.query(**query_kwargs)
    def delete_collection(self, name: str):
        """
        删除集合
        :param name: 集合名称
        :return:
        """
        self.client.delete_collection(name=name)
    def get_collection(self, name: str) -> chromadb.Collection:
        """
        获取已有集合
        :param name: 集合名称
        :return: chromadb.Collection 集合对象
        """
        try:
            return self.client.get_collection(name=name)
        except Exception as e:
            raise ValueError(f"集合 {name} 不存在：{str(e)}")
    def get_collection_count(self, name: str) -> int:
        """
        获取集合中文档数量
        :param name: 集合名称
        :return: 文档数量
        """
        collection = self.get_collection(name=name)
        return collection.count()

    def get_documents_by_id(self, collection: chromadb.Collection, ids: list[str]) -> dict:
        """
        根据ID获取文档
        :param collection: 目标集合
        :param ids: 文档ID列表
        :return: 文档数据
        """
        return collection.get(ids=ids)

    def update_documents(
        self,
        collection: chromadb.Collection,
        ids: list[str],
        documents: Optional[list[str]] = None,
        metadatas: Optional[list[dict]] = None
    ):
        """
        更新文档
        :param collection: 目标集合
        :param ids: 要更新的文档ID列表
        :param documents: 新的文档内容（可选）
        :param metadatas: 新的元数据（可选）
        """
        update_kwargs = {"ids": ids}
        if documents is not None:
            update_kwargs["documents"] = documents
        if metadatas is not None:
            update_kwargs["metadatas"] = metadatas
        collection.update(**update_kwargs)

    def delete_documents(self, collection_name: str, ids: list[str]):
        """
        从集合中删除指定ID的文档
        :param collection_name: 集合名称
        :param ids: 要删除的文档ID列表
        :return:
        """
        collection = self.get_or_create_collection(name=collection_name)
        collection.delete(ids=ids)

# 全局单例实例
_vector_db_instance: Optional[VectorDB] = None
def get_vector_db() -> VectorDB:
    """
    获取VectorDB单例实例(FastAPI依赖注入用)
    :return:
    """
    global _vector_db_instance
    if _vector_db_instance is None:
        _vector_db_instance = VectorDB()
    return _vector_db_instance

