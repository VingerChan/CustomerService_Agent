import time
from datetime import datetime
from app.rag.embedding import get_embedding_service
from app.rag.rag import get_vector_db
import logging
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
fh = logging.FileHandler('logs/updater.log', encoding='utf-8')
fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(fh)


class UpdateStats:
    """更新统计信息"""
    def __init__(self):
        self.total: int = 0
        self.success: int = 0
        self.fail: int = 0
        self.skipped: int = 0
        self.start_time: float = 0
        self.end_time: float = 0
    def start(self):
        self.start_time = time.time()
    def finish(self):
        self.end_time = time.time()
    @property
    def duration(self):
        return self.end_time - self.start_time
    def to_dict(self) -> dict:
        return {
            'total': self.total,
            'success': self.success,
            'failed': self.fail,
            'skipped': self.skipped,
            'duration': round(self.duration, 2),
            'timestamp': datetime.now().isoformat()
        }

# 向量库更新服务
class VectorDBUpdater:
    def __init__(self):
        self.vector_db = get_vector_db()
        self.embedding_service = get_embedding_service()
    def _embed_batch(self, documents: list[str]) -> list[list[float]]:
        """
        批量向量化文档
        :param documents: 文档列表
        :return: 向量列表
        """
        return self.embedding_service.embed_documents(documents)
    async def incremental_update(self, collection_name: str, documents: list[str], metadatas: list[dict], ids: list[str], batch_size: int=50):
        """
        增量更新：添加或更新指定文档
        :param collection_name: 集合名称
        :param documents: 文档内容列表
        :param metadatas: 元数据列表
        :param ids: 文档ID列表
        :param batch_size: 每批处理数量
        :return: 更新统计信息
        """
        stats = UpdateStats()
        stats.total = len(ids)
        stats.start()
        def _sync_update():
            # 获取集合
            collection = self.vector_db.get_or_create_collection(collection_name)
            # 获取集合中所有数据
            collection_data = collection.get()
            # 获取集合中的id
            collection_ids = set(collection_data.get('ids', [])) # 去重无序
            # 分离： 需要更新的，需要添加的
            update_ids, update_docs, update_metas = [], [], []
            add_ids, add_docs, add_metas = [], [], []
            for i, doc_id in enumerate(ids):
                # 如果ids中有id存在于collection_ids，则为更新
                if doc_id in collection_ids:
                    update_ids.append(doc_id)
                    update_docs.append(documents[i])
                    update_metas.append(metadatas[i])
                else:
                    add_ids.append(doc_id)
                    add_docs.append(documents[i])
                    add_metas.append(metadatas[i])
            # 分批向量化并更新
            for i in range(0, len(update_ids), batch_size):
                batch_ids = update_ids[i:i+batch_size] # [0.50],[51,100]
                batch_docs = update_docs[i:i+batch_size]
                batch_metas = update_metas[i:i+batch_size]
                try:
                    embeddings = self._embed_batch(batch_docs)
                    collection.update(
                        ids=batch_ids,
                        documents=batch_docs,
                        metadatas=batch_metas,
                        embeddings=embeddings
                    )
                    stats.success += len(batch_ids)
                except Exception as e:
                    logger.error(f"更新批次失败 batch_ids={batch_ids}: {e}", exc_info=True)
                    stats.failed += len(batch_ids)
            # 分批向量化并添加
            for i in range(0, len(add_ids), batch_size):
                batch_ids = add_ids[i:i+batch_size]
                batch_docs = add_docs[i:i+batch_size]
                batch_metas = add_metas[i:i+batch_size]
                try:
                    embeddings = self._embed_batch(batch_docs)
                    collection.add(
                        ids=batch_ids,
                        documents=batch_docs,
                        metadatas=batch_metas,
                        embeddings=embeddings
                    )
                    stats.success += len(batch_ids)
                except Exception as e:
                    logger.error(f"添加批次失败 batch_ids={batch_ids}: {e}", exc_info=True)
                    stats.failed += len(batch_ids)
            stats.skipped = len(ids) - stats.success - stats.failed
        await asyncio.to_thread(_sync_update)
        stats.finish()
        logger.info(f"增量更新完成: {stats.to_dict()}")
        return stats.to_dict()

    # 全量更新
    async def full_update(self, collection_name: str, documents: list[str], metadatas: list[dict], ids: list[str], batch_size: int=50) -> dict:
        """
        全量更新：清空集合后重新添加
        :param collection_name: 集合名称
        :param documents: 文档内容列表
        :param metadatas: 元数据列表
        :param ids: 文档ID列表
        :param batch_size: 每批处理数量
        :return: 更新统计信息
        """
        stats = UpdateStats()
        stats.total = len(ids)
        stats.start()
        def _sync_update():
            # 删除并重建集合(清空所有的数据)
            try:
                self.vector_db.delete_collection(collection_name)
            except:
                pass
            collection = self.vector_db.get_or_create_collection(collection_name)
            # 分批向量化并添加
            for i in range(0, len(ids), batch_size):
                batch_ids = ids[i:i+batch_size]
                batch_docs = documents[i:i+batch_size]
                batch_metas = metadatas[i:i+batch_size]
                try:
                    embeddings = self._embed_batch(batch_docs)
                    collection.add(
                        ids=batch_ids,
                        documents=batch_docs,
                        metadatas=batch_metas,
                        embeddings=embeddings
                    )
                    stats.success += len(batch_ids)
                except Exception as e:
                    logger.error(f"全量更新批次失败：{e}", exc_info=True)
                    stats.failed += len(batch_ids)
        await asyncio.to_thread(_sync_update)
        stats.finish()
        logger.info(f"全量更新完成：{stats.to_dict()}")
        return stats.to_dict()

    async def delete_documents(self, collection_name: str, ids: list[str]) -> dict:
        """
        删除指定文档
        :param collection_name: 集合名称
        :param ids: 要删除的文档ID列表
        :return: 删除结果
        """
        def _sync_delete():
            self.vector_db.delete_documents(collection_name, ids)
        await asyncio.to_thread(_sync_delete)
        result = {
            'deleted_count': len(ids),
            'collection': collection_name,
            'timestamp': datetime.now().isoformat()
        }
        logger.info(f"删除文档完成：{result}")
        return result

    async def get_collection_stats(self, collection_name: str) -> dict:
        """
        获取集合统计信息
        :param collection_name: 集合名称
        :return: 集合统计
        """
        def _sync_stats():
            count = self.vector_db.get_collection_count(collection_name)
            return {
                'collection': collection_name,
                'document_count': count,
                'timestamp': datetime.now().isoformat()
            }
        return await asyncio.to_thread(_sync_stats)

_updater_instance: Optional[VectorDBUpdater] = None

def get_updater() -> VectorDBUpdater:
    global _updater_instance
    if _updater_instance is None:
        _updater_instance = VectorDBUpdater()
    return _updater_instance
