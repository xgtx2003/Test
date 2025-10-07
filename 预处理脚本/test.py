import fitz  # PyMuPDF
import re
import json
import os
from typing import List, Dict, Tuple
from collections import defaultdict

chapter_patterns = [
    re.compile(r'^(附\s*录\s*[A-Z])\s+(.+)$'),
    re.compile(r'^([A-Z](?:\.\d+)+)\s+(.+)$'),
    re.compile(r'^(\d+(?:\.\d+)*)(\s+)(.+)$'),
]

def detect_chapter(line: str):
    for pattern in chapter_patterns:
        m = pattern.match(line)
        if m:
            return {
                "chapter_id": m.group(1).strip(),
                "chapter_title": m.group(len(m.groups())).strip(),
                "title_in_next_line": True
            }
    return None


def build_tree(chapter_list: List[Dict]) -> List[Dict]:
    id_map = {}
    root = []

    for chap in chapter_list:
        chap["children"] = []
        id_map[chap["chapter_id"]] = chap

    for chap in chapter_list:
        parts = chap["chapter_id"].split(".")
        if len(parts) == 1 or chap["chapter_id"].startswith("附录"):
            root.append(chap)
        else:
            parent_id = ".".join(parts[:-1])
            parent = id_map.get(parent_id)
            if parent:
                parent["children"].append(chap)
            else:
                if len(parts) == 2 and len(parts[0]) == 1 and parts[0].isupper():
                    appendix_id = f"附录{parts[0]}"
                    appendix_title = f"附录{parts[0]}"
                    if appendix_id not in id_map:
                        appendix_node = {
                            "chapter_id": appendix_id,
                            "chapter_title": appendix_title,
                            "raw_text": "",
                            "children": []
                        }
                        id_map[appendix_id] = appendix_node
                        root.append(appendix_node)
                    id_map[appendix_id]["children"].append(chap)
                else:
                    root.append(chap)
    return root

def build_full_path(chapters: List[Dict], path_prefix=""):
    for chap in chapters:
        if path_prefix:
            chap["full_path"] = f"{path_prefix}/{chap['chapter_id']} {chap['chapter_title']}"
        else:
            chap["full_path"] = f"{chap['chapter_id']} {chap['chapter_title']}"
        if chap.get("children"):
            build_full_path(chap["children"], chap["full_path"])

def fullwidth_to_halfwidth(text: str) -> str:
    result = []
    for char in text:
        code = ord(char)
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        else:
            result.append(char)
    return ''.join(result)

def build_term_dict(raw_text: str) -> Dict[str, str]:
    text = re.sub(r'\n+', '\n', raw_text.strip())
    pattern = re.compile(
        r'^\d+\.\d+\n'
        r'(?P<cn>[^\n]*?)\s*'
        r'(?P<en>[A-Za-z].*?)\s*(?=\n)',
        re.MULTILINE
    )

    term_map = {}
    for m in pattern.finditer(text):
        cn = m.group("cn").strip()
        en = m.group("en").strip()
        if cn and en:
            term_map[cn] = en
    return term_map

def extract_terms_with_abbr_from_terms_section(raw_text: str) -> Dict[str, Dict[str, str]]:
    """
    提取术语章节中的中英文术语及缩写
    返回格式：
    {
      "中文术语": {
         "en": "英文术语",
         "abbr": "缩写（如有）"
      }
    }
    """
    term_map = {}
    text = re.sub(r'\n+', '\n', raw_text.strip())

    pattern = re.compile(
        r'(?P<cn>[\u4e00-\u9fff（）()·\s]{2,})'        # 中文部分
        r'\s*'                                         # 可选空格
        r'(?P<en>[A-Za-z][A-Za-z\s\-/]*)'              # 英文术语
        r'(?:[;；:：]?\s*(?P<abbr>[A-Z0-9·]+))?',       # 可选缩写
        re.MULTILINE
    )


    for m in pattern.finditer(text):
        cn = m.group("cn").strip()
        en = m.group("en").strip()
        abbr = m.group("abbr").strip() if m.group("abbr") else ""

        term_map[cn] = {"en": en}
        if abbr:
            term_map[cn]["abbr"] = abbr

    return term_map

