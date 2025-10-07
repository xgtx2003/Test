import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import re
import os

def extract_pdf_with_ocr(pdf_path, output_txt_path):
    """
    使用OCR提取PDF文本内容（最终修正版）
    主要改进：
    1. 修复了图像转换问题
    2. 添加了Tesseract路径检查
    3. 优化了图像预处理
    4. 改进了水印过滤
    """
    # 检查Tesseract路径
    try:
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Windows默认路径
    except Exception as e:
        print(f"⚠️ Tesseract未正确安装或路径错误: {e}")
        print("请从 https://github.com/UB-Mannheim/tesseract/wiki 安装Tesseract")
        return

    doc = fitz.open(pdf_path)
    full_text = []
    
    # 增强的水印过滤正则
    watermark_re = re.compile(
        r'上海机动车检测认证技术研究中心有限公司内部文件，不得外传！|'
        r'下载者：.*?批准者：.*?\d{1,2}:\d{2}:\d{2}|'
        r'犌犅／犜[\d—]+'
    )
    
    for page_num in range(len(doc)):
        try:
            # 将PDF页面转为高质量图像（600 DPI）
            pix = doc[page_num].get_pixmap(
                dpi=600,
                matrix=fitz.Matrix(2.0, 2.0),  # 提高分辨率
                colorspace="rgb",
                alpha=False
            )
            
            # 转换为PIL Image并进行预处理
            img = Image.open(io.BytesIO(pix.tobytes("ppm")))
            
            # 图像增强处理
            img = img.convert('L')  # 转为灰度
            img = img.point(lambda x: 0 if x < 140 else 255)  # 二值化阈值调整
            
            # 使用Tesseract OCR识别（调整参数）
            text = pytesseract.image_to_string(
                img,
                lang='chi_sim+eng',
                config='--psm 6 --oem 3'  # 页面分段模式为"假设统一的文本块"
            )
            
            # 高级过滤处理
            cleaned_lines = []
            for line in text.split('\n'):
                line = line.strip()
                if line and not watermark_re.search(line):
                    # 替换常见乱码字符
                    line = (line.replace('犌犅', 'GB')
                          .replace('／', '/')
                          .replace('犜', 'T')
                          .replace('犃', 'A'))
                    cleaned_lines.append(line)
            
            if cleaned_lines:
                full_text.append("\n".join(cleaned_lines))
            
        except Exception as e:
            print(f"⚠️ 第 {page_num+1} 页处理失败: {e}")
            continue
    
    # 保存结果
    try:
        with open(output_txt_path, "w", encoding="utf-8", errors="replace") as f:
            f.write("\n\n".join(full_text))
        
        print(f"✅ OCR提取完成，结果保存至 {output_txt_path}")
        print(f"提取页数：{len(doc)}")
        print(f"有效文本页：{len(full_text)}")
        # print(f"总文本行数：{sum(len(page.split('\n')) for page in full_text)}")
        
    except Exception as e:
        print(f"⚠️ 无法保存结果文件: {e}")

if __name__ == "__main__":
    # 配置参数
    input_pdf = "GB∕T+38186-2019+商用车辆自动紧急制动系统（AEBS）性能要求及试验方法.pdf"
    output_txt = "ocr_extracted_text_final.txt"
    
    # 检查文件是否存在
    if not os.path.exists(input_pdf):
        print(f"⚠️ 输入文件不存在: {input_pdf}")
    else:
        extract_pdf_with_ocr(input_pdf, output_txt)