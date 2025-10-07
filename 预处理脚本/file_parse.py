import json
import os
from typing import List, Tuple, Dict, Any

def flatten_chapters(chapters: List[Dict], file_name: str, section_name: str) -> Tuple[List[str], List[Tuple[str, str, str]]]:
    """
    递归地铺平所有章节，提取所需字段
    
    Args:
        chapters: 章节列表
        file_name: 文件名
        section_name: 章节名
    
    Returns:
        Tuple[List[str], List[Tuple[str, str, str]]]: (章节数据行列表, 元组数组)
    """
    chapter_lines = []
    chapter_tuples = []
    
    for chapter in chapters:
        # 只处理有chapter_id的章节
        if 'chapter_id' in chapter:
            # 提取所需字段
            chapter_data = {
                # 'chapter_id': chapter.get('chapter_id', ''),
                'topic_keywords': chapter.get('topic_keywords', []),
                'parameters': chapter.get('parameters', []),
                'context_keywords': chapter.get('context_keywords', []),
                'table_headers': chapter.get('table_headers', [])
            }
            
            # 将字典转换为JSON字符串（一行）
            chapter_line = json.dumps(chapter_data, ensure_ascii=False, separators=(',', ':'))
            chapter_lines.append(chapter_line)
            
            # 添加对应的元组
            chapter_tuples.append((file_name, section_name, chapter.get('chapter_id', '')))
        
        # 递归处理子章节
        if 'children' in chapter and chapter['children']:
            child_lines, child_tuples = flatten_chapters(chapter['children'], file_name, section_name)
            chapter_lines.extend(child_lines)
            chapter_tuples.extend(child_tuples)
    
    return chapter_lines, chapter_tuples

def parse_json_file(json_file_path: str, output_txt_path: str, output_tuples_path: str = None):
    """
    解析JSON文件，提取regulation文件的章节信息
    
    Args:
        json_file_path: 输入的JSON文件路径
        output_txt_path: 输出的txt文件路径
        output_tuples_path: 输出元组数组的文件路径（可选）
    """
    try:
        # 读取JSON文件
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        all_chapter_lines = []
        all_chapter_tuples = []
        
        # 遍历所有文件
        for file_item in data:
            file_name = file_item.get('file', '')
            
            # 只处理file为regulation的项目
            if file_name.lower() == 'regulation':
                sections = file_item.get('sections', [])
                
                # 遍历所有section
                for section in sections:
                    section_name = section.get('section', '')
                    chapters = section.get('chapters', [])
                    
                    # 铺平所有章节
                    chapter_lines, chapter_tuples = flatten_chapters(chapters, file_name, section_name)
                    all_chapter_lines.extend(chapter_lines)
                    all_chapter_tuples.extend(chapter_tuples)
        
        # 将章节数据写入txt文件
        with open(output_txt_path, 'w', encoding='utf-8') as f:
            for line in all_chapter_lines:
                f.write(line + '\n')
        
        # 如果指定了元组输出路径，将元组数组保存为JSON文件
        if output_tuples_path:
            with open(output_tuples_path, 'w', encoding='utf-8') as f:
                json.dump(all_chapter_tuples, f, ensure_ascii=False, indent=2)
        
        print(f"处理完成！")
        print(f"共处理 {len(all_chapter_lines)} 个章节")
        print(f"章节数据已保存到: {output_txt_path}")
        if output_tuples_path:
            print(f"元组数组已保存到: {output_tuples_path}")
        
        return all_chapter_lines, all_chapter_tuples
        
    except Exception as e:
        print(f"处理过程中出现错误: {e}")
        return [], []

def main():
    """
    主函数，示例用法
    """
    # 示例文件路径
    json_file_path = r"d:/Documents/知识图谱agent/示例文件/temp/CELEX_42006X1227(06)_EN_TXT/CELEX_42006X1227(06)_EN_TXT.json"
    # json_file_path = r"D:/Documents/知识图谱agent/示例文件/temp/GSO-1040-2000-E机动车- 轻型柴油引擎车辆大气污染物排放允许限值/GSO-1040-2000-E机动车- 轻型柴油引擎车辆大气污染物排放允许限值.json"
    output_txt_path = r"d:/Documents/知识图谱agent/示例文件/temp/parsed_chapters.txt"
    output_tuples_path = r"d:/Documents/知识图谱agent/示例文件/temp/chapter_tuples.json"

    # 解析文件
    chapter_lines, chapter_tuples = parse_json_file(json_file_path, output_txt_path, output_tuples_path)
    
    # 打印前几个样例
    if chapter_lines:
        print("\n前3个章节数据示例:")
        for i, line in enumerate(chapter_lines[:3]):
            print(f"{i+1}: {line}")
    
    if chapter_tuples:
        print("\n前3个元组示例:")
        for i, tuple_item in enumerate(chapter_tuples[:3]):
            print(f"{i+1}: {tuple_item}")

if __name__ == "__main__":
    main()