def extract_abbr_terms_from_symbols_section(raw_text: str) -> Dict[str, Dict[str, str]]:
    """
    提取“符号和缩略语”章节的中英缩写映射，返回以中文为键的结构：
    {
        "中文": {
            "abbr": "缩写",
            "en": "英文释义"
        }
    }
    """
    abbr_map = {}
    # 清理文本
    text = re.sub(r'\n+', '\n', raw_text.strip())

    # 匹配模式：ACLR: 邻道泄漏功率比 (Adjacent Channel Leakage Power Ratio)
    pattern = re.compile(
        r'(?P<abbr>[A-Za-z0-9·\-_]+)\s*[:：]?\s*'
        r'(?P<cn>[\u4e00-\u9fff·]+)'
        r'(?:[（）()]*\s*(?P<en>[A-Za-z\s/\-]+)\s*[（）()]*)?'
    )

    for m in pattern.finditer(text):
        abbr = m.group("abbr").strip()
        cn = m.group("cn").strip("（）()").strip()
        en = m.group("en").strip() if m.group("en") else ""

        if cn:
            abbr_map[cn] = {}
            if abbr:
                abbr_map[cn]["abbr"] = abbr
            if en:
                abbr_map[cn]["en"] = en

    return abbr_map

# def fix_broken_chapters(lines: list[str]) -> list[str]:
#     fixed = []
#     i = 0
#     n = len(lines)

#     # 匹配章节编号的单个片段（如 3. 或 1. 或 A.）
#     chapter_part_re = re.compile(r'^(?:[A-Z]|\d+)\.?$')

#     while i < n:
#         parts = []

#         # 1. 连续匹配独立章节号片段，如 3. \n 1. \n 1.
#         while i < n and chapter_part_re.match(lines[i].strip()):
#             part = lines[i].strip().rstrip('.')
#             parts.append(part)
#             i += 1

#         # 2. 判断是否还有类似 “1 标题” 的行，把 "1" 加入编号
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
#                 # 没有编号，整行作为标题
#                 title = line
#                 i += 1

#         if parts:
#             chapter_id = ".".join(parts)
#             fixed.append(f"{chapter_id} {title}".strip())
#         else:
#             # 非编号开头的正常文本行
#             fixed.append(lines[i - 1].strip())

#     # ---------- 追加：把 “编号\n标题” 合并成 “编号 标题” ----------
#     merged_final = []
#     j = 0
#     m = len(fixed)

#     # 复用你的 chapter_patterns，但去掉捕获组
#     num_pattern = re.compile(r'^\d+(?:\.\d+)*$')
#     alpha_pattern = re.compile(r'^[A-Z](?:\.\d+)*$')

#     while j < m:
#         line = fixed[j].strip()
#         next_line = fixed[j + 1].strip() if j + 1 < m else ""

#         # 当前行是裸编号/字母编号，且下一行不是编号
#         if (num_pattern.fullmatch(line) or alpha_pattern.fullmatch(line)) \
#         and j + 1 < m \
#         and not (num_pattern.match(next_line) or alpha_pattern.match(next_line)):
#             merged_final.append(f"{line} {next_line}")
#             j += 2
#         else:
#             merged_final.append(line)
#             j += 1
#     return merged_final

# def fix_broken_chapters(lines: list[str]) -> list[str]:
#     merged_final = []
#     j = 0
#     m = len(lines)

#     # 复用你的 chapter_patterns，但去掉捕获组
#     num_pattern = re.compile(r'^\d+(?:\.\d+)*$')
#     alpha_pattern = re.compile(r'^[A-Z](?:\.\d+)*$')

#     while j < m:
#         line = lines[j].strip()
#         next_line = lines[j + 1].strip() if j + 1 < m else ""

#         # 当前行是裸编号/字母编号，且下一行不是编号
#         if (num_pattern.fullmatch(line) or alpha_pattern.fullmatch(line)) \
#         and j + 1 < m \
#         and not (num_pattern.match(next_line) or alpha_pattern.match(next_line)):
#             merged_final.append(f"{line} {next_line}")
#             j += 2
#         else:
#             merged_final.append(line)
#             j += 1
#     return merged_final

import re

