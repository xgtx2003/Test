# # import fitz  # PyMuPDF
# # import re
# # import json
# # from typing import List, Dict
# # from collections import defaultdict

# # # 章节标题正则（保持不变）
# # chapter_patterns = [
# #     re.compile(r'^(附\s*录\s*[A-Z])\s+(.+)$'),
# #     re.compile(r'^([A-Z](?:\.\d+)+)\s+(.+)$'),
# #     re.compile(r'^(\d+(?:\.\d+)*)(\s+)(.+)$'),
# # ]

# # def detect_chapter(line: str):
# #     for pattern in chapter_patterns:
# #         m = pattern.match(line)
# #         if m:
# #             return {
# #                 "chapter_id": m.group(1).strip(),
# #                 "chapter_title": m.group(len(m.groups())).strip()
# #             }
# #     return None

# # def build_tree(chapter_list: List[Dict]) -> List[Dict]:
# #     id_map = {}
# #     root = []
# #     for chap in chapter_list:
# #         chap["children"] = []
# #         id_map[chap["chapter_id"]] = chap

# #     for chap in chapter_list:
# #         parts = chap["chapter_id"].split(".")
# #         if len(parts) == 1 or chap["chapter_id"].startswith("附录"):
# #             root.append(chap)
# #         else:
# #             parent_id = ".".join(parts[:-1])
# #             parent = id_map.get(parent_id)
# #             if parent:
# #                 parent["children"].append(chap)
# #             elif len(parts) == 2 and parts[0].isupper():
# #                 appendix_id = f"附录{parts[0]}"
# #                 if appendix_id not in id_map:
# #                     id_map[appendix_id] = {
# #                         "chapter_id": appendix_id,
# #                         "chapter_title": appendix_id,
# #                         "raw_text": "",
# #                         "children": []
# #                     }
# #                     root.append(id_map[appendix_id])
# #                 id_map[appendix_id]["children"].append(chap)
# #             else:
# #                 root.append(chap)
# #     return root

# # def build_full_path(chapters: List[Dict], path_prefix=""):
# #     for chap in chapters:
# #         chap["full_path"] = f"{path_prefix}/{chap['chapter_id']} {chap['chapter_title']}" if path_prefix \
# #                            else f"{chap['chapter_id']} {chap['chapter_title']}"
# #         if chap.get("children"):
# #             build_full_path(chap["children"], chap["full_path"])

# # def parse_pdf_to_chapter_tree(pdf_path: str) -> List[Dict]:
# #     doc = fitz.open(pdf_path)
# #     lines = []
    
# #     # 改进的文本提取参数
# #     for page in doc:
# #         # text = page.get_text("text", flags=fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_MEDIABOX_CLIP)
# #         text = page.get_text("text", flags=fitz.TEXT_DEHYPHENATE | fitz.TEXT_MEDIABOX_CLIP)
# #         lines += [line.strip() for line in text.split("\n") if line.strip()]

# #     chapters = []
# #     current = None
# #     buffer = []

# #     for line in lines:
# #         # 过滤水印（示例）
# #         if "下载者：" in line and "批准者：" in line:
# #             continue
            
# #         chapter_info = detect_chapter(line)
# #         if chapter_info:
# #             if current:
# #                 current["raw_text"] = "\n".join(buffer).strip()
# #                 chapters.append(current)
# #                 buffer = []
# #             current = {
# #                 "chapter_id": chapter_info["chapter_id"],
# #                 "chapter_title": chapter_info["chapter_title"],
# #                 "raw_text": ""
# #             }
# #         else:
# #             buffer.append(line)

# #     if current:
# #         current["raw_text"] = "\n".join(buffer).strip()
# #         chapters.append(current)

# #     tree = build_tree(chapters)
# #     build_full_path(tree)
# #     return [n for n in tree if n.get("raw_text") or n.get("children")]

# # def extract_tables_from_pdf(pdf_path: str) -> List[Dict]:
# #     doc = fitz.open(pdf_path)
# #     all_tables = []
    
# #     for page_num, page in enumerate(doc):
# #         # 获取页面文本块（用于找表格标题）
# #         blocks = page.get_text("blocks", flags=fitz.TEXT_PRESERVE_LIGATURES)
# #         text_blocks = [b for b in blocks if b[6] == 0]  # 类型0为文本
        
