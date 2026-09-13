from app.rag.rag import get_vector_db
from app.rag.embedding import get_embedding_service
from datetime import datetime, timedelta

class VectorMemory:
    """
    长期记忆管理器（基于VectorDB + EmbeddingService）

    职责：
    - 保存对话摘要到向量数据库
    - 根据当前问题语义检索相关历史
    - 管理用户画像/偏好

    设计决策：
    - 复用VectorDB类，避免重复实现ChromaDB操作
    - 复用EmbeddingService类，使用BGE-M3模型进行向量化
    - 集合名称：user_memories
    - 距离算法：cosine（余弦相似度，适合文本语义匹配）
    """

    def __init__(self):
        """初始化VectorMemory，复用VectorDB和EmbeddingService单例"""
        self.vector_db = get_vector_db()
        self.embedding_service = get_embedding_service()
        self.collection = self.vector_db.get_or_create_collection(
            name="user_memories",
            metadata={"hnsw:space": "cosine"}    # 距离算法：cosine（余弦相似度，适合文本语义匹配）
        )

    async def save_memory(self, user_id: str, content: str, topic: str, session_id: str, memory_type: str = "conversation_summary"
    ) -> str:
        """
        保存对话摘要到ChromaDB长期记忆
        将对话内容向量化后存储到user_memories集合
        每条记忆都有唯一ID(user:{user_id}:memory:{timestamp})
        :param user_id:
        :param content:
        :param topic:
        :param session_id:
        :param memory_type:
        :return: 记忆ID(user:{user_id}:memory:{timestamp})
        """
        """保存记忆到向量库（使用BGE-M3向量化）"""
        memory_id = f"user:{user_id}:memory:{int(datetime.now().timestamp())}"
        # 使用EmbeddingService进行向量化
        embeddings = self.embedding_service.embed_documents([content])
        now = datetime.now()
        self.vector_db.add_documents(
            collection=self.collection,
            documents=[content],
            metadatas=[{
                "user_id": user_id,
                "topic": topic,
                "created_at": now.isoformat(),
                "created_timestamp": now.timestamp(),
                "session_id": session_id,
                "memory_type": memory_type,
            }],
            ids=[memory_id],
            embeddings=embeddings
        )
        return memory_id

    async def search_memory(self, user_id: str, query: str, n_results: int = 5, max_age_days: int = 90) -> list[dict]:
        """
        根据当前问题语义检索相关历史记忆(带时效性权重)
        使用ChromaDB向量检索找到与当前问题最相关的历史对话摘要
        并结合时间衰减机制计算最终分数，确保返回最新且最相关的结果
        :param user_id: 用户ID，只检索该用户的历史记忆
        :param query: 当前用户问题，用于语义匹配
        :param n_results: 返回的最大结果数
        :param max_age_days: 检索的最大时间返回
        :return: 记忆列表，按相关性降序排列
        """
        # 时间边界，当前时间 - 最大时间
        cutoff_timestamp = (datetime.now() - timedelta(days=max_age_days)).timestamp()
        # 只检索时间边界之后创建的记忆，90天前的旧记忆会被过滤掉
        # 使用EmbeddingService进行查询向量化
        query_embedding = self.embedding_service.embed_query(query)
        results = self.vector_db.query(
            collection=self.collection,
            query_embedding=query_embedding,
            n_results=n_results,
            where={
                "$and": [
                    {"user_id": user_id},
                    {"created_timestamp": {"$gte": cutoff_timestamp}}
                ]
            }
        )

        memories = []
        if results and results.get("documents"):    # 检查结果是否有效
            for i, doc in enumerate(results["documents"][0]):
                metadata = results["metadatas"][0][i]
                distance = results["distances"][0][i]
                similarity = 1 - distance    # 1-距离度=相似度
                created_at = datetime.fromisoformat(metadata["created_at"])
                # 计算记忆年龄(天)
                days_old = (datetime.now() - created_at).days
                # 时间衰减：30天半衰期
                time_decay = 1 / (1 + days_old / 30)
                # 最终分数：语义相似度70% + 时效性30%
                final_score = similarity * 0.7 + time_decay * 0.3

                memories.append({
                    "content": doc,    # 对话摘要内容
                    "topic": metadata["topic"],    # 对话主题
                    "created_at": metadata["created_at"],    # 创建时间
                    "score": final_score,    # 最终分数
                    "similarity": similarity,    # 语义相似度
                    "time_decay": time_decay,    # 时间衰减因子
                })
        memories.sort(key=lambda x: x["score"], reverse=True)
        return memories

    async def update_user_preference(self, user_id: str, preference_key: str, preference_value: str
    ) -> None:
        """
        更新用户画像/偏好（使用BGE-M3向量化）
        将用户偏好存储到ChromaDB，使用固定格式ID确保同一偏好可以被更新。
        如果偏好已存在则更新，不存在则新增。
        :param user_id: 用户ID
        :param preference_key: 偏好键名，"preferred_color", "favorite_category"
        :param preference_value: 偏好值，如 "红色", "电子产品"
        :return: None
        """
        memory_id = f"user:{user_id}:preference:{preference_key}"
        existing = self.vector_db.get_documents_by_id(self.collection, [memory_id])
        # 使用EmbeddingService进行向量化
        embeddings = self.embedding_service.embed_documents([f"{preference_key}: {preference_value}"])
        now = datetime.now()
        # 已存在：更新文档内容和元数据
        if existing and existing["ids"]:
            self.vector_db.update_documents(
                collection=self.collection,
                ids=[memory_id],
                documents=[f"{preference_key}: {preference_value}"],
                metadatas=[{
                    "user_id": user_id,
                    "topic": "user_preference",
                    "created_at": now.isoformat(),
                    "created_timestamp": now.timestamp(),
                    "memory_type": "user_preference",
                    "preference_key": preference_key,
                }],
                embeddings=embeddings
            )
        else:    # 新增文档
            self.vector_db.add_documents(
                collection=self.collection,
                documents=[f"{preference_key}: {preference_value}"],
                metadatas=[{
                    "user_id": user_id,
                    "topic": "user_preference",
                    "created_at": now.isoformat(),
                    "created_timestamp": now.timestamp(),
                    "memory_type": "user_preference",
                    "preference_key": preference_key,
                }],
                ids=[memory_id],
                embeddings=embeddings
            )

_vector_memory_instance = None

def get_vector_memory() -> VectorMemory:
    global _vector_memory_instance
    if _vector_memory_instance is None:
        _vector_memory_instance = VectorMemory()
    return _vector_memory_instance