def fix_broken_chapters(lines: list[str]) -> list[str]:
    fixed = []
    i = 0
    n = len(lines)

    # 编号独立片段（如 "3." / "A." / "1"），允许中间有空格
    chapter_part_re = re.compile(r'^(?:[A-Z]|\d+)\.?$')

    # 先全局预处理：去掉编号中间的多余空格
    def normalize_chapter_spaces(s: str) -> str:
        # 把像 "5. 3. 1" 这样的，统一去掉点后的空格
        return re.sub(r'\s*\.\s*', '.', s.strip())

    lines = [normalize_chapter_spaces(line) for line in lines]

    # 第一步：合并分散的编号 + 标题
    while i < n:
        parts = []
        title = ""

        # 连续的单编号片段
        while i < n and chapter_part_re.match(lines[i]):
            part = lines[i].rstrip('.')
            parts.append(part)
            i += 1

        # 编号+标题在同一行
        if i < n:
            line = lines[i]
            m = re.match(r'^(\d+(?:\.\d+)*)\s+(.*)$', line)
            if m:
                parts.append(m.group(1))
                title = m.group(2)
                i += 1
            else:
                title = line
                i += 1

        if parts:
            chapter_id = ".".join(parts)
            fixed.append(f"{chapter_id} {title}".strip())
        else:
            fixed.append(title)

    # 第二步：裸编号 + 下一行标题
    merged_final = []
    j = 0
    m = len(fixed)

    num_pattern = re.compile(r'^\d+(?:\.\d+)*$')
    alpha_pattern = re.compile(r'^[A-Z](?:\.\d+)*$')

    while j < m:
        line = fixed[j].strip()
        next_line = fixed[j + 1].strip() if j + 1 < m else ""

        if (num_pattern.fullmatch(line) or alpha_pattern.fullmatch(line)) \
           and j + 1 < m \
           and not (num_pattern.match(next_line) or alpha_pattern.match(next_line)):
            merged_final.append(f"{line} {next_line}")
            j += 2
        else:
            merged_final.append(line)
            j += 1

    return merged_final


# def extract_full_text_with_filter(pdf_path: str, y_tol=3, x_tol=5):
#     doc = fitz.open(pdf_path)
#     all_lines = []

#     for page in doc:
#         spans_all = []

#         h = page.rect.height
#         clip_rect = fitz.Rect(0, h*0.10, page.rect.width, h*0.90)

#         # 提取所有 span 信息
#         for block in page.get_text("dict", clip=clip_rect)["blocks"]:
#             if block["type"] != 0:
#                 continue
#             for line in block["lines"]:
#                 for span in line["spans"]:
#                     text = span["text"].strip()
#                     if not text:
#                         continue
#                     x0, y0, x1, y1 = span["bbox"]
#                     spans_all.append({
#                         "text": text,
#                         "x0": x0,
#                         "x1": x1,
#                         "y0": y0,
#                         "y1": y1
#                     })

#         # 按 y 排序，确保自上而下
#         spans_all.sort(key=lambda s: (round(s["y0"], 1), s["x0"]))

#         merged_lines = []
#         current_line = []
#         current_y = None

#         for span in spans_all:
#             y = span["y0"]

#             if current_y is None or abs(y - current_y) <= y_tol:
#                 current_line.append(span)
#                 current_y = y if current_y is None else (current_y + y) / 2
#             else:
#                 merged_lines.append(current_line)
#                 current_line = [span]
#                 current_y = y

#         if current_line:
#             merged_lines.append(current_line)

#         # 合并每一行内的 span（按 x0 顺序 + 控制空格）
#         for line in merged_lines:
#             line.sort(key=lambda s: s["x0"])
#             merged_text = ""
#             last_x1 = None
#             for span in line:
#                 if last_x1 is not None and span["x0"] - last_x1 > x_tol:
#                     merged_text += " "
#                 merged_text += span["text"]
#                 last_x1 = span["x1"]
#             all_lines.append(merged_text.strip())

#     all_lines = fix_broken_chapters(all_lines)

#     # 写入文件
#     with open('extracted_full_text.txt', "w", encoding="utf-8") as f:
#         f.write("\n".join(all_lines))

#     return all_lines