# #         # 提取表格
# #         tabs = page.find_tables()
# #         if not tabs:
# #             continue
            
# #         for table_idx, tab in enumerate(tabs):
# #             # 获取表格数据
# #             table_data = tab.extract()
# #             if len(table_data) <= 1:  # 过滤空表
# #                 continue
                
# #             # 清理数据
# #             cleaned_data = [
# #                 [cell.replace('\n', ' ').strip() if cell else "" 
# #                 for cell in row] 
# #                 for row in table_data
# #             ]
            
# #             # 找表格标题（在表格上方最近的文本块）
# #             table_top = tab.bbox.y0
# #             best_title = None
# #             min_dist = float('inf')
            
# #             for block in text_blocks:
# #                 if "表" in block[4] and 0 < (table_top - block[3]) < 100:  # 100pt范围内
# #                     dist = table_top - block[3]
# #                     if dist < min_dist:
# #                         min_dist = dist
# #                         best_title = block[4].strip()
            
# #             table_id = best_title if best_title else f"表-页{page_num+1}-表{table_idx+1}"
# #             all_tables.append({
# #                 "table_id": table_id,
# #                 "table_content": cleaned_data
# #             })
    
# #     return all_tables

# # def main():
# #     import argparse
# #     parser = argparse.ArgumentParser()
# #     parser.add_argument("--pdf_path", default="GB∕T+38186-2019+商用车辆自动紧急制动系统（AEBS）性能要求及试验方法.pdf")
# #     parser.add_argument("--output", default="output.json")
# #     args = parser.parse_args()

# #     # 提取内容
# #     chapter_tree = parse_pdf_to_chapter_tree(args.pdf_path)
# #     tables = extract_tables_from_pdf(args.pdf_path)
    
# #     # 保存结果
# #     with open(args.output, "w", encoding="utf-8") as f:
# #         json.dump({
# #             "chapters": chapter_tree,
# #             "tables": tables
# #         }, f, ensure_ascii=False, indent=2)
    
# #     print(f"✅ 提取完成，共提取 {len(chapter_tree)} 个章节和 {len(tables)} 个表格")

# # if __name__ == "__main__":
# #     main()
# import fitz  # PyMuPDF
# import re

# def extract_full_text_with_filter(pdf_path, output_txt_path):
#     """
#     完整提取PDF文本到TXT文件，包含：
#     1. 自动过滤常见水印
#     2. 处理特殊编码
#     3. 保留原始段落结构
#     """
#     doc = fitz.open(pdf_path)
#     full_text = []
    
#     # 水印正则模式（根据您的文件调整）
#     watermark_patterns = [
#         re.compile(r'下载者：.*?批准者：.*?\d{2}:\d{2}:\d{2}'),
#         re.compile(r'犌犅／犜[\d—]+'),  # 处理GB/T特殊编码
#     ]
    
#     for page in doc:
#         h = page.rect.height
#         clip_rect = fitz.Rect(0, h*0.10, page.rect.width, h*0.90)
        
#         # # 最佳文本提取参数组合
#         # text = page.get_text("text", flags=
#         #     fitz.TEXT_PRESERVE_LIGATURES |  # 保留连字
#         #     fitz.TEXT_MEDIABOX_CLIP |       # 裁剪到页面内容区
#         #     fitz.TEXT_DEHYPHENATE           # 处理连字符
#         # )
#         text = page.get_text("text", clip=clip_rect, flags=
#             fitz.TEXT_PRESERVE_LIGATURES |
#             fitz.TEXT_MEDIABOX_CLIP |
#             fitz.TEXT_DEHYPHENATE
#         )
            
        
#         # 按行处理并过滤水印
#         cleaned_lines = []
#         for line in text.split('\n'):
#             line = line.strip()
#             if not line:
#                 continue
                
#             # 过滤水印
#             is_watermark = False
#             for pattern in watermark_patterns:
#                 if pattern.search(line):
#                     is_watermark = True
#                     break
#             if is_watermark:
#                 continue
                
#             # 处理特殊编码（示例：将"犌犅"转为"GB"）
#             line = line.replace('犌犅', 'GB').replace('／', '/')
#             cleaned_lines.append(line)
        
