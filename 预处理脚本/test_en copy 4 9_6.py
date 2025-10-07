import fitz  # PyMuPDF
import re
import json
import os
from typing import List, Dict, Tuple
from collections import defaultdict

# chapter_patterns = [
#     re.compile(r'^(附\s*录\s*[A-Z])\s+(.+)$'),
#     re.compile(r'^([A-Z](?:\.\d+)+)\s+(.+)$'),
#     re.compile(r'^(\d+(?:\.\d+)*)(\s+)(.+)$'),
# ]

# chapter_patterns = [
#     re.compile(r'^(APPENDIX\s+[A-Z0-9]+)$', re.I),          # APPENDIX A / APPENDIX 1
#     re.compile(r'^([A-Z](?:\.\d+)+)\s+(.+)$'),
#     re.compile(r'^(\d+(?:\.\d+)*\.?)\s+(.+)$'),                     # 1.1. Title
# ]

# 旧的章节模式（已注释）
# chapter_patterns = [
#     re.compile(r'^(附\s*录\s*[A-Z0-9])$'), # 附 录 B
#     re.compile(r'^((APPENDIX|ANNEX|ATTACHMENT)\s+(?:[A-Z0-9]+|\([A-Z0-9]+\)))$', re.I),  # ANNEX A / ANNEX 1
#     re.compile(r'^([A-Z]\.)\s+(.+)$'),                                # A. Title (单独字母章节)
#     re.compile(r'^([A-Z](?:\.\d+)+\.?)\s+(.+)$'),                     # A.1. Title / A.1.1. Title
#     re.compile(r'^(\d+(?:\.\d+)*\.?)\s+(.+)$'),                       # 1.1. Title
#     re.compile(r'^(\d+(?:-\d+)*-)\s+(.+)$'),                          # 1- Title / 1-2- Title
# ]

# 新的合并后的章节模式
chapter_patterns = [
    # 1. 中文附录：附录A, 附 录 B
    re.compile(r'^(附\s*录\s*[A-Z0-9])$'),
    
    # 2. 英文附录：APPENDIX A, ANNEX A, ATTACHMENT A
    re.compile(r'^((APPENDIX|ANNEX|ATTACHMENT)\s+(?:[A-Z0-9]+|\([A-Z0-9]+\)))$', re.I),
    
    # 3. 字母章节（支持点和横线分隔符）：A. Title, A.1. Title, A-1- Title
    re.compile(r'^([A-Z](?:[.\-]\d+)*[.\-]?)\s+(.+)$'),
    
    # 4. 数字章节（支持点和横线分隔符）：1. Title, 1.1. Title, 1- Title, 1-2- Title
    re.compile(r'^(\d+(?:[.\-]\d+)*[.\-]?)\s+(.+)$'),
]

def detect_document_language(lines: List[str]) -> str:
    """
    检测文档语言：中文或英文
    :param lines: 文档的所有行
    :return: 'zh' 表示中文，'en' 表示英文
    """
    chinese_char_count = 0
    total_chars = 0
    
    # 采样前1000行或全部行
    sample_lines = lines[:1000] if len(lines) > 1000 else lines
    
    for line in sample_lines:
        for char in line:
            total_chars += 1
            if '\u4e00' <= char <= '\u9fff':  # 中文字符
                chinese_char_count += 1
    
    # 只要有中文字符就认为是中文文档
    if chinese_char_count > 0:
        return 'zh'
    else:
        return 'en'