# 建议替换的核心合并代码（页内逐 line 合并，动态阈值）
def extract_full_text_with_filter(pdf_path: str, top_crop=0.10, bottom_crop=0.10):
    doc = fitz.open(pdf_path)
    all_lines = []

    for page in doc:
        h = page.rect.height
        # 可选裁剪，若不确定先设为 0
        clip_rect = fitz.Rect(0, h * top_crop, page.rect.width, h * (1 - bottom_crop))

        page_dict = page.get_text("dict", clip=clip_rect)
        for block in page_dict["blocks"]:
            if block["type"] != 0:
                continue
            # 直接用 block->lines 结构，避免跨行合并错误
            for line in block["lines"]:
                spans = sorted(line["spans"], key=lambda s: s["bbox"][0])
                merged = ""
                last_x = None
                # 用 span 宽度估算字符宽，动态判断是否插空格
                for sp in spans:
                    x0, x1 = sp["bbox"][0], sp["bbox"][2]
                    width = max(1.0, x1 - x0)
                    avg_char_w = width / max(len(sp["text"]), 1)
                    if last_x is not None:
                        gap = x0 - last_x
                        # 当 gap 明显大于字符宽时插空格（阈值可调）
                        if gap > max(avg_char_w * 0.5, 3.0):
                            merged += " "
                    merged += sp["text"]
                    last_x = x1
                all_lines.append(merged.strip())

    # 规范化空格与标点（去掉标点前多余空格，保证标点后有一个空格）
    normalized = []
    for l in all_lines:
        # 1) 去掉标点前的空格
        l = re.sub(r'\s+([，,。:：；;、\.\,\:\;\)])', r'\1', l)
        # 2) 去掉开括号后多余空格，去掉闭括号前多余空格
        l = re.sub(r'([（\(])\s+', r'\1', l)
        l = re.sub(r'\s+([）\)])', r'\1', l)
        # 3) 标点后保证有一个空格（如果后面是中文或英文单词）
        l = re.sub(r'([，,。:：；;、\.\,\:\;])([^\s])', r'\1 \2', l)
        # 4) 把多重逗号/空格压缩
        l = re.sub(r'[，,]{2,}', r'，', l)
        l = re.sub(r'\s{2,}', ' ', l)
        normalized.append(l.strip())

    # 再进行章节编号修复（用你已有的 fix_broken_chapters）
    normalized = fix_broken_chapters(normalized)

    # 写出文件与返回
    with open('extracted_full_text.txt', "w", encoding="utf-8") as f:
        f.write("\n".join(normalized))
    return normalized



ALPHA_OFFSET = 1000  # 附录字母编号的基准值

def parse_chapter_id(chapter_id: str) -> List[int]:
    chapter_id = chapter_id.strip()

    if re.fullmatch(r'[A-Z](\.\d+)*', chapter_id):  # 附录格式
        parts = chapter_id.split('.')
        letter = parts[0]
        letter_value = ALPHA_OFFSET + (ord(letter) - ord('A'))  # A=1000, B=1001...
        try:
            rest = [int(p) for p in parts[1:]]
            return [letter_value] + rest
        except ValueError:
            return []

    elif re.fullmatch(r'(\d+\.)*\d+', chapter_id):  # 数字章节
        try:
            return [int(p) for p in chapter_id.split('.')]
        except ValueError:
            return []

    return []

def is_chapter_a_before_b(a: list[int], b: list[int]) -> bool:
    for i in range(min(len(a), len(b))):
        if a[i] < b[i]:
            return True
        elif a[i] > b[i]:
            return False
    return len(a) < len(b)

def find_longest_chapter_chain_with_append(chapters: List[Dict]) -> List[Dict]:
    parsed_ids = [parse_chapter_id(ch["chapter_id"]) for ch in chapters]
    n = len(chapters)

    dp = [1] * n
    prev = [-1] * n
    max_len = 0
    max_idx = -1

    for i in range(n):
        if not parsed_ids[i]:
            continue
        for j in range(i):
            if not parsed_ids[j]:
                continue
            if is_chapter_a_before_b(parsed_ids[j], parsed_ids[i]):
                if dp[j] + 1 > dp[i]:
                    dp[i] = dp[j] + 1
                    prev[i] = j
        if dp[i] > max_len:
            max_len = dp[i]
            max_idx = i

    # 回溯出主链索引
    chain_indices = []
    idx = max_idx
    while idx != -1:
        chain_indices.append(idx)
        idx = prev[idx]
    chain_indices.reverse()
    chain_set = set(chain_indices)  # 方便判断是否在主链中

    # 最终结果构建
    result = []
    last_valid = None
    for i, chap in enumerate(chapters):
        if i in chain_set:
            result.append(chap)
            last_valid = chap
        else:
            if last_valid:
                content_to_add = "\n" + chap["chapter_id"] + chap["chapter_title"]
                if chap.get("raw_text"):
                    content_to_add += "\n" + chap["raw_text"]
                last_valid["raw_text"] += content_to_add

    return result

