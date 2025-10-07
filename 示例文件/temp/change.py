import pandas as pd
import openpyxl
from openpyxl.utils.dataframe import dataframe_to_rows
import json

def convert_single_to_double_quotes(text):
    """
    将字符串中的所有单引号转换为双引号
    
    Args:
        text (str): 输入字符串
    
    Returns:
        str: 转换后的字符串
    """
    if not isinstance(text, str):
        return text
    
    return text.replace("'", "\"")

def modify_first_column_from_row2(excel_file_path):
    """
    读取Excel文件第二行开始的第一列数据，修改后覆盖回原位
    
    Args:
        excel_file_path (str): Excel文件路径
    """
    try:
        # 读取Excel文件
        df = pd.read_excel(excel_file_path, header=None)  # 不设置表头，读取所有数据
        
        print(f"原始数据形状: {df.shape}")
        print("原始数据预览:")
        # print(df.head())
        
        # 获取从第二行开始的第一列数据（索引从0开始，所以第二行是索引1）
        column_data = df.iloc[1:, 0]  # 从第二行开始，第一列
        default_score = -1
        print(f"\n需要修改的数据行数: {len(column_data)}")
        
        modified_data = []
        for i, line in enumerate(column_data, 1):
            line = str(line).strip()
            line = convert_single_to_double_quotes(line)
            json_list = json.loads(line)
            json_list = convert_single_to_double_quotes(json_list)
            for item in enumerate(json_list, 1):
                print(item)
                score = item.get('score', default_score) if isinstance(item, dict) else default_score
                chapter_path = item.get('chapter_path',None) if isinstance(item, dict) else None
                print(f"\"score\":{score}, \"chapter_path\":{chapter_path}")
        
        # print("\n修改后的数据:")
        # print(modified_data)
        
        # # 将修改后的数据覆盖回原位
        # df.iloc[1:, 0] = modified_data
        
        # # 保存回原文件（覆盖）
        # df.to_excel(excel_file_path, index=False, header=False)
        
        # print(f"\n✅ 修改完成！文件已保存: {excel_file_path}")
        return True
        
    except Exception as e:
        print(f"❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    excel_file_path = r'示例文件/temp/R048r12e/comparison.xlsx'  # 替换为你的文件路径
    modify_first_column_from_row2(excel_file_path)