#         full_text.append("\n".join(cleaned_lines))
    
#     # 写入文本文件
#     with open(output_txt_path, "w", encoding="utf-8") as f:
#         f.write("\n\n".join(full_text))  # 用两个换行分隔页面
    
#     # 修正后的统计行（避免f-string中的反斜杠）
#     total_lines = sum(len(page.splitlines()) for page in full_text)
#     print(f"✅ 文本已提取到 {output_txt_path}")
#     print(f"总页数: {len(doc)}")
#     print(f"有效文本行: {total_lines}")

# # 使用示例
# extract_full_text_with_filter(
#     pdf_path="../示例文件/GB+11551-2014.pdf",
#     output_txt_path="extracted_full_text_1.txt"
# )


import fitz  # PyMuPDF
import re

# ---------- 新增 ----------
import re

import re

def fix_broken_chapters(lines: list[str]) -> list[str]:
    fixed = []
    i = 0
    n = len(lines)

    # 匹配章节编号的单个片段（如 3. 或 1. 或 A.）
    chapter_part_re = re.compile(r'^(?:[A-Z]|\d+)\.?$')

    while i < n:
        parts = []

        # 1. 连续匹配独立章节号片段，如 3. \n 1. \n 1.
        while i < n and chapter_part_re.match(lines[i].strip()):
            part = lines[i].strip().rstrip('.')
            parts.append(part)
            i += 1

        # 2. 判断是否还有类似 “1 标题” 的行，把 "1" 加入编号
        title = ""
        if i < n:
            line = lines[i].strip()
            m = re.match(r'^(\d+)\s+(.*)$', line)
            if m:
                part = m.group(1)
                title = m.group(2)
                parts.append(part)
                i += 1
            else:
                # 没有编号，整行作为标题
                title = line
                i += 1

        if parts:
            chapter_id = ".".join(parts)
            fixed.append(f"{chapter_id} {title}".strip())
        else:
            # 非编号开头的正常文本行
            fixed.append(lines[i - 1].strip())

    # ---------- 追加：把 “编号\n标题” 合并成 “编号 标题” ----------
    merged_final = []
    j = 0
    m = len(fixed)

    # 复用你的 chapter_patterns，但去掉捕获组
    num_pattern = re.compile(r'^\d+(?:\.\d+)*$')
    alpha_pattern = re.compile(r'^[A-Z](?:\.\d+)*$')

    while j < m:
        line = fixed[j].strip()
        next_line = fixed[j + 1].strip() if j + 1 < m else ""

        # 当前行是裸编号/字母编号，且下一行不是编号
        if (num_pattern.fullmatch(line) or alpha_pattern.fullmatch(line)) \
        and j + 1 < m \
        and not (num_pattern.match(next_line) or alpha_pattern.match(next_line)):
            merged_final.append(f"{line} {next_line}")
            j += 2
        else:
            merged_final.append(line)
            j += 1
    return merged_final

    # return fixed


# ---------- 新增结束 ----------

def merge_soft_wrapped_paragraphs(lines):
    """
    合并 OCR 导致的软换行（句子没有结束符，却换行了）
    """
    merged = []
    buffer = ""

    for line in lines:
        line = line.strip()
        if not line:
            if buffer:
                merged.append(buffer)
                buffer = ""
            continue
        if buffer and not buffer.endswith(('。', '；', '：', '”', '！', '？', '.', ';', ':', '"', '?', '!', '）', ')')):
            buffer += line  # 合并无结束符的换行
        else:
            if buffer:
                merged.append(buffer)
            buffer = line
    if buffer:
        merged.append(buffer)
    return merged

def extract_text_from_page_dict(page, clip_rect=None):
    data = page.get_text("dict", clip=clip_rect)
    lines_text = []

    for block in data["blocks"]:
        if block["type"] != 0:
            continue  # 非文本块

        for line in block.get("lines", []):
            line_text = ""
            last_span_right = None

            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                if not text:
                    continue

                # ---------- 可选：过滤图中文字 ----------
                if span["size"] < 6:  # 太小的字号
                    continue
                if len(text) <= 1 and span["size"] < 9:
                    continue
                # --------------------------------------

                # 补空格（防止“表2标题”粘连）
                if last_span_right is not None:
                    gap = span["bbox"][0] - last_span_right
                    if gap > span["size"] * 0.5:
                        line_text += " "

                line_text += text
                last_span_right = span["bbox"][2]

            if line_text.strip():
                lines_text.append(line_text.strip())

    return lines_text