def parse_pdf_to_chapter_tree(pdf_path: str) -> Tuple[List[Dict], Dict[str, str]]:
    """
    从 PDF 中提取章节树和术语映射
    :param pdf_path: PDF 文件路径
    :return: (章节树, 术语映射)
    """
    cleaned_lines = extract_full_text_with_filter(pdf_path)

    chapters = []
    current = None
    buffer = []

    # # 写入文本文件
    # with open('extracted_full_text.txt', "w", encoding="utf-8") as f:
    #     f.write("\n".join(cleaned_lines))  # 用两个换行分隔页面

    # # 修正后的统计行（避免f-string中的反斜杠）
    # total_lines = sum(len(page.splitlines()) for page in cleaned_lines)
    # print(f"✅ 文本已提取到 extracted_full_text.txt")
    # print(f"总页数: {len(doc)}")
    # print(f"有效文本行: {total_lines}")

    for line in cleaned_lines:
        line = line.strip()
        line = fullwidth_to_halfwidth(line)
        chapter_info = detect_chapter(line)

        if chapter_info:
            if current:
                current["raw_text"] = "\n".join(buffer).strip()
                chapters.append(current)
                buffer = []
            current = {
                "chapter_id": chapter_info["chapter_id"],
                "chapter_title": chapter_info["chapter_title"],
                "raw_text": ""
            }
        else:
            buffer.append(line)

    if current:
        current["raw_text"] = "\n".join(buffer).strip()
        chapters.append(current)

    # ✅ 忽略“范围”之前的内容
    start_index = 0
    for i, chap in enumerate(chapters):
        if chap.get("chapter_id") == "1" and (chap.get("chapter_title", "") == "范围" or chap.get("chapter_title", "") == "总则"):
            start_index = i
            # break
    # print(f"⚠️ 忽略前 {start_index} 章，保留后 {len(chapters) - start_index} 章")
    filtered_chapters = chapters[start_index:]

    valid_chapters = find_longest_chapter_chain_with_append(filtered_chapters)

    # tree = build_tree(valid_chapters)
    # build_full_path(tree)

    term_map = {}

    for chap in valid_chapters:
        title = chap.get("chapter_title", "")
        if "术语" in title:
            # 提取术语
            for child in chap.get("children", []):
                terms = extract_terms_with_abbr_from_terms_section(child["chapter_title"])
                term_map.update(terms)
        elif "缩略" in title:
            # 提取缩略语
            abbr_terms = extract_abbr_terms_from_symbols_section(chap.get("raw_text", ""))
            term_map.update(abbr_terms)

    return valid_chapters, term_map


# import re
# from collections import defaultdict
# from typing import List, Dict
# import pdfplumber


# def extract_tables_from_pdf(pdf_path: str) -> List[Dict]:
#     """
#     从PDF中提取所有表格及其标识
#     返回格式: [{"table_id": "表X.x 标题", "table_content": 二维数组}, ...]
#     """
#     all_tables = []

#     with pdfplumber.open(pdf_path) as pdf:
#         for page_num, page in enumerate(pdf.pages):
#             # ---- 1. 先收集页面文本行及其 y 坐标，方便后面找标题 ----
#             page_lines = []
#             if page.extract_text():
#                 chars = page.chars
#                 rows = defaultdict(list)
#                 for c in chars:
#                     rows[int(c['top'])].append(c)
#                 for top in sorted(rows.keys()):
#                     line = ''.join([c['text'] for c in rows[top]]).strip()
#                     page_lines.append({'text': line, 'y': top})

#             # ---- 2. 提取并排序表格 ----
#             tables = page.find_tables()
#             if not tables:
#                 # print(f"⚠️ 第 {page_num + 1} 页没有找到表格")
#                 continue
#             tables = sorted(tables, key=lambda t: t.bbox[1])  # 从上到下

