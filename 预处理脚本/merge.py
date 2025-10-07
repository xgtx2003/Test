import json
from collections import defaultdict

def load_json_file(filepath):
    """加载JSON文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def build_chapter_index(tree_data):
    """构建chapter索引，key为(file, section, chapter_id)，value为chapter对象的引用"""
    chapter_index = {}
    section_index = {}
    
    def add_chapter_recursive(chapter, file_name, section_name):
        """递归添加章节及其子章节到索引中"""
        if 'chapter_id' in chapter:
            chapter_id = chapter['chapter_id']
            chapter_key = (file_name, section_name, chapter_id)
            chapter_index[chapter_key] = chapter
        
        # 递归处理子章节
        if 'children' in chapter:
            for child_chapter in chapter['children']:
                add_chapter_recursive(child_chapter, file_name, section_name)
    
    for file_data in tree_data:
        file_name = file_data['file']
        for section in file_data['sections']:
            section_name = section['section']
            section_key = (file_name, section_name)
            section_index[section_key] = section
            
            # 处理每个顶级章节
            for chapter in section['chapters']:
                add_chapter_recursive(chapter, file_name, section_name)
    
    return chapter_index, section_index

def merge_final_tree_data(chapter_index, final_tree_data):
    """将final_tree的数据融合到tree中 - O(n)复杂度"""
    merged_count = 0
    not_found_count = 0
    
    for final_section in final_tree_data:
        file_name = final_section['file']
        section_name = final_section['section']
        
        for final_chapter in final_section['chapters']:
            chapter_id = final_chapter['chapter_id']
            chapter_key = (file_name, section_name, chapter_id)
            
            # O(1)查找
            tree_chapter = chapter_index.get(chapter_key)
            
            if tree_chapter:
                # 直接修改引用的对象
                tree_chapter['parameters'] = final_chapter.get('paramaters', [])
                tree_chapter['topic_keywords'] = final_chapter.get('topic_keywords', [])
                tree_chapter['context_keywords'] = final_chapter.get('context_keywords', [])
                tree_chapter['refs'] = final_chapter.get('refs', [])
                tree_chapter['table_headers'] = final_chapter.get('table_headers', [])
                merged_count += 1
            else:
                print(f"未找到对应的chapter: {file_name} -> {section_name} -> {chapter_id}")
                not_found_count += 1
    
    return merged_count, not_found_count

def merge_result_data(chapter_index, result_data):
    """将result的experiments数据融合到tree中 - O(n)复杂度"""
    merged_count = 0
    not_found_count = 0
    
    for result_section in result_data:
        file_name = result_section['file']
        section_name = result_section['section']
        experiments_groups = result_section.get('experiments', [])
        
        # 遍历每个实验组
        for experiments_group in experiments_groups:
            if not experiments_group:
                continue
                
            # 获取第一个实验的chapter_id作为该组的定位标识
            first_experiment = experiments_group[0]
            chapter_id = first_experiment.get('chapter_id')
            
            if not chapter_id:
                print(f"实验组缺少chapter_id: {experiments_group}")
                not_found_count += 1
                continue
            
            chapter_key = (file_name, section_name, chapter_id)
            # O(1)查找对应的章节
            chapter = chapter_index.get(chapter_key)
            
            if chapter:
                # 将该组实验添加到对应章节的experiments字段
                if 'experiments' not in chapter:
                    chapter['experiments'] = []
                chapter['experiments'].extend(experiments_group)
                merged_count += 1
            else:
                print(f"未找到对应的chapter: {file_name} -> {section_name} -> {chapter_id}")
                not_found_count += 1
    
    return merged_count, not_found_count

def main():
    # 加载三个JSON文件
    print("加载JSON文件...")
    tree_data = load_json_file('output.json')
    final_tree_data = load_json_file('D:/Documents/知识图谱agent/示例文件/temp/final_tree.json')
    result_data = load_json_file('D:/Documents/知识图谱agent/示例文件/temp/result.json')

    # 构建索引 - O(n)
    print("构建索引...")
    chapter_index, section_index = build_chapter_index(tree_data)
    print(f"章节索引数量: {len(chapter_index)}")
    print(f"节索引数量: {len(section_index)}")
    
    # 融合数据 - O(n)
    print("开始融合final_tree数据...")
    chapter_merged, chapter_not_found = merge_final_tree_data(chapter_index, final_tree_data)
    print(f"章节数据融合: 成功{chapter_merged}个, 未找到{chapter_not_found}个")
    
    print("开始融合result数据...")
    section_merged, section_not_found = merge_result_data(chapter_index, result_data)
    print(f"实验数据融合: 成功{section_merged}个, 未找到{section_not_found}个")
    
    # 保存融合后的数据
    output_file = 'merged_tree.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(tree_data, f, ensure_ascii=False, indent=2)
    
    print(f"融合完成，结果保存到: {output_file}")
    
    # 输出统计信息
    total_chapters = len(chapter_index)
    chapters_with_params = 0
    chapters_with_keywords = 0
    chapters_with_experiments = 0
    
    for chapter in chapter_index.values():
        if chapter.get('parameters'):
            chapters_with_params += 1
        if chapter.get('topic_keywords'):
            chapters_with_keywords += 1
        if chapter.get('experiments'):
            chapters_with_experiments += 1
    
    print(f"\n统计信息:")
    print(f"总章节数: {total_chapters}")
    print(f"包含参数的章节: {chapters_with_params}")
    print(f"包含主题关键词的章节: {chapters_with_keywords}")
    print(f"包含试验数据的章节: {chapters_with_experiments}")

if __name__ == "__main__":
    main()