import json
import pandas as pd
from pandas import json_normalize

def complex_json_to_excel():
  
    json_file_path = r'示例文件/temp/CELEX_42006X1227(06)_EN_TXT/selected_results.json'
    excel_file_path = r'示例文件/temp/CELEX_42006X1227(06)_EN_TXT/selected.xlsx'
    # json_file_path = r'示例文件/temp/R048r12e/selected_results.json'
    # excel_file_path = r'示例文件/temp/R048r12e/selected.xlsx'

    try:
        # 读取JSON文件
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        df = json_normalize(data)
        with pd.ExcelWriter(excel_file_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Sheet1',index=False)
                
        print(f"✅ 转换成功！")
        print(f"   输入: {json_file_path}")
        print(f"   输出: {excel_file_path}")
        print(f"   原始数据行数: {len(df)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 转换失败: {e}")
        return False

if __name__ == "__main__":
    complex_json_to_excel()