#             # ---- 3. 处理每个表格 ----
#             for table_idx, table in enumerate(tables):
#                 # 过滤：只有 1 列的直接丢弃
#                 sample_row = table.extract()[0] if table.extract() else []
#                 if len(sample_row) <= 1:
#                     continue

#                 # 获取表格内容
#                 table_data = table.extract()
#                 cleaned_data = [
#                     [cell.replace('\n', ' ').strip() if cell else "" for cell in row]
#                     for row in table_data
#                 ]

#                 # ---- 找标题：在表格上方 50 pt 内找“表 X.Y …”整行 ----
#                 table_top = table.bbox[1]
#                 best_line = None
#                 min_gap = float('inf')
#                 for item in page_lines:
#                     if "表" in item['text'] and 0 < (table_top - item['y']) < 50:
#                         gap = table_top - item['y']
#                         if gap < min_gap:
#                             min_gap = gap
#                             best_line = item['text']

#                 # 【修改】逻辑：找不到标题时，尝试合并到上一张表
#                 if best_line:
#                     # 找到了标题 -> 新增一张表
#                     all_tables.append({
#                         "table_id": best_line,
#                         "table_content": cleaned_data
#                     })
#                 else:
#                     if all_tables:
#                         # 【修改】找不到标题 -> 把当前表内容追加到上一张表
#                         all_tables[-1]["table_content"].extend(cleaned_data)
#                     else:
#                         # 整个文档第一张表就找不到标题，兜底命名
#                         table_id = f"表-页{page_num + 1}-表{table_idx + 1}"
#                         all_tables.append({
#                             "table_id": table_id,
#                             "table_content": cleaned_data
#                         })

#     return all_tables


import re
from collections import defaultdict
from typing import List, Dict
import pdfplumber

def _build_page_lines_from_words(page, y_tol=3):
    """
    用 page.extract_words() 构建行：按 top 分桶（y_tol 容差），每行按 x0 排序并合并文本，
    返回列表：{'text', 'y', 'x0', 'x1'}
    """
    words = page.extract_words()  # 返回每个 word 带 x0,x1,top,bottom,text
    if not words:
        return []

    # 按 top, x0 排序
    words = sorted(words, key=lambda w: (w['top'], w['x0']))

    lines = []
    cur = None
    for w in words:
        top = w['top']
        x0 = float(w['x0'])
        x1 = float(w['x1'])
        text = w['text']

        if cur is None:
            cur = {'text': text, 'y': top, 'x0': x0, 'x1': x1}
            continue

        if abs(top - cur['y']) <= y_tol:
            # 同一行，按 x 顺序连接（extract_words 已按 x 排序，但仍做保险）
            if x0 < cur['x1'] + 1:
                # 重叠或紧邻，直接用空格隔开（避免把词粘在一起）
                cur['text'] = cur['text'] + ' ' + text
            else:
                cur['text'] = cur['text'] + ' ' + text
            cur['x1'] = max(cur['x1'], x1)
            cur['x0'] = min(cur['x0'], x0)
            # keep y as average to be robust
            cur['y'] = (cur['y'] + top) / 2.0
        else:
            lines.append(cur)
            cur = {'text': text, 'y': top, 'x0': x0, 'x1': x1}
    if cur:
        lines.append(cur)
    return lines

