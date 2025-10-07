import json
import os

def flatten_chapters(chapters):
    """递归铺平章节结构"""
    flattened = []
    for chapter in chapters:
        # 添加当前章节
        if 'chapter_id' in chapter:
            flattened.append(chapter)
        
        # 递归处理子章节
        if 'children' in chapter and chapter['children']:
            flattened.extend(flatten_chapters(chapter['children']))
    
    return flattened


def generate_query_objects(json_file_path, output_file_path):
    """
    从JSON文件中生成query对象
    """
    with open(json_file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
    
    query_objects = []
    
    # 遍历所有文件
    for file_item in data:
        file_name = file_item.get('file', '')
        
        # 只处理file为"regulation"的项目
        if file_name == 'regulation':
            sections = file_item.get('sections', [])
            
            for section in sections:
                section_name = section.get('section', '')
                chapters = section.get('chapters', [])
                
                # 铺平所有章节
                flattened_chapters = flatten_chapters(chapters)
                
                # 为每个章节生成query对象
                for chapter in flattened_chapters:
                    chapter_id = chapter.get('chapter_id', '')
                    
                    # 提取指定字段
                    topic_keywords = chapter.get('topic_keywords', [])
                    parameters = chapter.get('parameters', [])
                    context_keywords = chapter.get('context_keywords', [])
                    table_headers = chapter.get('table_headers', [])
                    
                    # 构建query字符串（JSON格式）
                    query_data = {
                        'topic_keywords': topic_keywords,
                        'parameters': parameters,
                        'context_keywords': context_keywords,
                        'table_headers': table_headers
                    }
                    
                    # 创建query对象
                    query_object = {
                        'file': file_name,
                        'section': section_name,
                        'chapter_id': chapter_id,
                        'query': json.dumps(query_data, ensure_ascii=False)
                    }
                    
                    query_objects.append(query_object)
    
    # 保存到文件
    with open(output_file_path, 'w', encoding='utf-8') as file:
        json.dump(query_objects, file, ensure_ascii=False, indent=2)
    
    print(f"生成了 {len(query_objects)} 个query对象")
    print(f"已保存到: {output_file_path}")
    
    return query_objects

if __name__ == "__main__":
    # 输入文件路径
    input_file = r"d:/Documents/知识图谱agent/示例文件/temp/GSO-1040-2000-E机动车- 轻型柴油引擎车辆大气污染物排放允许限值/GSO-1040-2000-E机动车- 轻型柴油引擎车辆大气污染物排放允许限值.json"

    # 输出文件路径
    output_file = r"d:/Documents/知识图谱agent/示例文件/temp/query_objects.json"

    # 生成query对象
    query_objects = generate_query_objects(input_file, output_file)
    
    # 打印前几个示例
    print("\n前3个query对象示例:")
    for i, obj in enumerate(query_objects[:3]):
        print(f"\n对象 {i+1}:")
        print(f"  file: {obj['file']}")
        print(f"  section: {obj['section']}")
        print(f"  chapter_id: {obj['chapter_id']}")
        print(f"  query: {obj['query']}")