# 中文章节max_chapter_num=50
# 全文首先检测是中文还是英文
def detect_chapter(line: str, max_chapter_num=1000, language='en', number_analysis=None):
    clean_line = line.strip()
    if not clean_line:
        return None

    for pattern in chapter_patterns:
        m = pattern.match(clean_line)
        if m:
            chapter_id = m.group(1).strip()
            chapter_title = m.group(len(m.groups())).strip() if m.group(len(m.groups())) else ""
            if re.match(r'^(附\s*录\s*[A-Z0-9])$', chapter_id):
                # 去掉中间的空格
                chapter_id = chapter_id.replace(" ", "")
                # chapter_id = chapter_id[-1]
            # ---- 基础过滤 ----
            first_num = None
            if chapter_id.upper().startswith("APPENDIX"):
                suffix = chapter_id[len("APPENDIX"):].strip(" ()")
                if suffix.isdigit():
                    first_num = int(suffix)
            else:
                m_num = re.match(r'^(\d+)', chapter_id)
                if m_num:
                    first_num = int(m_num.group(1))

            if first_num is not None and number_analysis is not None:
                # 使用智能数字范围判断
                min_reasonable = number_analysis.get("min_reasonable", 1)
                max_reasonable = number_analysis.get("max_reasonable", max_chapter_num)
                
                # 特殊处理法规编号模式
                if number_analysis.get("regulation_mode", False):
                    regulation_number = number_analysis.get("regulation_number")
                    if first_num != regulation_number:
                        return None  # 不是法规编号，过滤掉
                else:
                    # 正常章节编号范围检查
                    if first_num < min_reasonable or first_num > max_reasonable:
                        return None  # 数字范围不合理
            elif first_num is not None:
                # 兜底逻辑：使用传统的max_chapter_num
                if first_num < 1 or first_num > max_chapter_num:
                    return None  # 数字范围不合理

            # ---- 内容特征过滤 ----
            # 1) 标题必须包含字母或中文
            if not re.search(r'[A-Za-z\u4e00-\u9fff]', chapter_title):
                return None

            # 2) 去掉纯数字表格行
            if re.fullmatch(r'[\d\s\.\-]+', chapter_title):
                return None

            # 3) 表格内容过滤 - 检测明显的表格数据模式
            # 如果标题包含大量数字、空格和少量字母的组合，可能是表格数据
            if re.search(r'^\d+\s+\d+.*[A-Z]\s+\d+\s+\d+', chapter_title):  # 如 "10 0 E 0 16"
                return None
            
            # 检测表格行模式：单个字母 + 数字组合
            if re.fullmatch(r'[A-Z]\s*\d+.*', chapter_title) and len(chapter_title.split()) >= 3:
                # 如果标题是 "A 10 0" 这样的格式，很可能是表格数据
                parts = chapter_title.split()
                if len(parts) >= 3 and all(part.isdigit() or part in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' for part in parts[:3]):
                    return None

            # 4) 检测坐标点或参数表格：如 "A15 0 E 0 3"
            if re.search(r'^[A-Z]\d+\s+\d+\s+[A-Z]\s+\d+\s+\d+', chapter_title):
                return None

            # 5) 行太短
            if len(clean_line) < 4 and not chapter_id.upper().startswith("APPENDIX") and not chapter_id.startswith("附录"):
                return None

            # 6) 过滤明显的表格标题组合
            if len(chapter_id) == 1 and chapter_id.isupper():
                # 单个大写字母作为章节ID，检查标题是否像表格数据
                if re.search(r'\d+.*\d+', chapter_title) and len(chapter_title.split()) <= 6:
                    return None

            return {
                "chapter_id": chapter_id,
                "chapter_title": chapter_title
            }

    return None

def build_tree(chapter_list: List[Dict]) -> List[Dict]:
    id_map = {}
    root = []

    # 先注册所有节点
    for chap in chapter_list:
        chap["children"] = []
        # 统一去掉末尾点和横线作为 key
        key = chap["chapter_id"].rstrip('.-')
        id_map[key] = chap

    # 为每个节点创建缺失的父节点（只针对三级及以上标题）
    for chap in chapter_list:
        cid = chap["chapter_id"].rstrip('.')
        parts = cid.split('.')
        
        # 只有三级及以上标题才创建中间父节点
        if len(parts) >= 3:
            # 创建所有缺失的中间父级节点（但不包括顶级父节点）
            for i in range(2, len(parts)):  # 从第二级开始创建，跳过顶级
                parent_key = '.'.join(parts[:i])
                if parent_key not in id_map:
                    # 创建缺失的父节点
                    parent_node = {
                        "chapter_id": parent_key + ".",
                        "chapter_title": "",
                        "raw_text": "",
                        "children": []
                    }
                    id_map[parent_key] = parent_node

    # 构建树结构
    for chap in chapter_list:
        cid = chap["chapter_id"].rstrip('.')
        parts = cid.split('.')

        # 根节点判断
        if cid.startswith("APPENDIX"):
            root.append(chap)
        elif cid.startswith("附录") or len(parts) == 1:
            root.append(chap)
        else:
            parent_key = '.'.join(parts[:-1])
            parent = id_map.get(parent_key)
            if parent:
                parent["children"].append(chap)
            else:
                # 如果父节点不存在，对于二级标题，直接作为根节点
                if len(parts) == 2:
                    root.append(chap)
                # 三级及以上标题没有父节点时，不做处理（因为前面已经创建了父节点）


    # 将创建的中间节点也添加到最终的章节列表中，但只有那些有子节点的
    created_parents = []
    for key, node in id_map.items():
        if node not in chapter_list and len(node["children"]) > 0:
            created_parents.append(node)
    
    # 对创建的父节点也进行树结构构建
    for parent in created_parents:
        cid = parent["chapter_id"].rstrip('.')
        parts = cid.split('.')
        
        if len(parts) == 1:
            root.append(parent)
        else:
            parent_key = '.'.join(parts[:-1])
            grandparent = id_map.get(parent_key)
            if grandparent and parent not in grandparent["children"]:
                grandparent["children"].append(parent)
            elif len(parts) == 1:  # 这是一级章节
                if parent not in root:
                    root.append(parent)
    
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

def should_merge_crossline(prev_text, curr_text, prev_bbox, curr_bbox):
    """
    判断是否需要把当前行合并到上一行
    """
    text_stripped = curr_text.strip()

    # 模式匹配：表格标题、编号标题等
    if re.match(r'^表\s*\d+', text_stripped):
        return True

    # 垂直距离很小（说明是视觉上的同一行）
    prev_y = prev_bbox[1]
    curr_y = curr_bbox[1]
    line_height = prev_bbox[3] - prev_bbox[1]
    if abs(curr_y - prev_y) < 0.3 * line_height:
        return True

    return False

def fix_broken_chapters(lines: list[str]) -> list[str]:
    def normalize_chapter_spaces(s: str) -> str:
        line = s.strip()
        
        # 1. 保留原来的逻辑：修复点后面的空格，适用于所有情况 (A. 1, 7. 1)
        line = re.sub(r'\.\s+(?=\d)', '.', line)
        
        # 2. 修复数字/字母和点之间的空格：7 .1 -> 7.1, A .1 -> A.1
        line = re.sub(r'([A-Za-z0-9]+)\s+(\.\d+)', r'\1\2', line)
        
        # 3. 修复复杂的多级空格：7 . 1 . 2 -> 7.1.2
        # 需要循环处理，直到没有更多变化
        max_iterations = 10  # 防止无限循环
        iterations = 0
        prev_line = ""
        while prev_line != line and iterations < max_iterations:
            prev_line = line
            # 处理各种空格组合，支持字母和数字开头
            line = re.sub(r'([A-Za-z0-9]+)\s*\.\s*(\d+)', r'\1.\2', line)
            iterations += 1
        
        # 4. 修复OCR常见错误：数字开头的章节
        line = re.sub(r'(\d+\.\d+)\.\s*l\b', r'\1.1', line)
        line = re.sub(r'([A-Za-z0-9]+)\.l\.(\d+)', r'\1.1.\2', line)
        line = re.sub(r'^l\.(\d+)', r'1.\1', line)
        
        # 5. 修复字母开头章节的OCR错误：B.l -> B.1, A.O -> A.0, C.I -> C.1
        line = re.sub(r'^([A-Z])\.l\b', r'\1.1', line)
        line = re.sub(r'^([A-Z])\.l\.(\d+)', r'\1.1.\2', line)
        line = re.sub(r'^([A-Z])\.O\.(\d+)', r'\1.0.\2', line)
        line = re.sub(r'^([A-Z])\.I\.(\d+)', r'\1.1.\2', line)
        
        # 6. 修复其他OCR错误：O -> 0, I -> 1
        line = re.sub(r'([A-Za-z0-9]+)\.O\.(\d+)', r'\1.0.\2', line)
        line = re.sub(r'([A-Za-z0-9]+)\.I\.(\d+)', r'\1.1.\2', line)
        
        return line

    lines = [normalize_chapter_spaces(line) for line in lines]

    return lines

def process_gb_terms_format(lines: List[str]) -> List[str]:
    """
    处理国标术语定义格式：
    将 "3.1" (下一行) "中文术语 英文术语" 合并为 "3.1 中文术语 英文术语"
    """
    result = []
    i = 0
    
    while i < len(lines):
        current_line = lines[i].strip()
        
        # 检测是否是术语定义编号：纯数字.数字格式，且下一行包含中文+英文，或者第二行是中文，第三行是英文
        if (i + 1 < len(lines) and 
            re.match(r'^\d+\.\d+$', current_line) and
            current_line.startswith('3.')):  # 通常术语章节是第3章
            
            next_line = lines[i + 1].strip()
            
            # 检查下一行是否符合: 中文 + 空格 + 英文 的模式
            if re.search(r'[\u4e00-\u9fa5].*[A-Za-z]', next_line):
                # 合并成标题格式
                merged_line = f"{current_line} {next_line}"
                result.append(merged_line)
                i += 2  # 跳过下一行
                continue

            # 检查第二行是否是中文，第三行是否是英文
            if (i + 2 < len(lines) and
                re.search(r'[\u4e00-\u9fa5]', lines[i + 1].strip()) and
                re.search(r'[A-Za-z]', lines[i + 2].strip())):
                merged_line = f"{current_line} {lines[i + 1].strip()} {lines[i + 2].strip()}"
                result.append(merged_line)
                i += 3  # 跳过后两行
                continue

        result.append(current_line)
        i += 1
    
    return result

def extract_full_text_with_filter(pdf_path: str, top_crop=0.08, bottom_crop=0.08):
    doc = fitz.open(pdf_path)
    all_lines = []

    prev_line_text = None
    prev_bbox = None



    for page in doc:

        h = page.rect.height
        clip_rect = fitz.Rect(0, h * top_crop, page.rect.width, h * (1 - bottom_crop))
        page_dict = page.get_text("dict", clip=clip_rect)

        for block in page_dict["blocks"]:
            if block["type"] != 0:  # 只处理文本
                continue

            for line in block["lines"]:
                # 1. 按x坐标合并同一行的span
                spans = sorted(line["spans"], key=lambda s: s["bbox"][0])
                merged = ""
                last_x = None
                for sp in spans:
                    x0, x1 = sp["bbox"][0], sp["bbox"][2]
                    width = max(1.0, x1 - x0)
                    avg_char_w = width / max(len(sp["text"]), 1)

                    if last_x is not None:
                        gap = x0 - last_x
                        if gap > max(avg_char_w * 0.5, 3.0):
                            merged += " "
                    merged += sp["text"]
                    last_x = x1

                merged = merged.strip()
                curr_bbox = line["bbox"]

                # 2. 跨行智能合并判定
                if prev_line_text is not None:
                    if should_merge_crossline(prev_line_text, merged, prev_bbox, curr_bbox):
                        prev_line_text += " " + merged
                        prev_bbox = (
                            prev_bbox[0],
                            prev_bbox[1],
                            max(prev_bbox[2], curr_bbox[2]),
                            max(prev_bbox[3], curr_bbox[3])
                        )
                        continue
                    else:
                        all_lines.append(prev_line_text)

                prev_line_text = merged
                prev_bbox = curr_bbox

    # 最后一行
    if prev_line_text:
        all_lines.append(prev_line_text)

    # 进行全角字符转半角字符
    all_lines = [fullwidth_to_halfwidth(line.strip()) for line in all_lines]

    # 进行章节编号修复
    normalized = fix_broken_chapters(all_lines)
    
    # 🆕 国标术语定义格式处理
    normalized = process_gb_terms_format(normalized)

    # 写出文件与返回
    with open('extracted_full_text.txt', "w", encoding="utf-8") as f:
        f.write("\n".join(normalized))

    return normalized

def detect_chapter_pattern(chapters: List[Dict]) -> str:
    """
    检测文档的章节模式：
    - 'alpha_first': 字母章节在前 (A, A.1, A.2, B, B.1, 1, 2, ...)
    - 'numeric_first': 数字章节在前 (1, 2, ..., A, A.1, A.2, B, B.1, ...)
    """
    alpha_indices = []
    numeric_indices = []
    
    for i, ch in enumerate(chapters):
        chapter_id = ch["chapter_id"].strip()
        if re.match(r'^[A-Z](\.\d+)*\.?$', chapter_id):
            alpha_indices.append(i)
        elif re.match(r'^\d+(\.\d+)*\.?$', chapter_id):
            numeric_indices.append(i)
    
    if not alpha_indices or not numeric_indices:
        return 'numeric_first'  # 默认数字优先
    
    # 比较第一个字母章节和第一个数字章节的位置
    first_alpha = min(alpha_indices)
    first_numeric = min(numeric_indices)
    
    if first_alpha < first_numeric:
        return 'alpha_first'
    else:
        return 'numeric_first'

def parse_chapter_id(chapter_id: str, pattern: str = 'numeric_first') -> List[int]:
    """
    根据文档模式解析章节ID
    :param chapter_id: 章节ID字符串
    :param pattern: 文档模式 ('alpha_first' 或 'numeric_first')
    """
    chapter_id = chapter_id.strip()

    # 字母章节格式 - 支持点和横线分隔符
    if re.fullmatch(r'[A-Z](?:[.\-]\d+)*[.\-]?', chapter_id):
        # 统一处理点和横线分隔符
        normalized = re.sub(r'[.\-]+', '.', chapter_id).rstrip('.')
        parts = normalized.split('.')
        letter = parts[0]
        
        if pattern == 'alpha_first':
            # 字母在前模式：A=1, B=2, C=3, ...
            letter_value = ord(letter) - ord('A') + 1
        else:
            # 数字在前模式：字母章节放在数字章节之后
            # 假设最多有100个数字章节，字母从101开始
            letter_value = ord(letter) - ord('A') + 101
        
        try:
            rest = [int(p) for p in parts[1:]] if len(parts) > 1 else []
            return [letter_value] + rest
        except ValueError:
            return []

    # 数字章节格式 - 支持点和横线分隔符
    elif re.fullmatch(r'\d+(?:[.\-]\d+)*[.\-]?', chapter_id):
        try:
            # 统一处理点和横线分隔符
            normalized = re.sub(r'[.\-]+', '.', chapter_id).rstrip('.')
            parts = normalized.split('.')
            numeric_parts = [int(p) for p in parts]
            
            if pattern == 'alpha_first':
                # 字母在前模式：数字章节放在字母章节之后
                # 假设最多有26个字母章节，数字从27开始
                numeric_parts[0] += 26
            # 数字在前模式：保持原有数字
            
            return numeric_parts
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

def is_reasonable_chapter_jump(prev_id: List[int], curr_id: List[int]) -> bool:
    """
    判断章节跳跃是否合理，更宽松的策略：
    主要过滤掉明显不合理的跳跃，但允许正常的章节结构
    对字母链和数字链都进行合理性判断
    """
    if not prev_id or not curr_id:
        return True  # 如果无法解析，默认允许
    
    # 如果是不同层级，一般都是合理的（如 1. -> 1.1 或 1.1 -> 2.）
    if len(prev_id) != len(curr_id):
        return True
    
    # 同层级的情况下，检查跳跃幅度
    if len(prev_id) == 1:  # 一级章节
        prev_num = prev_id[0]
        curr_num = curr_id[0]
        diff = curr_num - prev_num
        
        # 判断是否为字母章节（编码范围101-126对应A-Z）
        if prev_num >= 101 and curr_num >= 101:  # 字母章节
            # 字母跳跃检查：不允许跨越超过2个字母（如B跳到E以上）
            return 1 <= diff <= 2
        else:  # 数字章节
            return 1 <= diff <= 5  # 允许跳跃1-5章（过滤掉从5跳到100这种明显错误的）
    
    elif len(prev_id) == 2:  # 二级章节
        # 如果第一级相同，检查第二级的跳跃
        if prev_id[0] == curr_id[0]:
            prev_num = prev_id[1]
            curr_num = curr_id[1]
            diff = curr_num - prev_num
            
            # 判断第一级是否为字母章节
            if prev_id[0] >= 101:  # 字母章节的子级
                return 1 <= diff <= 5  # 字母章节的子级跳跃稍微宽松一些
            else:  # 数字章节的子级
                return 1 <= diff <= 10  # 二级章节允许更大跳跃
        else:
            # 不同的一级章节，都合理
            return True
    
    else:  # 三级及以上章节
        # 对于深层次章节，更宽松一些
        return True

def analyze_chapter_number_distribution(chapters: List[Dict]) -> Dict[str, int]:
    """
    分析章节编号的数字分布，确定合理的数字范围
    返回: {"min_reasonable": 最小合理数字, "max_reasonable": 最大合理数字, "primary_range": 主要数字范围}
    """
    first_numbers = []
    
    for ch in chapters:
        chapter_id = ch["chapter_id"].strip()
        # 提取第一个数字
        m_num = re.match(r'^(\d+)', chapter_id)
        if m_num:
            first_numbers.append(int(m_num.group(1)))
        # 处理APPENDIX后跟数字的情况
        elif chapter_id.upper().startswith("APPENDIX"):
            suffix = chapter_id[len("APPENDIX"):].strip(" ()")
            if suffix.isdigit():
                first_numbers.append(int(suffix))
    
    if not first_numbers:
        return {"min_reasonable": 1, "max_reasonable": 50, "primary_range": (1, 50)}
    
    first_numbers.sort()
    
    # 分析数字分布模式
    from collections import Counter
    counter = Counter(first_numbers)
    
    # 如果大多数章节都是同一个数字开头（如60.1, 60.2, 60.3...），这可能是法规编号
    most_common = counter.most_common(1)[0]
    most_common_num, most_common_count = most_common
    
    # 如果某个数字出现次数超过总数的60%，且这个数字大于30，可能是法规编号模式
    if most_common_count > len(first_numbers) * 0.6 and most_common_num > 30:
        print(f"检测到可能的法规编号模式: {most_common_num}.x (出现{most_common_count}次)")
        # 在这种情况下，允许这个特定的法规编号
        return {
            "min_reasonable": most_common_num, 
            "max_reasonable": most_common_num, 
            "primary_range": (most_common_num, most_common_num),
            "regulation_mode": True,
            "regulation_number": most_common_num
        }
    
    # 正常的章节编号模式
    min_num = min(first_numbers)
    max_num = max(first_numbers)
    
    # 如果数字范围很小（<= 50），认为是正常章节
    if max_num <= 50:
        return {
            "min_reasonable": max(1, min_num), 
            "max_reasonable": min(50, max_num + 5),  # 允许少量超出
            "primary_range": (min_num, max_num)
        }
    
    # 如果数字范围很大，可能包含页码等干扰，采用更保守策略
    # 找到最密集的数字区间
    gaps = []
    for i in range(len(first_numbers) - 1):
        gaps.append(first_numbers[i + 1] - first_numbers[i])
    
    # 如果有明显的大跳跃（>20），可能前面是正常章节，后面是页码等
    large_gap_idx = -1
    for i, gap in enumerate(gaps):
        if gap > 20:
            large_gap_idx = i
            break
    
    if large_gap_idx != -1:
        # 取跳跃前的数字作为合理范围
        reasonable_max = first_numbers[large_gap_idx]
        return {
            "min_reasonable": max(1, min_num), 
            "max_reasonable": reasonable_max,
            "primary_range": (min_num, reasonable_max)
        }
    
    # 默认保守策略
    return {"min_reasonable": 1, "max_reasonable": 50, "primary_range": (1, 50)}

def find_longest_chapter_chain_with_append(chapters: List[Dict], language: str = 'en') -> Tuple[List[Dict], str]:
    # 先检测章节模式
    pattern = detect_chapter_pattern(chapters)
    print(f"检测到章节模式: {pattern}")
    
    # 🆕 分析章节数字分布
    number_analysis = analyze_chapter_number_distribution(chapters)
    print(f"章节数字分析结果: {number_analysis}")
    
    # 用检测到的模式重新解析章节ID
    parsed_ids = [parse_chapter_id(ch["chapter_id"], pattern) for ch in chapters]
    # print(f'第一个章节: {chapters[0]}')
    n = len(chapters)

    # 第一步：过滤掉明显不合理的章节（如误识别的数字）
    valid_indices = []
    for i in range(n):
        if not parsed_ids[i]:
            continue
            
        # 检查是否是明显的误识别
        chapter_text = chapters[i]["chapter_id"] + " " + chapters[i]["chapter_title"]
        
        # 过滤明显的测量单位、频率范围、纯数字等
        if re.search(r'\b\d+\s*(MHz|GHz|Hz|kHz|dB|V|mV|µV|A|mA|µA|W|mW|Ω|%|°C|°F|mm|cm|m|km|kg|g|mg|ms|s|min|h|rpm|bar|Pa|kPa|MPa)\b', chapter_text, re.I):
            continue
        if re.search(r'\d+\s*MHz\s*[~-]\s*\d+\s*MHz', chapter_text, re.I):
            continue
        if re.match(r'^\d+\s*$', chapters[i]["chapter_title"].strip()):  # 标题是纯数字
            continue
        if len(chapters[i]["chapter_title"].strip()) < 2:  # 标题太短
            continue
            
        # 🆕 表格数据特征过滤
        chapter_title = chapters[i]["chapter_title"].strip()
        chapter_id = chapters[i]["chapter_id"].strip()
        
        # 检测表格行模式：单个字母 + 主要是数字的标题
        if (len(chapter_id) == 1 and chapter_id.isupper() and 
            re.search(r'^\d+.*\d+', chapter_title) and 
            len([x for x in chapter_title.split() if x.isdigit()]) >= 2):
            continue
            
        # 检测坐标点格式：如 "10 0 E 0 16"
        if re.match(r'^\d+\s+\d+\s+[A-Z]\s+\d+\s+\d+', chapter_title):
            continue
            
        # 检测参数表格格式：如 "34 65 F 25 77"
        title_parts = chapter_title.split()
        if (len(title_parts) >= 4 and 
            sum(1 for part in title_parts if part.isdigit()) >= 3 and
            sum(1 for part in title_parts if len(part) == 1 and part.isupper()) >= 1):
            continue
            
        # 检测图表标注说明：单个字母 + 以破折号开头的标题
        if (len(chapter_id) == 1 and chapter_id.isupper() and 
            chapter_title.startswith('———')):
            continue
            
        valid_indices.append(i)
    
    # 第二步：验证字母章节的合理性（针对中英文差异化处理）
    if valid_indices:
        # 检查是否包含字母章节
        alpha_chapters = []
        for i, idx in enumerate(valid_indices):
            chapter_id = chapters[idx]["chapter_id"].strip()
            if re.match(r'^[A-Z](?:\.\d+)*\.?$', chapter_id):
                alpha_chapters.append((i, idx, chapter_id[0]))  # (在valid_indices中的位置, 原始索引, 首字母)
        
        # 如果有字母章节，进行合理性验证
        if alpha_chapters:
            if language == 'en':
                # 英文文档：要求字母章节必须从A开头
                first_alpha_letter = alpha_chapters[0][2]
                if first_alpha_letter != 'A':
                    print(f"英文文档字母章节不以A开头，跳过: 第一个字母章节是 {alpha_chapters[0][2]}")
                    # 移除所有字母章节
                    alpha_indices_set = {item[1] for item in alpha_chapters}
                    valid_indices = [idx for idx in valid_indices if idx not in alpha_indices_set]
            else:
                # 中文文档：检查字母章节的一致性（同一附录应该以同一字母开头）
                from collections import Counter
                alpha_letters = [item[2] for item in alpha_chapters]
                letter_counter = Counter(alpha_letters)
                most_common_letter, most_common_count = letter_counter.most_common(1)[0]
                
                # 如果某个字母出现次数超过60%，认为这是主要的附录字母
                if most_common_count > len(alpha_chapters) * 0.6:
                    print(f"中文文档检测到主要附录字母: {most_common_letter} (出现{most_common_count}次)")
                    # 保留与主要字母一致的章节，移除其他字母章节
                    keep_alpha_indices = {item[1] for item in alpha_chapters if item[2] == most_common_letter}
                    remove_alpha_indices = {item[1] for item in alpha_chapters if item[2] != most_common_letter}
                    valid_indices = [idx for idx in valid_indices if idx not in remove_alpha_indices]
                    if remove_alpha_indices:
                        removed_letters = {chapters[idx]["chapter_id"].strip()[0] for idx in remove_alpha_indices}
                        print(f"移除不一致的字母章节: {removed_letters}")
                else:
                    # 如果没有明显的主要字母，保持原有逻辑（可能是混合情况）
                    print(f"中文文档字母章节分布较均匀: {dict(letter_counter)}")
                    # 不做特殊处理，保留所有字母章节

    # 第三步：从后往前构建最长链
    dp = [1] * len(valid_indices)
    next_link = [-1] * len(valid_indices)  # 改为记录下一个节点
    max_len = 0
    max_idx = -1

    # 从后往前遍历
    for i in range(len(valid_indices) - 1, -1, -1):
        curr_idx = valid_indices[i]
        curr_parsed = parsed_ids[curr_idx]
        
        # 找在当前节点之后的所有节点
        for j in range(i + 1, len(valid_indices)):
            next_idx = valid_indices[j]
            next_parsed = parsed_ids[next_idx]
            
            # 检查当前节点是否可以连到下一个节点
            if (is_chapter_a_before_b(curr_parsed, next_parsed) and 
                is_reasonable_chapter_jump(curr_parsed, next_parsed)):
                if dp[j] + 1 > dp[i]:
                    dp[i] = dp[j] + 1
                    next_link[i] = j
        
        if dp[i] > max_len:
            max_len = dp[i]
            max_idx = i

    # 第四步：如果没有找到合理的链，退回到简单的顺序过滤
    if max_len < 2:
        # 简单按章节编号顺序过滤
        filtered_chapters = simple_chapter_filter(chapters)
        
        # 如果过滤后还是没有章节，将所有内容放入跳过的内容中
        if not filtered_chapters:
            all_content = []
            for ch in chapters:
                content = f"{ch['chapter_id']} {ch['chapter_title']}"
                if ch.get('raw_text'):
                    content += " " + ch['raw_text']
                all_content.append(content)
            skipped_text = "\n".join(all_content)
            return [], skipped_text
        
        return filtered_chapters, ""

    # 回溯出主链索引（从前往后的正确顺序）
    chain_indices = []
    idx = max_idx
    while idx != -1:
        chain_indices.append(valid_indices[idx])
        idx = next_link[idx]
    
    print(f"从后往前生成的最长链: 长度={len(chain_indices)}, 位置={chain_indices[:5]}{'...' if len(chain_indices)>5 else ''}")
    
    # 最长链的第一个章节索引
    first_chain_idx = chain_indices[0]
    
    # 生成跳过的内容（最长链第一个章节之前的所有内容）
    skipped_chapters = chapters[:first_chain_idx]
    skipped_text = "\n".join([f"{ch['chapter_id']} {ch['chapter_title']} {ch.get('raw_text','')}" for ch in skipped_chapters])
    
    chain_set = set(chain_indices)

    # 最终结果构建
    result = []
    last_valid = None
    for i, chap in enumerate(chapters):
        if i in chain_set:
            result.append(chap)
            last_valid = chap
        elif i >= first_chain_idx:  # 只处理最长链开始之后的章节
            if last_valid:
                content_to_add = "\n" + chap["chapter_id"] + chap["chapter_title"]
                if chap.get("raw_text"):
                    content_to_add += " " + chap["raw_text"]
                last_valid["raw_text"] += content_to_add

    # 判断章节标题是否应该合并到正文中
    for chap in result:
        should_merge = False
        
        # 中文处理：包含中文且有中文逗号，句号，冒号，或者长度大于30字符
        if re.search(r'[\u4e00-\u9fa5]', chap["chapter_title"]):
            # 获取章节编号的第一个数字，前三章跳过合并判断
            first_num = None
            chapter_id = chap["chapter_id"].strip('.-')
            if re.match(r'^\d+', chapter_id):
                first_num = int(re.match(r'^\d+', chapter_id).group())
            # 前三章跳过合并判断
            if first_num is not None and first_num <= 3:
                continue          
            if re.search(r'[，。：,:]', chap["chapter_title"]) or len(chap["chapter_title"]) > 30:
                should_merge = True
        
        # 英文处理：更智能的判断逻辑
        else:
            # 如果全大写，则肯定是标题
            if chap["chapter_title"].isupper():
                continue
            # 1. 如果raw_text以小写字母开头，可能是标题的延续
            if len(chap["raw_text"]) and chap["raw_text"][0].islower():
                should_merge = True
            # 2. 如果chapter_title包含完整句子的特征
            elif re.search(r'[,;!?]', chap["chapter_title"]):
                should_merge = True
            # 3. 如果chapter_title很长（超过50个字符），可能是段落文本
            elif len(chap["chapter_title"]) > 50:
                should_merge = True
        
        if should_merge:
            chap["raw_text"] = chap["chapter_title"] + ' ' + chap["raw_text"]
            chap["chapter_title"] = ""

    return result, skipped_text

def simple_chapter_filter(chapters: List[Dict]) -> List[Dict]:
    """
    简单的章节过滤策略：当最长链算法失效时的备用方案
    """
    # 检测章节模式
    pattern = detect_chapter_pattern(chapters)
    
    result = []
    parsed_ids = [parse_chapter_id(ch["chapter_id"], pattern) for ch in chapters]
    
    for i, chap in enumerate(chapters):
        parsed_id = parsed_ids[i]
        
        # 基本合理性检查
        if not parsed_id:
            # 无法解析的章节，追加到上一个有效章节
            if result:
                content_to_add = "\n" + chap["chapter_id"] + chap["chapter_title"]
                if chap.get("raw_text"):
                    content_to_add += " " + chap["raw_text"]
                result[-1]["raw_text"] += content_to_add
            continue
        
        # 检查章节编号是否在合理范围内
        first_num = parsed_id[0]
        
        # 根据模式调整合理性检查
        if pattern == 'alpha_first':
            # 字母在前：A=1, B=2, ..., 1=27, 2=28, ...
            if 1 <= first_num <= 50:  # 合理范围：26个字母 + 20个数字章节
                result.append(chap)
            else:
                # 不合理的章节，追加到上一个有效章节
                if result:
                    content_to_add = "\n" + chap["chapter_id"] + chap["chapter_title"]
                    if chap.get("raw_text"):
                        content_to_add += " " + chap["raw_text"]
                    result[-1]["raw_text"] += content_to_add
        else:
            # 数字在前：1, 2, ..., A=101, B=102, ...
            if (1 <= first_num <= 20) or (101 <= first_num <= 126):  # 数字章节或字母章节
                result.append(chap)
            else:
                # 不合理的章节，追加到上一个有效章节
                if result:
                    content_to_add = "\n" + chap["chapter_id"] + chap["chapter_title"]
                    if chap.get("raw_text"):
                        content_to_add += " " + chap["raw_text"]
                    result[-1]["raw_text"] += content_to_add
    
    return result
    
    return result

def split_sections_by_attachment(chapters: List[Dict]) -> List[Dict]:
    """
    将整个文档按附件（ANNEX）切分。
    顶层 file: regulation / ANNEX n
    改进：合并连续的相同附件标题
    """
    sections = []
    current_section = {
        "section": "regulation",  # 默认主文档
        "chapters": []
    }

    annex_pattern = re.compile(r'^(ANNEX|ATTACHMENT)\s+([A-Z0-9]+)', re.I)

    for chap in chapters:
        match = annex_pattern.match(chap['chapter_id'])
        if match:
            annex_name = match.group(1).upper() + " " + match.group(2)  # 标准化名称，如 "ANNEX 1"
            
            # 检查是否与当前 section 的名称相同
            if current_section["section"] != "regulation" and current_section["section"].upper() == annex_name:
                # 相同的附件，直接添加到当前 section，跳过重复的标题章节
                if chap.get('chapter_title') or chap.get('raw_text', '').strip():
                    current_section["chapters"].append(chap)
                # 如果是空的重复标题章节（只有chapter_id没有内容），则跳过
            else:
                # 不同的附件，保存当前块并新建
                if current_section["chapters"]:
                    sections.append(current_section)
                # 新建附件块
                current_section = {
                    "section": annex_name,
                    "chapters": [chap] if (chap.get('chapter_title') or chap.get('raw_text', '').strip()) else []
                }
        else:
            current_section["chapters"].append(chap)

    if current_section["chapters"]:
        sections.append(current_section)

    return sections

def split_sections_by_appendix(chapters):
    sections = []
    current_section = {"section": "MAIN", "chapters": []}

    for ch in chapters:
        # 检测 APPENDIX 开头的顶层标题，或者附录
        appendix_match = re.match(r'^(APPENDIX\s+(?:[A-Z0-9]+|\([A-Z0-9]+\)))$', ch['chapter_id'], re.IGNORECASE)
        annex_match = ch["chapter_id"].startswith("附录")
        
        if appendix_match or annex_match:
            # 标准化附录名称
            if appendix_match:
                appendix_name = appendix_match.group(1).upper()
            else:
                appendix_name = ch['chapter_id'].strip()
            
            # 检查是否与当前 section 的名称相同
            if current_section["section"] != "MAIN" and current_section["section"].upper() == appendix_name:
                # 相同的附录，直接添加到当前 section（如果有实际内容）
                if ch.get('chapter_title') or ch.get('raw_text', '').strip():
                    current_section["chapters"].append(ch)
                # 如果是空的重复标题章节，则跳过
            else:
                # 不同的附录，先保存当前块
                if current_section["chapters"]:
                    sections.append(current_section)
                # 新建附录块
                current_section = {
                    "section": appendix_name,
                    "chapters": [ch] if (ch.get('chapter_title') or ch.get('raw_text', '').strip()) else []
                }
        else:
            current_section["chapters"].append(ch)

    # 末尾块加入
    if current_section["chapters"]:
        sections.append(current_section)

    # # 打印提取的所有章节标题
    # for sec in sections:
    #     print(f"Section: {sec['section']}")
    #     for chap in sec["chapters"]:
    #         print(f"  Chapter ID: {chap['chapter_id']}, Title: {chap['chapter_title']}")

    return sections

def process_sections_with_lis(chapters, language='en'):
    # 先拆分成正文和多个附录
    sections = split_sections_by_appendix(chapters)

    # 每个部分内部单独跑最长链
    processed_sections = []
    for sec in sections:
        valid_chaps, skipped_content = find_longest_chapter_chain_with_append(sec["chapters"], language)
        processed_sections.append({
            "section": sec["section"],
            "context": skipped_content,  # 添加被跳过的内容
            "chapters": valid_chaps
        })

    return processed_sections

def filter_start_of_main(chapters: List[Dict]) -> Tuple[List[Dict], str]:
    """
    找到第一个正文章节作为起点，跳过目录
    """
    start_index = 0
    for i, chap in enumerate(chapters):
        chapter_id = chap.get("chapter_id", "").strip()
        # 正文主链或附件内部章节：数字开头或字母开头
        if chapter_id in {"1", "1-", "1.", "A", "A.", "A.1"}:
            # SCOPE / GENERAL / INTRO 等都算正文起点
            title_upper = chap.get("chapter_title", "").upper()
            if any(k in title_upper for k in ["SCOPE", "GENERAL", "INTRO", "总则", "范围", "LEGISLATIVE", "FUNCTION"]):
                start_index = i
                break
                
        # 也检查标准的章节开头模式
        if re.match(r'^[A-Z](\.\d+)*\.?$', chapter_id) or re.match(r'^\d+(\.\d+)*\.?$', chapter_id):
            title_upper = chap.get("chapter_title", "").upper()
            if any(k in title_upper for k in ["SCOPE", "GENERAL", "INTRO", "总则", "范围", "LEGISLATIVE", "FUNCTION"]):
                start_index = i
                break
                
    # print(f'chapters[str]: {chapters[start_index]}')
    filtered_chapters = chapters[start_index:]
    skipped_content = chapters[:start_index]
    skipped_text = "\n".join([f"{ch['chapter_id']} {ch['chapter_title']} {ch.get('raw_text','')}" for ch in skipped_content])

    return filtered_chapters, skipped_text


def smart_paragraph_join(lines: List[str]) -> str:
    """
    智能段落合并：只在段落结束时换行
    """
    if not lines:
        return ""
    
    result = []
    current_paragraph = []
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:  # 空行直接跳过
            continue
            
        # 检查是否是段落结束的标志
        is_paragraph_end = False
        
        # 1. 以标点符号结尾（中英文）
        if re.search(r'[。！？；：.!?;:]$', line):
            is_paragraph_end = True
            
        # 2. 检查下一行是否是新段落的开始
        if i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            # 下一行是章节标题、列表项、或明显的段落开始
            if (detect_chapter(next_line) or
                re.match(r'^[一二三四五六七八九十\d]+[、\.\)]', next_line) or  # 列表项
                re.match(r'^[（(]\d+[）)]', next_line) or  # 编号项
                re.match(r'^[——\-—]+', next_line)):  # 破折号开头
                is_paragraph_end = True
        
        # 3. 表格相关内容保持原有换行
        if ('表' in line and re.search(r'表\s*[A-Z0-9]', line)) or \
           re.match(r'^[|\s]*[A-Za-z0-9\u4e00-\u9fa5]+[|\s]*$', line):  # 简单表格行检测
            current_paragraph.append(line)
            is_paragraph_end = True
        else:
            current_paragraph.append(line)
        
        # 如果是段落结束，将当前段落合并并加入结果
        if is_paragraph_end:
            if current_paragraph:
                paragraph_text = ''.join(current_paragraph).strip()
                if paragraph_text:
                    result.append(paragraph_text)
                current_paragraph = []
    
    # 处理最后剩余的段落
    if current_paragraph:
        paragraph_text = ' '.join(current_paragraph).strip()
        if paragraph_text:
            result.append(paragraph_text)
    
    return '\n'.join(result)

def parse_pdf_to_chapter_tree(pdf_path: str) -> Tuple[List[Dict], Dict[str, str]]:
    """
    从 PDF 中提取章节树和术语映射
    :param pdf_path: PDF 文件路径
    :return: (章节树, 术语映射)
    """
    cleaned_lines = extract_full_text_with_filter(pdf_path)

    # 🆕 检测文档语言
    language = detect_document_language(cleaned_lines)
    max_chapter_num = 50 if language == 'zh' else 1000
    print(f"检测到文档语言: {'中文' if language == 'zh' else '英文'}, max_chapter_num={max_chapter_num}")

    # 🆕 第一轮：粗略提取所有可能的章节，用于分析数字分布
    preliminary_chapters = []
    current = {
        "chapter_id": "",
        "chapter_title": "",
        "raw_text": ""
    }
    buffer = []

    for line in cleaned_lines:
        # 第一轮使用宽松的数字范围进行粗提取
        chapter_info = detect_chapter(line, max_chapter_num=1000, language=language, number_analysis=None)

        if chapter_info:
            if current:
                current["raw_text"] = smart_paragraph_join(buffer)
                preliminary_chapters.append(current)
                buffer = []
            current = {
                "chapter_id": chapter_info["chapter_id"],
                "chapter_title": chapter_info["chapter_title"],
                "raw_text": ""
            }
        else:
            buffer.append(line)

    if current:
        current["raw_text"] = smart_paragraph_join(buffer)
        preliminary_chapters.append(current)

    # 🆕 分析章节数字分布
    number_analysis = analyze_chapter_number_distribution(preliminary_chapters)
    print(f"数字分布分析: {number_analysis}")

    # 🆕 第二轮：使用分析结果重新精确提取章节
    chapters = []
    current = {
        "chapter_id": "",
        "chapter_title": "",
        "raw_text": ""
    }
    buffer = []

    for line in cleaned_lines:
        chapter_info = detect_chapter(line, max_chapter_num=max_chapter_num, language=language, number_analysis=number_analysis)

        if chapter_info:
            if current:
                # 使用智能段落合并而不是简单的 \n 连接
                current["raw_text"] = smart_paragraph_join(buffer)
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
        current["raw_text"] = smart_paragraph_join(buffer)
        chapters.append(current)

    # 1️⃣ 先按附件切分顶层
    attachment_sections = split_sections_by_attachment(chapters)

    tree = []

    for top_sec in attachment_sections:
        
        # 2️⃣ 每个顶层块再按附录切分
        sections = split_sections_by_appendix(top_sec["chapters"])
        section_tree_list = []

        for sec in sections:
            # filtered_chapters, skipped_text = filter_start_of_main(sec["chapters"])
            # 3️⃣ 对每个部分内部保留最长链
            valid_chaps_in_sec, skipped_text = find_longest_chapter_chain_with_append(sec["chapters"], language)
            tree_in_sec = build_tree(valid_chaps_in_sec)
            build_full_path(tree_in_sec)
            # 插入键值对 section
            section_tree_list.append({
                "section": sec["section"],
                "context": skipped_text,
                "chapters": tree_in_sec,
            })

        # 4️⃣ 构建顶层树
        tree.append({
            "file": top_sec["section"],  # regulation 或 ANNEX n
            "sections": section_tree_list,
        })

    term_map = {}

    for chap in chapters:
        title = chap.get("chapter_title", "")
        if "术语" in title:
            # 提取术语
            terms = extract_terms_with_abbr_from_terms_section(chap["chapter_title"])
            term_map.update(terms)
            for child in chap.get("children", []):
                terms = extract_terms_with_abbr_from_terms_section(child["chapter_title"])
                term_map.update(terms)
        elif "缩略" in title:
            # 提取缩略语
            abbr_terms = extract_abbr_terms_from_symbols_section(chap["chapter_title"] + chap["raw_text"])
            term_map.update(abbr_terms)
            for child in chap.get("children", []):
                abbr_terms = extract_abbr_terms_from_symbols_section(child["chapter_title"] + child["raw_text"])
                term_map.update(abbr_terms)

    return tree, term_map

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
        if '表' in ln['text'] or 'Table' in ln['text']:
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

    # print(f"找到标题候选: {cand}")
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
                        if ("表" in item['text'] or 'Table' in item['text']) and 0 < (table_top - item['y']) < 60:
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
    # parser.add_argument("--pdf_path", default="C:/Users/chenhuaji/OneDrive/桌面/DAO2016-23-1.pdf")
    # parser.add_argument("--pdf_path", default="C:/Users/chenhuaji/OneDrive/桌面/CELEX_42012X0920(02)_EN_TXT.pdf")
    
    # parser.add_argument("--pdf_path", default="国标_车载事故紧急呼叫系统-征求意见稿.pdf")
    # parser.add_argument("--pdf_path", default="D:\\Documents\\知识图谱agent\\示例文件\\GBT+43187-2023 处理\\组合 1.pdf")
    
    # parser.add_argument("--pdf_path", default="GB∕T 38997-2020 轻小型多旋翼无人机飞行控制与导航系统通用要求.pdf")
    # parser.add_argument("--pdf_path", default="国标_车载事故紧急呼叫系统-征求意见稿_可识别文字.pdf")
    # parser.add_argument("--pdf_path", default="GB∕T 38930-2020 民用轻小型无人机系统抗风性要求及试验方法.pdf")
    # parser.add_argument("--pdf_path", default="GB 7258-2017 《机动车运行安全技术条件》.pdf")
    # parser.add_argument("--pdf_path", default="../示例文件/GB+11551-2014.pdf")
    # parser.add_argument("--pdf_path", default="../示例文件/GB+20071-2025.pdf")
    # parser.add_argument("--pdf_path", default="../示例文件/GB+20072-2024.pdf")
    # parser.add_argument("--pdf_path", default="../示例文件/GB+34660-2017.pdf")
    # parser.add_argument("--pdf_path", default="../示例文件/GBT+43187-2023.pdf")
    # parser.add_argument("--pdf_path", default="../示例文件/GBT+43187-2023_OCR.pdf")
    # parser.add_argument("--pdf_path", default="C:/Users/chenhuaji/OneDrive/桌面/test/GBT+43187-2023_page-0001_chrome.pdf")
    # parser.add_argument("--pdf_path", default="D:\\Documents\\知识图谱agent\\示例文件\\GB+34660-2017 处理\\组合 1.pdf")
    # parser.add_argument("--pdf_path", default="D:\\Documents\\知识图谱agent\\示例文件\\GBT+43187-2023 处理\\组合 1.pdf")
    # parser.add_argument("--pdf_path", default="GB+45672-2025.pdf")
    parser.add_argument("--pdf_path", default="D:/Documents/知识图谱agent/标准差异分析/GSO-1040/GSO-1040-2000_OCR/GSO-1040-2000-E机动车- 轻型柴油引擎车辆大气污染物排放允许限值.pdf")
    # parser.add_argument("--pdf_path", default="D:/Documents/知识图谱agent/标准差异分析/GSO-1040/CELEX_42006X1124(01)_EN_TXT.pdf")
    # parser.add_argument("--pdf_path", default="D:/Documents/知识图谱agent/标准差异分析/GSO-1040/CELEX_42006X1227(06)_EN_TXT.pdf")
    # parser.add_argument("--pdf_path", default="D:/Documents/知识图谱agent/标准差异分析/ADR60/R048r12e.pdf")
    # parser.add_argument("--pdf_path", default="D:/Documents/知识图谱agent/标准差异分析/ADR60/R007r6e.pdf")
    # parser.add_argument("--pdf_path", default="D:/Documents/知识图谱agent/标准差异分析/ADR60/F2023C00147.pdf")


    parser.add_argument("--output", help="输出 JSON 文件路径", default="output.json")
    args = parser.parse_args()

    chapter_tree, term_map = parse_pdf_to_chapter_tree(args.pdf_path)

    # # 提取表格
    # tables = extract_tables_from_pdf(args.pdf_path)
    
    # # 创建输出目录结构
    # output_data = {
    #     "chapters": chapter_tree,
    #     "tables": tables
    # }

    output_data = chapter_tree
    # # output_data["terms"] = term_map
    # output_data["tables"] = tables

    print(f'term_map: {term_map}')

    # 保存结果
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    # # file之间换行隔开，section直接换行隔开
    # with open(args.output, "w", encoding="utf-8") as f:
    #     for file in output_data:
    #         for section in file["sections"]:
    #             for chapter in section["chapters"]:
    #                 # 将chapter_title字段合并到rawtext，删掉chapter_title字段
    #                 # chapter["raw_text"] = chapter["chapter_title"] + " " + chapter["raw_text"]
    #                 # del chapter["chapter_title"]
    #                 f.write(json.dumps(chapter, ensure_ascii=False) + "\n")
    #             f.write("\n")
    #         f.write("\n")
    #     # json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 提取完成，章节和表格已保存至 {args.output}")
    print(f"   - 共提取 {len(chapter_tree)} 个章节")
    # print(f"   - 共提取 {len(tables)} 个表格")

if __name__ == "__main__":
    main()
