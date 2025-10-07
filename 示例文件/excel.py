import json
import pandas as pd
from pandas import json_normalize

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


def complex_json_to_excel():
  
    json_file_path = r'示例文件/temp/CELEX_42006X1227(06)_EN_TXT/comparison_results.json'
    excel_file_path = r'示例文件/temp/CELEX_42006X1227(06)_EN_TXT/comparison.xlsx'
    # json_file_path = r'示例文件/temp/R048r12e/comparison_results.json'
    # excel_file_path = r'示例文件/temp/R048r12e/comparison.xlsx'

    # tmp_path = r'示例文件/temp/R048r12e/temp.txt'
    # short_path = r'示例文件/temp/R048r12e/short2.xlsx'
    tmp_path = r'示例文件/temp/CELEX_42006X1227(06)_EN_TXT/temp.txt'
    short_path = r'示例文件/temp/CELEX_42006X1227(06)_EN_TXT/short2.xlsx'
    try:
        # 读取JSON文件
        # with open(json_file_path, 'r', encoding='utf-8') as f:
        #     data = json.load(f)
        
        # df = json_normalize(data)
        # candidates = df["candidates"]
        # with open(tmp_path, 'w', encoding='utf-8') as f:
        #   for item in candidates:
        #     line = json.dumps(item)
        #     print(line)
        #     f.write(line+'\n')
        #     print("------------")
        
        start_row=0
        with open(tmp_path, 'r', encoding='utf-8') as f:
            with pd.ExcelWriter(short_path, engine='openpyxl') as writer:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()  # 去除首尾空白字符
                    data = json.loads(line)
                    df = json_normalize(data)
                    # scores = df["score"]
                    # paths = df["chapter_path"]
                    # output = df[["score","chapter_path"]]
                    
                    df.to_excel(writer, sheet_name='Sheet1',startrow=start_row,index=False,header=(start_row == 0))
                    
                    start_row += len(df)+1
                
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