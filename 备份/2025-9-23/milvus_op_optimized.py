"""
优化版的Milvus操作模块 - 支持批量处理和多线程
"""

from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility
import json
import logging
import requests
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class BatchInsertData:
    """批量插入数据结构"""
    collection_name: str
    data: List[List[Any]]
    texts_for_vectorization: List[str]

class OptimizedSiliconFlowEmbedder:
    """优化的SiliconFlow API调用类，支持大批量向量化"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.siliconflow.cn/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.dimension = 1024
        self.max_batch_size = 64  # SiliconFlow API最大批量限制为64
        
    def encode_batch(self, texts: List[str], model: str = "BAAI/bge-m3") -> List[List[float]]:
        """
        批量向量化文本，自动分批处理大量文本
        """
        if not texts:
            return []
        
        all_embeddings = []
        
        # 分批处理
        for i in range(0, len(texts), self.max_batch_size):
            batch_texts = texts[i:i + self.max_batch_size]
            print(f"🔄 向量化批次 {i//self.max_batch_size + 1}/{(len(texts)-1)//self.max_batch_size + 1} ({len(batch_texts)} 个文本)")
            
            batch_embeddings = self._encode_single_batch(batch_texts, model)
            all_embeddings.extend(batch_embeddings)
            
            # 简单的速率限制
            if i + self.max_batch_size < len(texts):
                time.sleep(0.1)
        
        return all_embeddings
    
    def _encode_single_batch(self, texts: List[str], model: str) -> List[List[float]]:
        """处理单个批次的向量化"""
        processed_texts = [text if text and text.strip() else " " for text in texts]
        
        payload = {
            "model": model,
            "input": processed_texts,
            "encoding_format": "float"
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{self.base_url}/embeddings",
                    headers=self.headers,
                    json=payload,
                    timeout=60  # 增加超时时间
                )
                
                if response.status_code == 200:
                    result = response.json()
                    embeddings = [item["embedding"] for item in result["data"]]
                    return embeddings
                else:
                    logger.error(f"API调用失败 (尝试 {attempt+1}/{max_retries}): {response.status_code}, {response.text}")
                    if attempt < max_retries - 1:
                        time.sleep(1 * (attempt + 1))  # 指数退避
                        
            except Exception as e:
                logger.error(f"向量化失败 (尝试 {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))
        
        # 失败后返回零向量
        logger.warning(f"批次向量化最终失败，返回零向量")
        return [[0.0] * self.dimension for _ in texts]

class OptimizedStandardClauseMatchingSystem:
    """
    优化的标准条款匹配系统 - 支持批量处理和多线程
    """
    
    def __init__(self, uri: str, token: str, siliconflow_api_key: str, 
                 siliconflow_base_url: str = "https://api.siliconflow.cn/v1"):
        self.uri = uri
        self.token = token
        self.embedder = OptimizedSiliconFlowEmbedder(siliconflow_api_key, siliconflow_base_url)
        self.dimension = self.embedder.dimension
        self.connect()
        
        # 集合名称定义
        self.collections = {
            'scope': 'standard_scope_collection',
            'parameters': 'standard_parameters_collection', 
            'topic_keywords': 'standard_topic_keywords_collection',
            'context_keywords': 'standard_context_keywords_collection',
            'table_headers': 'standard_table_headers_collection'
        }
        
        # 基础权重配置 - 用于动态调整
        self.base_weights = {
            'topic_keywords': 0.30,
            'scope': 0.20,
            'parameters': 0.20,
            'context_keywords': 0.10,
            'table_headers': 0.20
        }
        
        # 高价值字段 - 当相似度高时给予额外奖励
        self.high_value_fields = {'parameters', 'table_headers'}
        
        # 相似度阈值 - 超过此值时启动奖励机制
        self.similarity_thresholds = {
            'parameters': 0.6,      # 参数相似度超过0.6认为高度相关
            'table_headers': 0.7,  # 表头相似度超过0.7认为高度相关
            'topic_keywords': 0.8,  # 主题词需要更高相似度
            'scope': 0.7,          # 范围相似度阈值
            'context_keywords': 0.75 # 上下文关键词阈值
        }
        
        # 缓存集合加载状态
        self._collections_loaded = False
    
    def connect(self):
        """连接到Milvus"""
        try:
            connections.connect("default", uri=self.uri, token=self.token)
            logger.info("✅ Successfully connected to Milvus")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Milvus: {e}")
            raise
    
    def batch_insert_clause_data(self, chapters_data: List[Dict[str, Any]], batch_size: int = 50):
        """
        批量插入章节数据 - 核心优化方法
        
        Args:
            chapters_data: 章节数据列表，每个元素包含 document_id, chapter, clause_data
            batch_size: 批量处理大小
        """
        print(f"🚀 开始批量插入 {len(chapters_data)} 个章节")
        
        # 第一步：收集所有需要向量化的文本
        all_texts = []
        text_to_data_mapping = []  # 记录每个文本对应的数据信息
        
        print("📝 收集所有文本用于向量化...")
        for i, chapter_info in enumerate(chapters_data):
            document_id = chapter_info['document_id']
            chapter = chapter_info['chapter']
            clause_data = chapter_info['clause_data']
            
            # 收集scope文本
            if clause_data.get('scope'):
                all_texts.append(clause_data['scope'])
                text_to_data_mapping.append({
                    'type': 'scope',
                    'index': i,
                    'document_id': document_id,
                    'chapter': chapter,
                    'text': clause_data['scope']
                })
            
            # 收集topic keywords文本
            if clause_data.get('topic_keywords'):
                keywords_text = ",".join(clause_data['topic_keywords'])
                all_texts.append(keywords_text)
                text_to_data_mapping.append({
                    'type': 'topic_keywords',
                    'index': i,
                    'document_id': document_id,
                    'chapter': chapter,
                    'text': keywords_text
                })
            
            # 收集context keywords文本
            if clause_data.get('context_keywords'):
                keywords_text = ",".join(clause_data['context_keywords'])
                all_texts.append(keywords_text)
                text_to_data_mapping.append({
                    'type': 'context_keywords',
                    'index': i,
                    'document_id': document_id,
                    'chapter': chapter,
                    'text': keywords_text
                })
            
            # 收集parameters文本
            if clause_data.get('parameters'):
                for param in clause_data['parameters']:
                    # 确保所有字段都不是None
                    item = param.get('item', '') or ''
                    constraint = param.get('constraint', '') or ''
                    value = str(param.get('value', '') or '')
                    unit = param.get('unit', '') or ''
                    
                    param_text = f"{item} {constraint} {value} {unit}".strip()
                    all_texts.append(param_text)
                    text_to_data_mapping.append({
                        'type': 'parameters',
                        'index': i,
                        'document_id': document_id,
                        'chapter': chapter,
                        'param': param,
                        'text': param_text
                    })
            
            # 收集table headers文本
            if clause_data.get('table_headers'):
                headers_text = ",".join(clause_data['table_headers'])
                all_texts.append(headers_text)
                text_to_data_mapping.append({
                    'type': 'table_headers',
                    'index': i,
                    'document_id': document_id,
                    'chapter': chapter,
                    'text': headers_text
                })
        
        print(f"📊 收集了 {len(all_texts)} 个文本需要向量化")
        
        # 第二步：批量向量化所有文本
        print("🔢 开始批量向量化...")
        all_embeddings = self.embedder.encode_batch(all_texts)
        
        # 第三步：组织数据按集合分组
        collection_data = {
            'scope': [],
            'parameters': [],
            'topic_keywords': [],
            'context_keywords': [],
            'table_headers': []
        }
        
        print("📦 组织数据按集合分组...")
        for i, mapping in enumerate(text_to_data_mapping):
            embedding = all_embeddings[i]
            data_type = mapping['type']
            
            if data_type == 'scope':
                collection_data['scope'].append([
                    mapping['document_id'],
                    mapping['chapter'],
                    mapping['text'],
                    embedding
                ])
            elif data_type == 'topic_keywords':
                collection_data['topic_keywords'].append([
                    mapping['document_id'],
                    mapping['chapter'],
                    mapping['text'],
                    embedding
                ])
            elif data_type == 'context_keywords':
                collection_data['context_keywords'].append([
                    mapping['document_id'],
                    mapping['chapter'],
                    mapping['text'],
                    embedding
                ])
            elif data_type == 'parameters':
                param = mapping['param']
                collection_data['parameters'].append([
                    mapping['document_id'],
                    mapping['chapter'],
                    param.get('item', '') or '',
                    param.get('constraint', '') or '',
                    str(param.get('value', '') or ''),
                    param.get('unit', '') or '',  # 确保None转换为空字符串
                    param.get('source_text', '') or '',
                    embedding
                ])
            elif data_type == 'table_headers':
                collection_data['table_headers'].append([
                    mapping['document_id'],
                    mapping['chapter'],
                    mapping['text'],
                    embedding
                ])
        
        # 第四步：批量插入到各个集合
        print("💾 开始批量插入数据到Milvus...")
        
        def insert_to_collection(collection_name, data_list):
            if not data_list:
                return
            
            collection = Collection(self.collections[collection_name])
            
            # 转换数据格式为Milvus期望的格式
            if collection_name == 'parameters':
                # parameters集合有更多字段
                transposed_data = [
                    [row[0] for row in data_list],  # document_id
                    [row[1] for row in data_list],  # chapter
                    [row[2] for row in data_list],  # item
                    [row[3] for row in data_list],  # constraint
                    [row[4] for row in data_list],  # value
                    [row[5] for row in data_list],  # unit
                    [row[6] for row in data_list],  # source_text
                    [row[7] for row in data_list],  # vector
                ]
            else:
                # 其他集合格式相同
                transposed_data = [
                    [row[0] for row in data_list],  # document_id
                    [row[1] for row in data_list],  # chapter
                    [row[2] for row in data_list],  # text
                    [row[3] for row in data_list],  # vector
                ]
            
            collection.insert(transposed_data)
            print(f"✅ 插入了 {len(data_list)} 条记录到 {collection_name} 集合")
        
        # 并行插入各个集合
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for collection_name, data_list in collection_data.items():
                if data_list:
                    future = executor.submit(insert_to_collection, collection_name, data_list)
                    futures.append((collection_name, future))
            
            for collection_name, future in futures:
                try:
                    future.result(timeout=60)
                except Exception as e:
                    logger.error(f"❌ 插入到 {collection_name} 失败: {e}")
        
        print(f"🎉 批量插入完成！处理了 {len(chapters_data)} 个章节")

    def create_collections(self):
        """创建所有必要的集合（保持与原版一致）"""
        print("创建 Milvus 集合...")
        
        # 1. Scope 集合
        scope_fields = [
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
            FieldSchema(name="chapter", dtype=DataType.VARCHAR, max_length=200),
            FieldSchema(name="scope_text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.dimension)
        ]
        scope_schema = CollectionSchema(scope_fields, "标准文件范围向量集合")
        
        if utility.has_collection(self.collections['scope']):
            utility.drop_collection(self.collections['scope'])
            logger.info(f"Dropped existing collection: {self.collections['scope']}")
        Collection(self.collections['scope'], scope_schema)
        logger.info(f"Created collection: {self.collections['scope']}")
        
        # 2. Parameters 集合
        param_fields = [
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="chapter", dtype=DataType.VARCHAR, max_length=200),
            FieldSchema(name="item", dtype=DataType.VARCHAR, max_length=500),
            FieldSchema(name="constraint", dtype=DataType.VARCHAR, max_length=200),
            FieldSchema(name="value", dtype=DataType.VARCHAR, max_length=200),
            FieldSchema(name="unit", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="source_text", dtype=DataType.VARCHAR, max_length=2000),
            FieldSchema(name="param_id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.dimension)
        ]
        param_schema = CollectionSchema(param_fields, "标准文件参数向量集合")
        
        if utility.has_collection(self.collections['parameters']):
            utility.drop_collection(self.collections['parameters'])
            logger.info(f"Dropped existing collection: {self.collections['parameters']}")
        Collection(self.collections['parameters'], param_schema)
        logger.info(f"Created collection: {self.collections['parameters']}")
        
        # 3. Topic Keywords 集合
        topic_fields = [
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="chapter", dtype=DataType.VARCHAR, max_length=200),
            FieldSchema(name="keywords_text", dtype=DataType.VARCHAR, max_length=2000),
            FieldSchema(name="keyword_id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.dimension)
        ]
        topic_schema = CollectionSchema(topic_fields, "标准文件主题关键词向量集合")
        
        if utility.has_collection(self.collections['topic_keywords']):
            utility.drop_collection(self.collections['topic_keywords'])
            logger.info(f"Dropped existing collection: {self.collections['topic_keywords']}")
        Collection(self.collections['topic_keywords'], topic_schema)
        logger.info(f"Created collection: {self.collections['topic_keywords']}")
        
        # 4. Context Keywords 集合
        context_fields = [
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="chapter", dtype=DataType.VARCHAR, max_length=200),
            FieldSchema(name="keywords_text", dtype=DataType.VARCHAR, max_length=2000),
            FieldSchema(name="keyword_id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.dimension)
        ]
        context_schema = CollectionSchema(context_fields, "标准文件上下文关键词向量集合")
        
        if utility.has_collection(self.collections['context_keywords']):
            utility.drop_collection(self.collections['context_keywords'])
            logger.info(f"Dropped existing collection: {self.collections['context_keywords']}")
        Collection(self.collections['context_keywords'], context_schema)
        logger.info(f"Created collection: {self.collections['context_keywords']}")
        
        # 5. Table Headers 集合
        table_fields = [
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="chapter", dtype=DataType.VARCHAR, max_length=200),
            FieldSchema(name="headers_text", dtype=DataType.VARCHAR, max_length=2000),
            FieldSchema(name="header_id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.dimension)
        ]
        table_schema = CollectionSchema(table_fields, "标准文件表格标题向量集合")
        
        if utility.has_collection(self.collections['table_headers']):
            utility.drop_collection(self.collections['table_headers'])
            logger.info(f"Dropped existing collection: {self.collections['table_headers']}")
        Collection(self.collections['table_headers'], table_schema)
        logger.info(f"Created collection: {self.collections['table_headers']}")
    
    def create_indexes(self):
        """为所有集合创建索引"""
        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128}
        }
        
        for collection_name in self.collections.values():
            collection = Collection(collection_name)
            collection.create_index("vector", index_params)
            logger.info(f"Created index for {collection_name}")
    
    def load_collections(self):
        """加载所有集合到内存（带缓存）"""
        if self._collections_loaded:
            return
            
        for collection_name in self.collections.values():
            collection = Collection(collection_name)
            collection.load()
            logger.info(f"Loaded collection: {collection_name}")
        
        self._collections_loaded = True
    
    def _apply_field_reranker(self, query_text: str, search_results: List[Dict], top_k: int) -> List[Dict]:
        """
        对单个字段的搜索结果进行reranker重排
        """
        if not search_results or len(search_results) <= top_k:
            return search_results
        
        # 构建文档文本
        documents = []
        for result in search_results:
            content = result.get('content', '')
            if content:
                documents.append(content)
            else:
                # 备用方案：使用document_id和chapter
                documents.append(f"Document: {result['document_id']} Chapter: {result['chapter']}")
        
        try:
            payload = {
                "model": "BAAI/bge-reranker-v2-m3",
                "query": query_text,
                "documents": documents,
                "top_k": top_k,
                "return_documents": True
            }
            
            response = requests.post(
                f"{self.embedder.base_url}/rerank",
                headers=self.embedder.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                rerank_results = response.json().get("results", [])
                reranked_search_results = []
                
                for rerank_item in rerank_results:
                    original_index = rerank_item.get('index', 0)
                    if 0 <= original_index < len(search_results):
                        result = search_results[original_index].copy()
                        # 用reranker分数替换原始相似度
                        result['similarity'] = rerank_item.get('relevance_score', result['similarity'])
                        result['reranked'] = True
                        reranked_search_results.append(result)
                
                return reranked_search_results
                
        except Exception as e:
            logger.error(f"字段重排失败: {e}")
        
        # 失败时返回原始结果
        return search_results[:top_k]

    def batch_find_matching_clauses(self, queries: List[Dict[str, Any]], top_k: int = 10, use_reranker: bool = True) -> List[List[Dict]]:
        """
        批量查找匹配的条款 - 字段级批量search优化版（带reranker前置）
        """
        self.load_collections()
        print(f"🔄 开始批量查询 {len(queries)} 个章节...")

        # 1. 按字段收集所有需要向量化的文本和索引
        field_vectors = {ft: [] for ft in self.collections.keys()}
        field_query_indices = {ft: [] for ft in self.collections.keys()}
        field_texts = {ft: [] for ft in self.collections.keys()}

        for i, query in enumerate(queries):
            clause_data = query['clause_data']
            if clause_data.get('scope'):
                print("=" * 20,"发现scope")
                field_texts['scope'].append(clause_data['scope'])
                field_query_indices['scope'].append(i)
            if clause_data.get('topic_keywords'):
                keywords_text = " ".join(clause_data['topic_keywords'])
                field_texts['topic_keywords'].append(keywords_text)
                field_query_indices['topic_keywords'].append(i)
            if clause_data.get('context_keywords'):
                keywords_text = " ".join(clause_data['context_keywords'])
                field_texts['context_keywords'].append(keywords_text)
                field_query_indices['context_keywords'].append(i)
            if clause_data.get('parameters'):
                for param in clause_data['parameters']:
                    param_text = f"{param.get('item', '')} {param.get('constraint', '')} {param.get('value', '')} {param.get('unit', '')}"
                    field_texts['parameters'].append(param_text)
                    field_query_indices['parameters'].append(i)
            if clause_data.get('table_headers'):
                headers_text = " | ".join(clause_data['table_headers'])
                field_texts['table_headers'].append(headers_text)
                field_query_indices['table_headers'].append(i)

        # 2. 批量向量化所有文本
        for ft in self.collections.keys():
            if field_texts[ft]:
                field_vectors[ft] = self.embedder.encode_batch(field_texts[ft])
            else:
                field_vectors[ft] = []

        # 3. 批量search并分配结果（所有字段都扩大搜索范围用于reranker）
        field_search_results = {ft: [] for ft in self.collections.keys()}
        for ft in self.collections.keys():
            if field_vectors[ft]:
                collection = Collection(self.collections[ft])
                search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
                vectors = field_vectors[ft]
                
                # 所有字段都扩大搜索范围用于reranker
                search_limit = (top_k * 3) if use_reranker else (top_k * 2)
                
                # 获取更多字段用于reranker
                output_fields = ["document_id", "chapter"]
                if ft == 'parameters':
                    output_fields.extend(["item", "constraint", "value", "unit"])
                elif ft in ['topic_keywords', 'context_keywords']:
                    output_fields.append('keywords_text')
                elif ft == 'table_headers':
                    output_fields.append('headers_text')
                elif ft == 'scope':
                    output_fields.append('scope_text')
                
                batch_size = 10  # Milvus nq限制
                all_results = []
                for start in range(0, len(vectors), batch_size):
                    batch_vectors = vectors[start:start+batch_size]
                    batch_results = collection.search(
                        data=batch_vectors,
                        anns_field='vector',
                        param=search_params,
                        limit=search_limit,
                        output_fields=output_fields
                    )
                    all_results.extend(batch_results)
                field_search_results[ft] = all_results
            else:
                field_search_results[ft] = []

        # 4. 对所有字段应用reranker
        if use_reranker:
            for ft in self.collections.keys():
                if field_search_results[ft] and field_texts[ft]:
                    print(f"🔄 对 {ft} 字段应用reranker...")
                    # 分组处理每个查询的reranker
                    reranked_results = []
                    for idx, (query_text, result_batch) in enumerate(zip(field_texts[ft], field_search_results[ft])):
                        if result_batch:
                            # 构建候选文档内容
                            search_results = []
                            for hit in result_batch:
                                result_data = {
                                    'document_id': hit.entity.get('document_id'),
                                    'chapter': hit.entity.get('chapter'),
                                    'similarity': hit.score,
                                    'collection_type': ft
                                }
                                
                                # 构建内容文本
                                if ft == 'parameters':
                                    content = f"{hit.entity.get('item', '')} {hit.entity.get('constraint', '')} {hit.entity.get('value', '')} {hit.entity.get('unit', '')}"
                                elif ft in ['topic_keywords', 'context_keywords']:
                                    content = hit.entity.get('keywords_text', '')
                                elif ft == 'table_headers':
                                    content = hit.entity.get('headers_text', '')
                                elif ft == 'scope':
                                    content = hit.entity.get('scope_text', '')
                                else:
                                    content = f"Document: {result_data['document_id']} Chapter: {result_data['chapter']}"
                                
                                result_data['content'] = content
                                search_results.append(result_data)
                            
                            # 应用reranker
                            reranked = self._apply_field_reranker(query_text, search_results, top_k * 2)
                            reranked_results.append(reranked)
                        else:
                            reranked_results.append([])
                    
                    field_search_results[ft] = reranked_results

        # 5. 按原查询分组，合并结果
        all_results = []
        for i, query in enumerate(queries):
            matching_results = {}
            # 遍历所有字段，将属于当前query的结果合并
            for ft in self.collections.keys():
                # 找到属于当前query的所有search结果
                query_result_indices = [idx for idx, qidx in enumerate(field_query_indices[ft]) if qidx == i]
                
                for result_idx in query_result_indices:
                    if result_idx < len(field_search_results[ft]):
                        if use_reranker:
                            # 已经reranked的结果（所有字段都可能被rerank了）
                            search_results = field_search_results[ft][result_idx]
                        else:
                            # 原始search结果
                            hits = field_search_results[ft][result_idx] if field_search_results[ft] else []
                            search_results = []
                            for hit in hits:
                                search_results.append({
                                    'document_id': hit.entity.get('document_id'),
                                    'chapter': hit.entity.get('chapter'),
                                    'similarity': hit.score,
                                    'collection_type': ft
                                })
                        
                        self._merge_results(matching_results, search_results, ft, query['document_id'])
            
            # 计算加权相似度并排序
            final_results = self._calculate_weighted_similarity(matching_results)
            all_results.append(final_results[:top_k])
        
        print(f"✅ 批量查询完成")
        return all_results
    
    def _search_collection_with_vector(self, collection_type: str, query_vector: List[float], top_k: int) -> List[Dict]:
        """使用预计算的向量在指定集合中搜索"""
        collection = Collection(self.collections[collection_type])
        
        # 执行搜索
        search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
        results = collection.search(
            data=[query_vector],
            anns_field='vector',
            param=search_params,
            limit=top_k,
            output_fields=["document_id", "chapter"]
        )
        
        search_results = []
        for hits in results:
            for hit in hits:
                search_results.append({
                    'document_id': hit.entity.get('document_id'),
                    'chapter': hit.entity.get('chapter'),
                    'similarity': hit.score,
                    'collection_type': collection_type
                })
        
        return search_results
    
    def _search_collection(self, collection_type: str, query_text: str, top_k: int, use_reranker: bool = False) -> List[Dict]:
        """在指定集合中搜索（可选reranker前置筛选）"""
        collection = Collection(self.collections[collection_type])
        
        # 编码查询文本
        query_vector = self.embedder.encode_batch([query_text])[0]
        
        # 向量字段名
        vector_field = 'vector'
        
        # 先用向量检索获取更多候选（如果用reranker则扩大候选池）
        search_limit = top_k * 3 if use_reranker else top_k
        search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
        
        # 获取更多字段用于reranker
        output_fields = ["document_id", "chapter"]
        if collection_type == 'parameters':
            output_fields.extend(["item", "constraint", "value", "unit"])
        elif collection_type in ['topic_keywords', 'context_keywords', 'table_headers']:
            field_name = 'keywords_text' if 'keywords' in collection_type else 'headers_text'
            output_fields.append(field_name)
        elif collection_type == 'scope':
            output_fields.append("scope_text")
        
        results = collection.search(
            data=[query_vector],
            anns_field=vector_field,
            param=search_params,
            limit=search_limit,
            output_fields=output_fields
        )
        
        search_results = []
        for hits in results:
            for hit in hits:
                result_data = {
                    'document_id': hit.entity.get('document_id'),
                    'chapter': hit.entity.get('chapter'),
                    'similarity': hit.score,
                    'collection_type': collection_type
                }
                
                # 保存原始内容用于reranker
                if collection_type == 'parameters':
                    result_data['content'] = f"{hit.entity.get('item', '')} {hit.entity.get('constraint', '')} {hit.entity.get('value', '')} {hit.entity.get('unit', '')}"
                elif collection_type == 'scope':
                    result_data['content'] = hit.entity.get('scope_text', '')
                elif collection_type in ['topic_keywords', 'context_keywords']:
                    result_data['content'] = hit.entity.get('keywords_text', '')
                elif collection_type == 'table_headers':
                    result_data['content'] = hit.entity.get('headers_text', '')
                
                search_results.append(result_data)
        
        # 如果启用reranker且有足够候选，则进行重排（所有字段都使用）
        if use_reranker and len(search_results) > top_k:
            search_results = self._apply_field_reranker(query_text, search_results, top_k)
        
        return search_results[:top_k]
    
    def _merge_results(self, matching_results: Dict, search_results: List[Dict], 
                      collection_type: str, exclude_document_id: str):
        """合并搜索结果"""
        for result in search_results:
            # 排除同一文档的结果
            if result['document_id'] == exclude_document_id:
                continue
                
            key = f"{result['document_id']}#{result['chapter']}"
            if key not in matching_results:
                matching_results[key] = {
                    'document_id': result['document_id'],
                    'chapter': result['chapter'],
                    'similarities': {}
                }
            
            # 保存该类型的最高相似度
            if (collection_type not in matching_results[key]['similarities'] or 
                result['similarity'] > matching_results[key]['similarities'][collection_type]):
                matching_results[key]['similarities'][collection_type] = result['similarity']
    
    def _calculate_weighted_similarity(self, matching_results: Dict) -> List[Dict]:
        """
        智能加权相似度计算 - 根据实际相似度表现动态调整权重
        """
        final_results = []
        
        for key, result in matching_results.items():
            similarities = result['similarities']
            
            # 第一步：计算动态权重
            dynamic_weights = self._calculate_dynamic_weights(similarities)
            
            # 第二步：计算基础加权分数
            base_weighted_score = 0.0
            total_weight = 0.0
            
            for collection_type, similarity in similarities.items():
                weight = dynamic_weights.get(collection_type, 0.1)
                base_weighted_score += similarity * weight
                total_weight += weight
            
            # 第三步：应用高价值字段奖励机制
            final_score = self._apply_high_value_bonus(base_weighted_score, similarities, total_weight)
            
            # # 第四步：应用协同效应奖励
            # final_score = self._apply_synergy_bonus(final_score, similarities)
            
            final_results.append({
                'document_id': result['document_id'],
                'chapter': result['chapter'],
                'weighted_similarity': final_score,
                'detailed_similarities': similarities,
                'dynamic_weights': dynamic_weights,
                'has_high_value_match': any(similarities.get(field, 0) >= self.similarity_thresholds.get(field, 0.8) 
                                          for field in self.high_value_fields)
            })
        
        # 按最终分数排序
        final_results.sort(key=lambda x: x['weighted_similarity'], reverse=True)
        
        return final_results
    
    def _calculate_dynamic_weights(self, similarities: Dict[str, float]) -> Dict[str, float]:
        """
        根据相似度表现动态调整权重
        """
        dynamic_weights = self.base_weights.copy()
        
        # 检查是否有高相似度的高价值字段
        high_value_boost = False
        for field in self.high_value_fields:
            if field in similarities:
                similarity = similarities[field]
                threshold = self.similarity_thresholds.get(field, 0.75)
                
                if similarity >= threshold:
                    # 高相似度时增加该字段权重
                    boost_factor = 1.0 + (similarity - threshold) * 2  # 最大可增加到2倍权重
                    dynamic_weights[field] *= boost_factor
                    high_value_boost = True
        
        # 如果有高价值字段表现优秀，适当降低其他字段权重
        if high_value_boost:
            for field in dynamic_weights:
                if field not in self.high_value_fields:
                    dynamic_weights[field] *= 0.8  # 轻微降低其他字段权重
        
        # 标准化权重，确保总和合理
        total_weight = sum(dynamic_weights.values())
        if total_weight > 0:
            for field in dynamic_weights:
                dynamic_weights[field] = dynamic_weights[field] / total_weight
        
        return dynamic_weights
    
    def _apply_high_value_bonus(self, base_score: float, similarities: Dict[str, float], total_weight: float) -> float:
        """
        为高价值字段的优秀表现提供额外奖励
        """
        bonus = 0.0
        
        for field in self.high_value_fields:
            if field in similarities:
                similarity = similarities[field]
                threshold = self.similarity_thresholds.get(field, 0.75)
                
                if similarity >= threshold:
                    # 计算奖励：相似度越高，奖励越大
                    field_bonus = (similarity - threshold) * 0.3  # 最大奖励0.3
                    bonus += field_bonus
                    
                    # 特别奖励：如果多个高价值字段都表现优秀
                    if field == 'parameters' and 'table_headers' in similarities:
                        table_sim = similarities['table_headers']
                        table_threshold = self.similarity_thresholds.get('table_headers', 0.75)
                        if table_sim >= table_threshold:
                            # 参数和表头都匹配良好时的协同奖励
                            bonus += 0.15
        
        return base_score + bonus
    
    def _apply_synergy_bonus(self, score: float, similarities: Dict[str, float]) -> float:
        """
        应用字段协同效应奖励
        """
        # 检查多字段高质量匹配的协同效应
        high_quality_fields = 0
        total_high_sim = 0.0
        
        for field, similarity in similarities.items():
            threshold = self.similarity_thresholds.get(field, 0.75)
            if similarity >= threshold:
                high_quality_fields += 1
                total_high_sim += similarity
        
        # 多字段协同奖励
        if high_quality_fields >= 3:
            # 3个或更多字段都表现优秀时的协同奖励
            synergy_bonus = 0.1 * (high_quality_fields - 2)  # 每多一个高质量字段增加0.1
            score += synergy_bonus
        elif high_quality_fields == 2:
            # 2个字段表现优秀的适度奖励
            avg_high_sim = total_high_sim / high_quality_fields
            if avg_high_sim >= 0.85:  # 平均相似度很高
                score += 0.05
        
        # 确保分数不超过1.0的合理范围
        return min(score, 1.0)
        
        # 按加权相似度排序
        final_results.sort(key=lambda x: x['weighted_similarity'], reverse=True)
        
        return final_results
    
    def _apply_reranker(self, query_data: Dict[str, Any], results: List[Dict]) -> List[Dict]:
        """
        使用BGE-Reranker对结果进行重排
        """
        if not results:
            return results
        
        # 构建查询文本
        query_parts = []
        if query_data.get('scope'):
            query_parts.append(query_data['scope'])
        if query_data.get('topic_keywords'):
            query_parts.append(" ".join(query_data['topic_keywords']))
        if query_data.get('parameters'):
            for param in query_data['parameters']:
                param_text = f"{param.get('item', '')} {param.get('value', '')}"
                if param_text.strip():
                    query_parts.append(param_text)
        
        query_text = " ".join(query_parts)
        
        # 构建文档文本（简化表示）
        documents = []
        for result in results:
            doc_text = f"Document: {result['document_id']} Chapter: {result['chapter']}"
            documents.append(doc_text)
        
        # 调用重排API
        try:
            payload = {
                "model": "BAAI/bge-reranker-v2-m3",
                "query": query_text,
                "documents": documents,
                "top_k": len(results),
                "return_documents": True
            }
            
            response = requests.post(
                f"{self.embedder.base_url}/rerank",
                headers=self.embedder.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                rerank_results = response.json().get("results", [])
                
                # 根据重排结果重新排序
                reranked_final = []
                for rerank_item in rerank_results:
                    original_index = rerank_item.get('index', 0)
                    if 0 <= original_index < len(results):
                        result = results[original_index].copy()
                        result['rerank_score'] = rerank_item.get('relevance_score', 0.0)
                        # 结合原始加权分数和重排分数
                        result['final_score'] = (result['weighted_similarity'] * 0.7 + 
                                               result['rerank_score'] * 0.3)
                        reranked_final.append(result)
                
                # 按最终分数排序
                reranked_final.sort(key=lambda x: x['final_score'], reverse=True)
                return reranked_final
        except Exception as e:
            logger.error(f"重排失败: {e}")
        
        return results

# 辅助函数
def create_optimized_milvus_system(siliconflow_api_key: str):
    """创建优化的Milvus系统实例"""
    MILVUS_URI = "https://in03-198809e1c756a88.serverless.aws-eu-central-1.cloud.zilliz.com"
    MILVUS_TOKEN = "922c1d2f5c907763b6db6489e9cd6d0f8258314a43c87b37ead9e429ee2c48de8a27ecb3531213809ee47705b8c3ba6bbe50a3bd"

    return OptimizedStandardClauseMatchingSystem(
        uri=MILVUS_URI,
        token=MILVUS_TOKEN,
        siliconflow_api_key=siliconflow_api_key
    )

def setup_optimized_database(system):
    """设置优化的数据库（清空并重新创建）"""
    try:
        system.create_collections()
        system.create_indexes() 
        system.load_collections()
        print("✅ 优化数据库设置完成")
        return True
    except Exception as e:
        print(f"❌ 数据库设置失败: {e}")
        return False