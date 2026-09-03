from FlagEmbedding import BGEM3FlagModel
from typing import Optional

class EmbeddingService:
    def __init__(self, model_name: str = 'BAAI/bge-m3', use_fp16 = True):
        """
        初始化BGE-M3向量化服务
        :param model_name: HuggingFace模型名称，BAAI/bge-m3是BAAI发布的多语言模型
        :param use_fp16: 是否使用半精度加速
            - GPU环境：开启后推理速度约2x，显存占用减半
            - CPU环境：自动回退到fp32，不影响结果准确性
        """
        self.model = BGEM3FlagModel(model_name, use_fp16=use_fp16)

    def embed_documents(self, documents: list[str], batch_size: int =12) -> list[list[float]]:
        """
        批量向量化文档列表
        :param documents: 文档文本列表
        :param batch_size: 每批处理的文档数量
        :return: 向量列表，每个向量1024维(BGE-M3的dense维度)
        """
        # BGE-M3最大支持 8192 tokens
        # BGE-M3返回字典包含dense_vecs(稠密向量) 和 sparse_vecs(稀疏向量)
        embeddings = self.model.encode(documents, batch_size=batch_size, max_length=8192)['dense_vecs']
        return embeddings.tolist()
    def embed_query(self, query: str) -> list[float]:
        """
        向量化单条查询文本
        :param query: 用户查询字符串
        :return: 1024维向量
        """
        embeddings = self.model.encode([query], max_length=8192)['dense_vecs']
        return embeddings[0].tolist()    # 取出唯一的向量

    def get_embedding_dim(self) -> int:
        """获取向量维度(BGE-M3为1024)"""
        return 1024

# 全局单例实例
# 延迟初始化，一开始设置成None，等用到再赋值
_embedding_service_instance: Optional[EmbeddingService] = None
def get_embedding_service() -> EmbeddingService:
    global _embedding_service_instance
    if _embedding_service_instance is None:
        _embedding_service_instance = EmbeddingService()
    return _embedding_service_instance