def extract_full_text_with_filter(pdf_path, output_txt_path):
    doc = fitz.open(pdf_path)
    full_text = []
    watermark_patterns = [
        re.compile(r'下载者：.*?批准者：.*?\d{2}:\d{2}:\d{2}'),
        re.compile(r'犌犅／犜[\d—]+'),
    ]
    for page in doc:
        h = page.rect.height
        clip_rect = fitz.Rect(0, h*0.10, page.rect.width, h*0.90)
        text = page.get_text("text", clip=clip_rect, flags=
            fitz.TEXT_PRESERVE_LIGATURES |
            fitz.TEXT_MEDIABOX_CLIP |
            fitz.TEXT_DEHYPHENATE
        )

        # ---------- 新增 ----------
        # 先把 PyMuPDF 给的行合并断开的章节号
        raw_lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
        # raw_lines = extract_text_from_page_dict(page, clip_rect=clip_rect)
        merged_lines = fix_broken_chapters(raw_lines)
        paragraphs = merge_soft_wrapped_paragraphs(merged_lines)
        # ---------- 新增结束 ----------

        cleaned_lines = []
        for line in paragraphs:          # 注意：这里用 merged_lines
            if not line:
                continue
            is_watermark = any(p.search(line) for p in watermark_patterns)
            if is_watermark:
                continue
            line = line.replace('犌犅', 'GB').replace('／', '/')
            cleaned_lines.append(line)

        full_text.append("\n".join(cleaned_lines))

    with open(output_txt_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(full_text))
    total_lines = sum(len(p.splitlines()) for p in full_text)
    print(f"✅ 文本已提取到 {output_txt_path}")
    print(f"总页数: {len(doc)}")
    print(f"有效文本行: {total_lines}")

# # 使用示例
# extract_full_text_with_filter(
#     pdf_path="../示例文件/GB+11551-2014.pdf",
#     output_txt_path="extracted_full_text.txt"
# )

# 使用示例
extract_full_text_with_filter(
    # pdf_path="国标_车载事故紧急呼叫系统-征求意见稿.pdf",
    # pdf_path="GB 7258-2017 《机动车运行安全技术条件》.pdf",
    # pdf_path="../示例文件/GB+11551-2014.pdf",
    # pdf_path="GB∕T 38930-2020 民用轻小型无人机系统抗风性要求及试验方法.pdf",
    # pdf_path="GB∕T 38997-2020 轻小型多旋翼无人机飞行控制与导航系统通用要求.pdf",
    # pdf_path="../示例文件/GBT+43187-2023.pdf",
    # pdf_path="D:/Documents/知识图谱agent/示例文件/png/组合 1.pdf",
    pdf_path="D:\\Documents\\知识图谱agent\\示例文件\\GB+34660-2017 处理\\组合 1.pdf",
    output_txt_path="extracted_full_text_2.txt"
)


import fitz  # PyMuPDF
import re

def extract_text_from_page_dict(page, clip_rect=None):
    blocks = page.get_text("dict")["blocks"]
    lines = []

    for b in blocks:
        if b["type"] != 0:  # skip non-text blocks (like images)
            continue
        for line in b["lines"]:
            span_texts = []
            for span in line["spans"]:
                if clip_rect and not clip_rect.contains(fitz.Rect(span["bbox"])):
                    continue
                text = span["text"]
                if text.strip():
                    span_texts.append(text.strip())
            if span_texts:
                full_line = "".join(span_texts)
                lines.append(full_line)
    return lines


def fix_broken_chapters(lines):
    """
    合并被错误换行的章节号，如“4.2”、“2.3.1”等
    """
    fixed = []
    prev = ""
    pattern = re.compile(r'^\d+(\.\d+)*$')

    for line in lines:
        if pattern.match(line):
            prev += line  # 合并进上一行
        elif prev:
            fixed.append(prev + line)
            prev = ""
        else:
            fixed.append(line)
    return fixed


