from dataclasses import dataclass
from app.rag.updater import get_updater
from app.rag.retriever import get_retriever
import re
from typing import Optional

@dataclass
class KnowledgeChunk:
    """
    知识库文档块
    """
    content: str
    metadata: dict
    doc_id: str

# 知识库管理
class KnowledgeBase:
    COLLECTION_NAME = 'knowledge_base'
    def __init__(self):
        self.updater = get_updater()
        self.retriever = get_retriever()
    def parse_faq(self, content: str) -> list[KnowledgeChunk]:
        """
        解析FAQ文档，按Q&A对分割
        :param content: FAQ文档的完整文本内容
        :return: 解析后的KnowledgeChunk列表
        """
        chunks = []
        # 按### Q分割，匹配### Q1：、###Q2：
        pattern = r'(### Q\d+[：:][^\n]+)'
        parts = re.split(pattern, content)
        current_category = '常见问题'
        # 跳过目录部分
        i = 1
        while i < len(parts):
            # 检测是否分类标题(如## 一、账户相关)
            if re.match(r'## [一二三四五六七八九十]+[、.]', parts[i]):
                current_category = parts[i].strip().lstrip('#').strip()
                i += 1
                continue    # 跳过本次，开始下一次循环
            # 匹配Q标题，()为捕获组
            q_match = re.match(r'### Q(\d+)[：:](.+)', parts[i])
            if q_match:
                # 获取标题号和标题名称
                question_id = q_match.group(1)
                question_title = q_match.group(2).strip()
                # 获取答案内容
                answer = ""
                if i + 1 < len(parts):    # 防止越界
                    answer = parts[i + 1].strip()
                    # 匹配并删除**A:** 或 **A：**这样的格式标记   \s匹配零个或多个空白字符
                    answer = re.sub(r'\*\*A[：:]\*\*\s*', '', answer)
                    answer = answer.strip()
                full_content = f"Q：{question_title}\nA：{answer}"
                chunks.append(KnowledgeChunk(
                    content=full_content,
                    metadata={
                        "source": "FAQ",
                        "category": current_category,
                        "question_id": f"Q{question_id}",
                        "question": question_title
                    },
                    doc_id=f"faq_q{question_id}"
                ))
            i += 1
        return chunks

    def parse_policy(self, content: str) -> list[KnowledgeChunk]:
        """
        解析政策文档，按章节条款分割
        :param content: 政策文档的完整文本内容
        :return: 解析后的KnowledgeChunk列表
        """
        chunks = []
        # 按### x.x 标题分割
        pattern = r'(### \d+\.\d+[^\n]+)'    # [^\n]+匹配一个或多个非换行字符
        parts = re.split(pattern, content)
        current_section = '总则'
        i = 1
        while i < len(parts):
            # 检测是否是大章节标题(## 一、总则与定义)
            if re.match(r'## [一二三四五六七八九十]+[、.]', parts[i]):
                current_section = parts[i].strip().lstrip('#').strip()
                i += 1
                continue
            # 匹配小节标题
            subsection_math = re.match(r'### (\d+\.\d+)([^\n]+)', parts[i])
            if subsection_math:
                subsection_id = subsection_math.group(1)
                subsection_title = subsection_math.group(2).strip()
                # 获取条款内容
                policy_content = ""
                if i + 1 < len(parts):
                    policy_content = parts[i + 1].strip()
                full_content = f"{current_section} {subsection_id} {subsection_title}\n{policy_content}"
                chunks.append(KnowledgeChunk(
                    content=full_content,
                    metadata={
                        'source': '政策',
                        'section': current_section,
                        'subsection_id': subsection_id,
                        'subsection_title': subsection_title
                    },
                    doc_id=f"policy_{subsection_id}"
                ))
            i += 1
        return chunks

    async def load_documents(self, faq_path: str, policy_path: str) -> dict:
        """
        加载FAQ和政策文档到向量数据库
        :param faq_path: FAQ文档的文件路径
        :param policy_path: 政策文档的文件路径
        :return: 加载统计信息 {"faq": FAQ块数量, "policy": 政策快数量}
        """
        stats = {"faq": 0, "policy": 0}
        # 读取并解析FAQ
        try:
            with open(faq_path, 'r', encoding='utf-8') as f:
                faq_content = f.read()
            faq_chunks = self.parse_faq(faq_content)    # 解析FAQ文档
            if faq_chunks:
                documents = [chunk.content for chunk in faq_chunks]
                metadatas = [chunk.metadata for chunk in faq_chunks]
                ids = [chunk.doc_id for chunk in faq_chunks]
                await self.updater.full_update(self.COLLECTION_NAME, documents, metadatas, ids)
                stats['faq'] = len(faq_chunks)
        except Exception as e:
            print(f"加载FAQ文档失败：{e}")
        # 读取并解析政策
        try:
            with open(policy_path, 'r', encoding='utf-8') as f:
                policy_content = f.read()
            policy_chunks = self.parse_policy(policy_content)
            if policy_chunks:
                documents = [chunk.content for chunk in policy_chunks]
                metadatas = [chunk.metadata for chunk in policy_chunks]
                ids = [chunk.doc_id for chunk in policy_chunks]
                await self.updater.full_update(self.COLLECTION_NAME, documents, metadatas, ids)
                stats['policy'] = len(policy_chunks)
        except Exception as e:
            print(f"加载政策文档失败：{e}")
        return stats

    async def search(self, query: str, n_results: int = 3) -> dict:
        """
        检索知识库
        :param query: 用户查询文本
        :param n_results: 返回的结果数量
        :return: ChromaDB查询结果，包含documents、metadatas、scores、ids
        """
        return await self.retriever.hybrid_search(
            self.COLLECTION_NAME,
            query,
            n_results
        )

    async def get_formatted_results(self, query: str, n_results: int = 3) -> str:
        """
        检索并格式化结果为可读文本
        :param query: 用户查询文本
        :param n_results: 返回的结果数量，默认3
        :return: 格式化的知识库内容字符串
        """
        results = await self.search(query, n_results)
        if not results or not results.get('documents'):
            return "未找到相关知识库内容"
        formatted = []
        for i, (doc, metadata, score) in enumerate(zip(
            results['documents'],
            results['metadatas'],
            results['scores']
        ), 1):
            source = metadata.get('source', '未知')
            if source == 'FAQ':
                header = f"[FAQ - {metadata.get('category', '')}]"
            else:
                header = f"[政策 - {metadata.get('section', '')}]"
            formatted.append(f"{i}. {header}\n相关度: {score:.2f}\n{doc}\n")
        return "\n---\n".join(formatted)

# 全局单局实例
_knowledge_base_instance: Optional[KnowledgeBase] = None

def get_knowledge_base() -> KnowledgeBase:
    """
    获取KnowledgeBase实例
    :return: KnowledgeBase实例
    """
    global _knowledge_base_instance
    if _knowledge_base_instance is None:
        _knowledge_base_instance = KnowledgeBase()
    return _knowledge_base_instance