"""
真实场景的标准条款匹配
CELEX作为知识库，GSO作为查询源进行匹配
"""

import json
import os
# 导入优化版本的Milvus操作模块
from milvus_op_optimized import create_optimized_milvus_system, setup_optimized_database
from typing import List, Dict, Any

# 您的SiliconFlow API密钥
SILICONFLOW_API_KEY = "sk-kgrvjrxrrnokraizppuidrfjucnlqcbynmnzskrlselyfuev"

def load_json_file(file_path: str) -> List[Dict]:
    """加载JSON文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"✅ 成功加载文件: {file_path}")
        return data
    except Exception as e:
        print(f"❌ 加载文件失败: {file_path}, 错误: {e}")
        return []

def extract_all_chapters_recursive(chapter_data: Dict, file_name: str, section_name: str, document_prefix: str) -> List[Dict]:
    """递归提取所有章节信息，包括children中的子章节"""
    chapters = []
    
    chapter_id = chapter_data.get('chapter_id', '')
    chapter_title = chapter_data.get('chapter_title', '')
    raw_text = chapter_data.get('raw_text', '')
    full_path = chapter_data.get('full_path', '')
    
    # 构建文档ID
    document_id = f"{document_prefix}_{file_name}_{section_name}"
    
    # 提取条款数据
    clause_data = {
        "scope": chapter_data.get('scope', ''),
        "parameters": chapter_data.get('parameters', []),
        "topic_keywords": chapter_data.get('topic_keywords', []),
        "context_keywords": chapter_data.get('context_keywords', []),
        "table_headers": chapter_data.get('table_headers', [])
    }
    
    # 添加原始文本到scope中以增加语义信息
    
    # if raw_text:
    #     if clause_data['scope']:
    #         clause_data['scope'] += f" | {raw_text[:200]}"  # 限制长度
    #     else:
    #         clause_data['scope'] = raw_text[:200]
    
    # # 如果chapter_title没有在scope中，将其添加到topic_keywords
    # if chapter_title and chapter_title not in str(clause_data['scope']):
    #     if not clause_data['topic_keywords']:
    #         clause_data['topic_keywords'] = []
    #     if isinstance(clause_data['topic_keywords'], list):
    #         clause_data['topic_keywords'].append(chapter_title)
    
    # 添加当前章节
    current_chapter = {
        'document_id': document_id,
        'file': file_name,
        'section': section_name,
        'chapter_id': chapter_id,
        'chapter_title': chapter_title,
        'full_path': full_path,
        'raw_text': raw_text,
        'clause_data': clause_data
    }
    chapters.append(current_chapter)
    
    # 递归处理children
    children = chapter_data.get('children', [])
    for child in children:
        child_chapters = extract_all_chapters_recursive(child, file_name, section_name, document_prefix)
        chapters.extend(child_chapters)
    
    return chapters

def extract_chapters_from_json(data: List[Dict], document_prefix: str) -> List[Dict]:
    """从JSON数据中递归提取所有章节信息"""
    all_chapters = []

    section = data[0].get('sections', [])[0] if data and 'sections' in data[0] and data[0]['sections'] else {}

    file_name = data[0].get('file', 'unknown_file')
    section_name = section.get('section', 'MAIN')
    section_chapters = section.get('chapters', [])
    
    # 递归处理每个章节
    for chapter in section_chapters:
        chapter_list = extract_all_chapters_recursive(chapter, file_name, section_name, document_prefix)
        all_chapters.extend(chapter_list)
    
    # 存储提取到的all_chapters以便调试
    with open('extracted_chapters_debug.json', 'w', encoding='utf-8') as debug_file:
        json.dump(all_chapters, debug_file, indent=2, ensure_ascii=False)

    return all_chapters

def import_celex_knowledge_base_optimized(milvus_system, right_file_path: str):
    """优化版本：批量导入CELEX文件作为知识库"""
    print("=== 批量导入CELEX知识库（优化版本）===")
    
    # 加载CELEX文件
    celex_data = load_json_file(right_file_path)
    if not celex_data:
        return False
    
    # 递归提取所有章节
    celex_chapters = extract_chapters_from_json(celex_data, "CELEX")
    print(f"📚 从CELEX文件中递归提取了 {len(celex_chapters)} 个章节")
    
    # 准备批量插入的数据
    chapters_for_batch_insert = []
    
    for i, chapter in enumerate(celex_chapters):
        try:
            # 跳过没有实质内容的章节
            clause_data = chapter['clause_data']
            if (not clause_data['scope'] and 
                not clause_data['parameters'] and 
                not clause_data['topic_keywords']):
                continue
            
            # 构建章节标识符
            chapter_identifier = f"{chapter['chapter_id']}_{chapter['chapter_title']}"[:50]
            if not chapter_identifier:
                chapter_identifier = f"ch_{i}"
            
            # 添加到批量插入列表
            chapters_for_batch_insert.append({
                'document_id': chapter['document_id'],
                'chapter': chapter_identifier,
                'clause_data': clause_data
            })
                
        except Exception as e:
            print(f"⚠️  准备章节数据失败: {chapter['chapter_id']}, 错误: {e}")
            continue
    
    print(f"📦 准备批量插入 {len(chapters_for_batch_insert)} 个有效章节")
    
    # 执行批量插入
    try:
        milvus_system.batch_insert_clause_data(chapters_for_batch_insert)
        print(f"✅ CELEX知识库批量导入完成，成功导入 {len(chapters_for_batch_insert)} 个章节")
        return True
    except Exception as e:
        print(f"❌ 批量插入失败: {e}")
        return False

def query_with_gso_optimized(milvus_system, left_file_path: str, top_k: int = 5):
    """使用GSO文件进行批量查询匹配 - 优化版本"""
    print("\n=== 使用GSO进行批量查询匹配（优化版本）===")
    
    # 加载GSO文件
    gso_data = load_json_file(left_file_path)
    if not gso_data:
        return []
    
    # 递归提取所有GSO章节
    gso_chapters = extract_chapters_from_json(gso_data, "GSO")
    print(f"🔍 从GSO文件中递归提取了 {len(gso_chapters)} 个查询章节")
    
    # 过滤有效章节并准备批量查询数据
    valid_queries = []
    chapter_index_mapping = []  # 记录有效章节在原列表中的索引
    
    for i, gso_chapter in enumerate(gso_chapters):
        clause_data = gso_chapter['clause_data']
        
        # 跳过没有实质内容的章节
        if (not clause_data['scope'] and 
            not clause_data['parameters'] and 
            not clause_data['topic_keywords']):
            continue
        
        valid_queries.append({
            'document_id': gso_chapter['document_id'],
            'chapter': gso_chapter['chapter_id'], 
            'clause_data': clause_data
        })
        chapter_index_mapping.append(i)  # 记录原始索引
    
    print(f"📦 准备批量查询 {len(valid_queries)} 个有效章节")
    
    if not valid_queries:
        print("❌ 没有有效的查询章节")
        return []
    
    # 执行批量查询
    batch_results = milvus_system.batch_find_matching_clauses(valid_queries, top_k=top_k, use_reranker=True)
    
    # 构建最终结果（按用户要求的格式）
    all_matches = []
    for i, (original_index, query_results) in enumerate(zip(chapter_index_mapping, batch_results)):
        gso_chapter = gso_chapters[original_index]
        
        # 构建候选列表
        candidates = []
        if query_results:
            print(f"✅ 章节 {gso_chapter['chapter_id']} 找到 {len(query_results)} 个匹配项")
            for j, match in enumerate(query_results, 1):
                # 从document_id中解析出file信息
                doc_parts = match['document_id'].split('_')
                file_name = doc_parts[1] if len(doc_parts) > 1 else 'regulation'
                section_name = doc_parts[2] if len(doc_parts) > 2 else 'MAIN'
                
                # 使用final_score作为score，如果没有则使用weighted_similarity
                score = match.get('final_score', match.get('weighted_similarity', 0))
                
                candidate = {
                    "score": score,
                    "chapter": [
                        file_name,
                        section_name,
                        match['chapter']
                    ],
                    "similarities": match.get("detailed_similarities", {})
                }
                candidates.append(candidate)
        else:
            print(f"❌ 章节 {gso_chapter['chapter_id']} 未找到匹配项")
        
        # 构建当前章节的查询结果
        query_result = {
            "file": gso_chapter['file'],
            "section": gso_chapter['section'], 
            "chapter_id": gso_chapter['chapter_id'],
            "candidates": candidates
        }
        
        all_matches.append(query_result)
    
    print(f"\n✅ 批量查询完成，处理了 {len(all_matches)} 个章节")
    return all_matches

def save_matching_results(matches: List[Dict], output_file: str):
    """保存匹配结果到文件（用户期望的格式）"""
    print(f"\n=== 保存匹配结果到 {output_file} ===")

    try:
        # 1. 自动创建缺失目录
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # 2. 再写文件
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(matches, f, indent=2, ensure_ascii=False)

        print(f"✅ 匹配结果已保存到: {output_file}")
        print(f"📊 总计保存了 {len(matches)} 个查询章节的匹配结果")

    except Exception as e:
        print(f"❌ 保存失败: {e}")

def print_summary_statistics(matches: List[Dict]):
    """打印匹配统计信息（适配新格式）"""
    print("\n=== 匹配统计摘要 ===")
    
    if not matches:
        print("没有找到任何匹配结果")
        return
    
    total_queries = len(matches)
    queries_with_matches = len([m for m in matches if m.get('candidates', [])])
    total_matches = sum(len(m.get('candidates', [])) for m in matches)
    
    print(f"📊 查询统计:")
    print(f"   - 总查询章节数: {total_queries}")
    print(f"   - 有匹配的查询: {queries_with_matches}")
    print(f"   - 总候选匹配数: {total_matches}")
    print(f"   - 平均每查询候选数: {total_matches/total_queries:.2f}")
    
    # 分数分布统计
    all_scores = []
    for match in matches:
        for candidate in match.get('candidates', []):
            all_scores.append(candidate.get('score', 0))
    
    if all_scores:
        import statistics
        print(f"\n📈 候选分数分布:")
        print(f"   - 最高分数: {max(all_scores):.4f}")
        print(f"   - 最低分数: {min(all_scores):.4f}")
        print(f"   - 平均分数: {statistics.mean(all_scores):.4f}")
        print(f"   - 中位数分数: {statistics.median(all_scores):.4f}")
        
        # 分数质量分布
        high_quality = [s for s in all_scores if s > 0.7]
        medium_quality = [s for s in all_scores if 0.5 <= s <= 0.7]
        low_quality = [s for s in all_scores if s < 0.5]
        
        print(f"\n🎯 匹配质量分布:")
        print(f"   - 高质量匹配 (>0.7): {len(high_quality)} 个")
        print(f"   - 中等质量匹配 (0.5-0.7): {len(medium_quality)} 个")
        print(f"   - 低质量匹配 (<0.5): {len(low_quality)} 个")
    
    # 按章节类型统计
    chapter_types = {}
    for match in matches:
        chapter_id = match.get('chapter_id', '')
        if '-' in chapter_id:
            chapter_type = chapter_id.split('-')[0] + '-'
        elif '.' in chapter_id:
            chapter_type = chapter_id.split('.')[0] + '.'
        else:
            chapter_type = 'other'
        
        if chapter_type not in chapter_types:
            chapter_types[chapter_type] = 0
        chapter_types[chapter_type] += 1
    
    print(f"\n📂 章节类型分布:")
    for ch_type, count in sorted(chapter_types.items()):
        print(f"   - {ch_type}: {count} 个章节")

def main():
    """主函数"""
    print("🚀 真实场景标准条款匹配系统")
    print("=" * 60)
    
    # left_file = r"D:\Documents\知识图谱agent\示例文件\temp\F2023C00147\F2023C00147.json"
    # right_file = r"D:\Documents\知识图谱agent\示例文件\temp\R048r12e\R048r12e.json"

    # 文件路径
    left_file = r"D:\汽车检测知识图谱Agent\汽车检测知识图谱Agent\示例文件\temp\F2023C00147\F2023C00147.json"
    right_file = r"D:\汽车检测知识图谱Agent\汽车检测知识图谱Agent\示例文件\temp\R048r12e\R048r12e.json"
    
    # 检查文件是否存在
    if not os.path.exists(right_file):
        print(f"❌ CELEX文件不存在: {right_file}")
        return
    
    if not os.path.exists(left_file):
        print(f"❌ GSO文件不存在: {left_file}")
        return
    
    try:
        # 1. 创建优化的系统实例
        print("1. 创建优化的系统实例...")
        milvus_system = create_optimized_milvus_system(SILICONFLOW_API_KEY)
        
        # 2. 初始化数据库（清空之前的数据）
        print("2. 初始化数据库...")
        setup_optimized_database(milvus_system)
        
        # 3. 批量导入CELEX知识库（优化版本）
        success = import_celex_knowledge_base_optimized(milvus_system, right_file)
        if not success:
            print("❌ CELEX知识库导入失败")
            return
        
        # 4. 使用GSO进行批量查询匹配（优化版本）
        matches = query_with_gso_optimized(milvus_system, left_file, top_k=10)
        
        # 5. 保存匹配结果
        output_file = "./match_result/ADR60 VS ECER7.json"
        # output_file = "./match_result/GSO VS ECE.json"
        # output_file = "./match_result/GSO.json"
        save_matching_results(matches, output_file)
        
        # 6. 打印统计摘要
        print_summary_statistics(matches)
        
        print("\n🎉 匹配完成！")
        print(f"📄 详细结果请查看: {output_file}")
        print(f"📋 结果格式：每个GSO章节都包含file、section、chapter_id和candidates（top5匹配）")
        
    except Exception as e:
        print(f"❌ 执行过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()