def merge_soft_wrapped_paragraphs(lines):
    """
    合并 OCR 导致的软换行（句子没有结束符，却换行了）
    """
    merged = []
    buffer = ""

    for line in lines:
        line = line.strip()
        if not line:
            if buffer:
                merged.append(buffer)
                buffer = ""
            continue
        if buffer and not buffer.endswith(('。', '；', '：', '”', '！', '？', '.', ';', ':', '"', '?', '!', '）', ')')):
            buffer += line  # 合并无结束符的换行
        else:
            if buffer:
                merged.append(buffer)
            buffer = line
    if buffer:
        merged.append(buffer)
    return merged

def extract_text_from_page_dict(page, clip_rect=None, y_tolerance=2.0):
    """
    从页面中提取视觉上一行的文本，按 y 坐标聚合
    """
    blocks = page.get_text("dict", clip=clip_rect)["blocks"]
    lines = []

    for b in blocks:
        if b["type"] != 0:  # 非文本块跳过
            continue
        for line in b["lines"]:
            line_str = ""
            last_y = None
            for span in line["spans"]:
                y = round(span["bbox"][1], 1)  # 精度可调
                text = span["text"].strip()
                if not text:
                    continue

                if last_y is None or abs(y - last_y) <= y_tolerance:
                    line_str += text
                else:
                    # 高度差超过阈值，认为是新的一行
                    lines.append(line_str.strip())
                    line_str = text
                last_y = y
            if line_str.strip():
                lines.append(line_str.strip())
    return lines


def extract_full_text_with_filter(pdf_path, output_txt_path):
    doc = fitz.open(pdf_path)
    full_text = []

    # 水印/噪声字符模式
    watermark_patterns = [
        re.compile(r'下载者：.*?批准者：.*?\d{2}:\d{2}:\d{2}'),
        re.compile(r'犌犅／犜[\d—]+'),
        re.compile(r'[犌犅／犜]{1,}'),  # 清除非汉字混杂干扰
    ]

    for page in doc:
        h = page.rect.height
        clip_rect = fitz.Rect(0, h * 0.10, page.rect.width, h * 0.90)

        raw_lines = extract_text_from_page_dict(page, clip_rect=clip_rect)

        # 修复章节断行
        fixed_lines = fix_broken_chapters(raw_lines)

        # # 合并软换行段落
        # merged_lines = merge_soft_wrapped_paragraphs(fixed_lines)

        # 清洗 OCR 噪声
        cleaned_lines = []
        for line in fixed_lines:
            if not line:
                continue
            if any(p.search(line) for p in watermark_patterns):
                continue
            line = line.replace("犌犅", "GB").replace("／", "/")
            cleaned_lines.append(line)

        full_text.append("\n".join(cleaned_lines))

    with open(output_txt_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(full_text))

    print(f"✅ 提取完成：{output_txt_path}")
    print(f"页数：{len(doc)}")
    print(f"有效段落：{sum(len(p.splitlines()) for p in full_text)}")

# 使用示例
extract_full_text_with_filter(
    pdf_path="D:\\Documents\\知识图谱agent\\示例文件\\GB+34660-2017 处理\\组合 1.pdf",
    output_txt_path="extracted_full_text_3.txt"
)

# import fitz  # PyMuPDF
# import re


# def extract_text_from_page_dict(page, clip_rect=None):
#     data = page.get_text("dict", clip=clip_rect)
#     lines_text = []

#     for block in data["blocks"]:
#         if block["type"] != 0:
#             continue  # 非文本块

#         for line in block.get("lines", []):
#             line_text = ""
#             last_span_right = None

#             for span in line.get("spans", []):
#                 text = span.get("text", "").strip()
#                 if not text:
#                     continue

#                 # ---------- 可选：过滤图中文字 ----------
#                 if span["size"] < 6:  # 太小的字号
#                     continue
#                 if len(text) <= 1 and span["size"] < 9:
#                     continue
#                 # --------------------------------------

#                 # 补空格（防止“表2标题”粘连）
#                 if last_span_right is not None:
#                     gap = span["bbox"][0] - last_span_right
#                     if gap > span["size"] * 0.5:
#                         line_text += " "

#                 line_text += text
#                 last_span_right = span["bbox"][2]

#             if line_text.strip():
#                 lines_text.append(line_text.strip())

