import json
import os

def load_json_file(file_path):
    """加载JSON文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def find_chapter_by_path(data, file_name, section_name, chapter_id):
    """
    根据file、section、chapter_id路径查找章节
    """
    for file_data in data:
        if file_data.get("file") == file_name:
            for section in file_data.get("sections", []):
                if section.get("section") == section_name:
                    return find_chapter_recursive(section.get("chapters", []), chapter_id)
    return None

def find_chapter_recursive(chapters, chapter_id):
    """
    递归查找章节
    """
    for chapter in chapters:
        if chapter.get("chapter_id") == chapter_id:
            return chapter
        # 递归查找子章节
        found = find_chapter_recursive(chapter.get("children", []), chapter_id)
        if found:
            return found
    return None

def extract_comparison_fields(chapter):
    """
    提取用于对比的字段
    """
    if not chapter:
        return None
    
    return {
        "chapter_id": chapter.get("chapter_id", ""),
        # "chapter_title": chapter.get("chapter_title", ""),
        "parameters": chapter.get("parameters", []),
        "topic_keywords": chapter.get("topic_keywords", []),
        "context_keywords": chapter.get("context_keywords", []),
        "table_headers": chapter.get("table_headers", []),
        # "full_path": chapter.get("full_path", "")
    }

def process_matches():
    """
    处理匹配关系，生成对比数据
    """
    # 文件路径
    base_dir = r"d:\Documents\知识图谱agent\示例文件\temp"
    match_file = os.path.join(base_dir, "match.json")
    gso_file = os.path.join(base_dir, "GSO-1040-2000-E机动车- 轻型柴油引擎车辆大气污染物排放允许限值", "GSO-1040-2000-E机动车- 轻型柴油引擎车辆大气污染物排放允许限值.json")
    ece_file = os.path.join(base_dir, "CELEX_42006X1227(06)_EN_TXT", "CELEX_42006X1227(06)_EN_TXT.json")
    
    # 加载数据
    print("正在加载数据文件...")
    match_data = load_json_file(match_file)
    gso_data = load_json_file(gso_file)
    ece_data = load_json_file(ece_file)
    
    print(f"加载了 {len(match_data)} 个匹配项")
    
    # 处理每个匹配项
    comparison_results = []
    
    for i, match_item in enumerate(match_data):
        print(f"处理匹配项 {i+1}/{len(match_data)}: {match_item.get('chapter_id', '')}")
        
        # 获取GSO源章节
        gso_chapter = find_chapter_by_path(
            gso_data, 
            match_item.get("file", ""), 
            match_item.get("section", ""), 
            match_item.get("chapter_id", "")
        )
        
        if not gso_chapter:
            print(f"  警告: 未找到GSO章节 {match_item.get('chapter_id', '')}")
            continue
        
        # 提取GSO章节的对比字段
        gso_comparison = extract_comparison_fields(gso_chapter)
        
        # 处理候选项
        candidates_comparison = []
        for j, candidate in enumerate(match_item.get("candidates", [])):
            chapter_path = candidate.get("chapter", [])
            if len(chapter_path) >= 3:
                file_name, section_name, chapter_id = chapter_path[0], chapter_path[1], chapter_path[2]
                
                # 查找ECE候选章节
                ece_chapter = find_chapter_by_path(ece_data, file_name, section_name, chapter_id)
                
                if ece_chapter:
                    ece_comparison = extract_comparison_fields(ece_chapter)
                    candidates_comparison.append({
                        "score": candidate.get("score", 0),
                        "chapter_path": chapter_path,
                        "comparison_data": ece_comparison
                    })
                else:
                    print(f"  警告: 未找到ECE候选章节 {chapter_path}")
                    candidates_comparison.append({
                        "score": candidate.get("score", 0),
                        "chapter_path": chapter_path,
                        "comparison_data": None
                    })
            else:
                print(f"  警告: 候选项路径格式不正确 {chapter_path}")
        
        # 构建对比结果
        comparison_result = {
            "gso_chapter": gso_comparison,
            "ece_candidates": candidates_comparison,
            "match_info": {
                "file": match_item.get("file", ""),
                "section": match_item.get("section", ""),
                "chapter_id": match_item.get("chapter_id", "")
            }
        }
        
        comparison_results.append(comparison_result)
    
    return comparison_results

def save_comparison_results(results, output_file):
    """
    保存对比结果到文件
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"对比结果已保存到: {output_file}")

def print_comparison_summary(results):
    """
    打印对比结果摘要
    """
    print("\n=== 对比结果摘要 ===")
    print(f"总共处理了 {len(results)} 个匹配项")
    
    # for i, result in enumerate(results[:5]):  # 只显示前5个作为示例
    #     gso = result["gso_chapter"]
    #     candidates = result["ece_candidates"]
        
    #     print(f"\n匹配项 {i+1}:")
    #     print(f"  GSO章节: {gso['chapter_id']} - {gso['chapter_title']}")
    #     print(f"  GSO关键词: {gso['topic_keywords']}")
    #     print(f"  候选项数量: {len(candidates)}")
        
    #     for j, candidate in enumerate(candidates[:3]):  # 只显示前3个候选项
    #         if candidate["comparison_data"]:
    #             ece = candidate["comparison_data"]
    #             print(f"    候选项{j+1} (分数: {candidate['score']:.4f}):")
    #             print(f"      ECE章节: {ece['chapter_id']} - {ece['chapter_title']}")
    #             print(f"      ECE关键词: {ece['topic_keywords']}")
    #         else:
    #             print(f"    候选项{j+1} (分数: {candidate['score']:.4f}): 数据缺失")

def main():
    """
    主函数
    """
    print("开始处理匹配关系...")
    
    try:
        # 处理匹配
        results = process_matches()
        
        # 保存结果
        output_file = r"d:/Documents/知识图谱agent/预处理脚本/comparison_results.json"
        save_comparison_results(results, output_file)
        
        # 打印摘要
        print_comparison_summary(results)
        
        print("\n处理完成!")
        
    except Exception as e:
        print(f"处理过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