def _find_table_title_near_bbox(page, table_bbox, max_above=60, y_tol=4):
    """
    在表格上方 max_above pt 的范围内找可能的标题：
    - 先从 page.extract_words() 中筛选出该垂直带内并且与表格水平有重叠的 words
    - 按 top/x0 分组成行并拼接，返回拼完的字符串（可能包含编号）
    """
    table_top = float(table_bbox[1])
    table_x0, table_x1 = float(table_bbox[0]), float(table_bbox[2])
    words = page.extract_words()
    if not words:
        return None

    # 筛选：垂直在 (table_top - max_above, table_top + 10) 范围内，
    # 同时水平上至少与表格左右扩展 50pt 有重叠（防止完全靠左的标题被忽略）
    relevant = []
    margin_x = 60
    for w in words:
        w_top = float(w['top'])
        if not (table_top - max_above <= w_top <= table_top + 10):
            continue
        w_x0 = float(w['x0']); w_x1 = float(w['x1'])
        # 与表格水平投影有重叠 或 在表格左侧接近位置
        if (w_x1 >= table_x0 - margin_x and w_x0 <= table_x1 + margin_x) or w_x0 < table_x0:
            relevant.append(w)

    if not relevant:
        return None

    # 将这些 words 按 top/x0 排序，分行并合并
    relevant = sorted(relevant, key=lambda w: (w['top'], w['x0']))
    lines = []
    cur = None
    for w in relevant:
        top = w['top']; x0 = float(w['x0']); x1 = float(w['x1']); txt = w['text']
        if cur is None:
            cur = {'text': txt, 'y': top, 'x0': x0, 'x1': x1}
        else:
            if abs(top - cur['y']) <= y_tol:
                cur['text'] = cur['text'] + ' ' + txt
                cur['x1'] = max(cur['x1'], x1)
                cur['x0'] = min(cur['x0'], x0)
                cur['y'] = (cur['y'] + top) / 2.0
            else:
                lines.append(cur)
                cur = {'text': txt, 'y': top, 'x0': x0, 'x1': x1}
    if cur:
        lines.append(cur)

    # 现在把这些行拼成最终标题：按 y 从上到下、按 x0 从左到右连接
    # 但优先选择包含 "表" 的行或以 "表" 开头的行及其相邻行
    full = " ".join([ln['text'] for ln in lines]).strip()

    # 优先策略：找到包含"表"的行（最靠近表格的那一行优先）
    cand = None
    candidates = []
    for ln in lines:
        if '表' in ln['text']:
            candidates.append((abs(table_top - ln['y']), ln))
    if candidates:
        # 取距离最小的那一行作为核心，然后把同一 y 带内的其他行合并（左右扩展）
        candidates.sort(key=lambda x: x[0])
        core_y = candidates[0][1]['y']
        # 合并与 core_y 接近的所有行
        merge_parts = [ln['text'] for ln in lines if abs(ln['y'] - core_y) <= max(y_tol, 10)]
        cand = " ".join(merge_parts).strip()
    else:
        # 未找到包含"表"的明确行，就退回用 full（可能就是整段标题）
        cand = full if full else None

    print(f"找到标题候选: {cand}")
    # 进一步清理：把多余空格、连续多余标点整理一下
    if cand:
        cand = re.sub(r'\s+', ' ', cand).strip()
        cand = re.sub(r'\s*([，,：:；;])\s*', r'\1 ', cand)
    return cand

def extract_tables_from_pdf(pdf_path: str) -> List[Dict]:
    """
    改进版：从PDF中提取所有表格及其标识，尽量恢复 '表F.1' 这类编号
    返回格式: [{"table_id": "表X.x 标题", "table_content": 二维数组}, ...]
    """
    all_tables = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            # 使用 extract_words 构建页面行（也保留原始 words 用于更精细判断）
            page_lines = _build_page_lines_from_words(page, y_tol=3)

            # 提取并排序表格
            tables = page.find_tables()
            if not tables:
                continue
            tables = sorted(tables, key=lambda t: t.bbox[1])

            for table_idx, table in enumerate(tables):
                # 过滤：只有 1 列的直接丢弃
                table_data = table.extract()
                if not table_data:
                    continue
                sample_row = table_data[0]
                if len(sample_row) <= 1:
                    continue

                cleaned_data = [
                    [cell.replace('\n', ' ').strip() if cell else "" for cell in row]
                    for row in table_data
                ]

                # 优先通过 page_lines 找标题
                table_top = table.bbox[1]
                best_line = None
                min_gap = float('inf')

                # 先尝试更稳健的方式：从 words 区域收集并拼接标题
                cand = _find_table_title_near_bbox(page, table.bbox, max_above=60, y_tol=4)
                if cand:
                    best_line = cand
                else:
                    # 退回到原先逻辑：在 page_lines 中找包含 "表" 的行（距离最近的）
                    for item in page_lines:
                        if "表" in item['text'] and 0 < (table_top - item['y']) < 60:
                            gap = table_top - item['y']
                            if gap < min_gap:
                                min_gap = gap
                                best_line = item['text']

                # 兜底：如果还是没有编号，检查表格第一行的单元格里是否有“表X”样式
                if best_line is None:
                    first_row = cleaned_data[0]
                    # 把第一行所有单元格拼起来查找“表”关键词
                    joined_first = " ".join(first_row).strip()
                    if re.search(r'表\s*[A-Z0-9]\.?\d*', joined_first) or joined_first.startswith('表'):
                        best_line = joined_first

                # 如果找到了标题则新增，否则用兜底 id
                if best_line:
                    # 进一步做小清洗：将 "表  F.1" 等中间多余空格去掉（保留表字和编号）
                    best_line = re.sub(r'表\s+([A-Za-z0-9])', r'表\1', best_line)
                    all_tables.append({
                        "table_id": best_line,
                        "table_content": cleaned_data
                    })
                else:
                    table_id = f"表-页{page_num + 1}-表{table_idx + 1}"
                    all_tables.append({
                        "table_id": table_id,
                        "table_content": cleaned_data
                    })

    return all_tables