#     return lines_text


# def fix_broken_chapters(lines):
#     fixed = []
#     i = 0
#     n = len(lines)

#     chapter_part_re = re.compile(r'^(?:[A-Z]|\d+)\.?$')

#     while i < n:
#         parts = []

#         while i < n and chapter_part_re.match(lines[i].strip()):
#             part = lines[i].strip().rstrip('.')
#             parts.append(part)
#             i += 1

#         title = ""
#         if i < n:
#             line = lines[i].strip()
#             m = re.match(r'^(\d+)\s+(.*)$', line)
#             if m:
#                 part = m.group(1)
#                 title = m.group(2)
#                 parts.append(part)
#                 i += 1
#             else:
#                 title = line
#                 i += 1

#         if parts:
#             chapter_id = ".".join(parts)
#             fixed.append(f"{chapter_id} {title}".strip())
#         else:
#             fixed.append(lines[i - 1].strip())

#     # 合并“编号\n标题”为“编号 标题”
#     merged_final = []
#     j = 0
#     m = len(fixed)

#     num_pattern = re.compile(r'^\d+(?:\.\d+)*$')
#     alpha_pattern = re.compile(r'^[A-Z](?:\.\d+)*$')

#     while j < m:
#         line = fixed[j].strip()
#         next_line = fixed[j + 1].strip() if j + 1 < m else ""

#         if (num_pattern.fullmatch(line) or alpha_pattern.fullmatch(line)) \
#                 and j + 1 < m \
#                 and not (num_pattern.match(next_line) or alpha_pattern.match(next_line)):
#             merged_final.append(f"{line} {next_line}")
#             j += 2
#         else:
#             merged_final.append(line)
#             j += 1

#     return merged_final


# def merge_soft_wrapped_paragraphs(lines):
#     merged = []
#     buffer = ""

#     for line in lines:
#         line = line.strip()
#         if not line:
#             if buffer:
#                 merged.append(buffer)
#                 buffer = ""
#             continue

#         is_new_para = bool(re.match(r'^(\d+(\.\d+)*|[A-Z](\.\d+)*)(\s+|$)', line))

#         if is_new_para:
#             if buffer:
#                 merged.append(buffer)
#             buffer = line
#         else:
#             if buffer and not buffer.endswith(('。', '；', '：', '”', '！', '？', '.', ';', ':', '"', '?', '!', '）', ')')):
#                 buffer += line
#             else:
#                 if buffer:
#                     merged.append(buffer)
#                 buffer = line

#     if buffer:
#         merged.append(buffer)

#     return merged


# def extract_full_text_with_filter(pdf_path, output_txt_path):
#     doc = fitz.open(pdf_path)
#     full_text = []

#     watermark_patterns = [
#         re.compile(r'下载者：.*?批准者：.*?\d{2}:\d{2}:\d{2}'),
#         re.compile(r'犌犅／犜[\d—]+'),
#         re.compile(r'[犌犅／犜]{1,}'),
#     ]

#     for page in doc:
#         h = page.rect.height
#         clip_rect = fitz.Rect(0, h * 0.10, page.rect.width, h * 0.90)

#         raw_lines = extract_text_from_page_dict(page, clip_rect=clip_rect)
#         fixed_lines = fix_broken_chapters(raw_lines)
#         merged_lines = merge_soft_wrapped_paragraphs(fixed_lines)

#         cleaned_lines = []
#         for line in merged_lines:
#             if not line:
#                 continue
#             if any(p.search(line) for p in watermark_patterns):
#                 continue
#             line = line.replace("犌犅", "GB").replace("／", "/")
#             cleaned_lines.append(line)

#         full_text.append("\n".join(cleaned_lines))

#     with open(output_txt_path, "w", encoding="utf-8") as f:
#         f.write("\n\n".join(full_text))

#     print(f"✅ 提取完成：{output_txt_path}")
#     print(f"页数：{len(doc)}")
#     print(f"有效段落：{sum(len(p.splitlines()) for p in full_text)}")


# # 使用示例
# extract_full_text_with_filter(
#     pdf_path="D:\\Documents\\知识图谱agent\\示例文件\\GB+34660-2017 处理\\组合 1.pdf",
#     output_txt_path="extracted_full_text.txt"
# )