def main():
    import argparse
    parser = argparse.ArgumentParser()
    # parser.add_argument("--pdf_path", help="PDF 文件路径", default="GB∕T 38997-2020 轻小型多旋翼无人机飞行控制与导航系统通用要求.pdf")
    parser.add_argument("--pdf_path", help="PDF 文件路径", default="国标_车载事故紧急呼叫系统-征求意见稿.pdf")
    # parser.add_argument("--pdf_path", help="PDF 文件路径", default="国标_车载事故紧急呼叫系统-征求意见稿_可识别文字.pdf")
    # parser.add_argument("--pdf_path", help="PDF 文件路径", default="GB∕T 38930-2020 民用轻小型无人机系统抗风性要求及试验方法.pdf")
    # parser.add_argument("--pdf_path", help="PDF 文件路径", default="GB 7258-2017 《机动车运行安全技术条件》.pdf")
    # parser.add_argument("--pdf_path", help="PDF 文件路径", default="../示例文件/GB+11551-2014.pdf")
    # parser.add_argument("--pdf_path", help="PDF 文件路径", default="../示例文件/GB+20071-2025.pdf")
    # parser.add_argument("--pdf_path", help="PDF 文件路径", default="../示例文件/GB+20072-2024.pdf")
    # parser.add_argument("--pdf_path", help="PDF 文件路径", default="../示例文件/GB+34660-2017.pdf")
    # parser.add_argument("--pdf_path", help="PDF 文件路径", default="../示例文件/GBT+43187-2023.pdf")
    # parser.add_argument("--pdf_path", help="PDF 文件路径", default="../示例文件/GBT+43187-2023_OCR.pdf")
    # parser.add_argument("--pdf_path", help="PDF 文件路径", default="C:/Users/chenhuaji/OneDrive/桌面/test/GBT+43187-2023_page-0001_chrome.pdf")
    # parser.add_argument("--pdf_path", help="PDF 文件路径", default="D:\\Documents\\知识图谱agent\\示例文件\\GB+34660-2017 处理\\组合 1.pdf")
    # parser.add_argument("--pdf_path", help="PDF 文件路径", default="D:\\Documents\\知识图谱agent\\示例文件\\GBT+43187-2023 处理\\组合 1.pdf")
    # parser.add_argument("--pdf_path", help="PDF 文件路径", default="GB+45672-2025.pdf")
    parser.add_argument("--output", help="输出 JSON 文件路径", default="output.json")
    args = parser.parse_args()

    chapter_tree, term_map = parse_pdf_to_chapter_tree(args.pdf_path)

    # 提取表格
    tables = extract_tables_from_pdf(args.pdf_path)
    
    # 创建输出目录结构
    output_data = {
        "chapters": chapter_tree,
        "tables": tables
    }

    print(f'term_map: {term_map}')

    # 保存结果，一个对象只占一行
    with open(args.output, "w", encoding="utf-8") as f:
        for chapter in output_data["chapters"]:
            f.write(json.dumps(chapter, ensure_ascii=False) + "\n")
        for table in output_data["tables"]:
            f.write(json.dumps(table, ensure_ascii=False) + "\n")

    print(f"✅ 提取完成，章节和表格已保存至 {args.output}")
    print(f"   - 共提取 {len(chapter_tree)} 个章节")
    print(f"   - 共提取 {len(tables)} 个表格")

if __name__ == "__main__":
    main()
