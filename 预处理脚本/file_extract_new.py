# # #!/usr/bin/env python3
# # # -*- coding: utf-8 -*-
# # """
# # 按字符级粗体信息精确拆分标题与正文
# # 要求：
# # 1. 只有章节号（含空格）是粗体 → 其余部分算正文
# # 2. 第一层节点若无子节点且无正文 → 直接删除
# # """

# # import pdfplumber
# # import re
# # import json
# # import argparse
# # from typing import List, Dict, Tuple, Optional

# # # -------------- 正则列表 --------------
# # PATTERNS = [
# #     re.compile(r'^(附录\s*[A-Z])\s+(.+)$'),          # 附录A xxx
# #     re.compile(r'^([A-Z](?:\.\d+)+)\s+(.+)$'),       # A.1、B.2.3
# #     re.compile(r'^(\d+(?:\.\d+)*)\s+(.+)$'),         # 4、4.1、4.1.2
# # ]

# # # -------------- 粗体判定 --------------
# # def is_bold(char: Dict) -> bool:
# #     font = (char.get("fontname") or "").upper()
# #     return any(k in font for k in ("BOLD", "HEAVY", "BLACK"))

# # # -------------- 拆分一行 --------------
# # def split_line(line: str, page) -> Tuple[Optional[str], Optional[str], str]:
# #     """
# #     返回 (chapter_id, chapter_title, extra)
# #     extra 为“非粗体”部分，直接放到 raw_text 最前面
# #     """
# #     # 1. 先尝试正则
# #     for pat in PATTERNS:
# #         m = pat.match(line)
# #         if m:
# #             cid, tail = m.group(1), m.group(2)
# #             break
# #     else:
# #         return None, None, ""

# #     # 2. 找到这一行的所有字符
# #     y_top = page.height
# #     y_bottom = 0
# #     for c in page.chars:
# #         if c["text"] and c["text"] in line:
# #             y_top = min(y_top, c["y0"])
# #             y_bottom = max(y_bottom, c["y1"])
# #     chars = [c for c in page.chars if y_top <= c["y0"] <= y_bottom and c["text"]]

# #     # 3. 计算粗体结束位置
# #     bold_end = 0
# #     for i, c in enumerate(chars):
# #         if not is_bold(c):
# #             bold_end = i
# #             break
# #     else:
# #         bold_end = len(chars)

# #     bold_part = "".join([c["text"] for c in chars[:bold_end]]).strip()
# #     rest_part = "".join([c["text"] for c in chars[bold_end:]]).strip()

# #     # 4. 再对粗体部分做一次正则，防止只匹配到序号
# #     for pat in PATTERNS:
# #         m2 = pat.match(bold_part)
# #         if m2:
# #             return m2.group(1), "", rest_part  # 标题只保留章节号

# #     # 如果整行都没匹配到，直接返回整行
# #     return cid, tail, ""

# # # -------------- 构造树 --------------
# # def build_tree(chapters: List[Dict]) -> List[Dict]:
# #     id_map = {c["chapter_id"]: c for c in chapters}
# #     root = []
# #     for c in chapters:
# #         c.setdefault("children", [])
# #     for c in chapters:
# #         parts = c["chapter_id"].split(".")
# #         if len(parts) == 1 or c["chapter_id"].startswith("附录"):
# #             root.append(c)
# #         else:
# #             parent_id = ".".join(parts[:-1])
# #             if parent_id in id_map:
# #                 id_map[parent_id]["children"].append(c)
# #             else:
# #                 root.append(c)  # fallback
# #     return root

# # def build_full_path(nodes: List[Dict], prefix: str = ""):
# #     for n in nodes:
# #         if prefix:
# #             n["full_path"] = f"{prefix}/{n['chapter_id']}"
# #         else:
# #             n["full_path"] = n["chapter_id"]
# #         build_full_path(n.get("children", []), n["full_path"])

# # # -------------- 主解析 --------------
# # def parse(pdf_path: str) -> List[Dict]:
# #     chapters, current, buffer = [], None, []

# #     with pdfplumber.open(pdf_path) as pdf:
# #         for page in pdf.pages:
# #             if not page.extract_text():
# #                 continue
# #             for line in page.extract_text().splitlines():
# #                 line = line.strip()
# #                 if not line:
# #                     continue

# #                 cid, title, extra = split_line(line, page)
# #                 if cid is not None:
# #                     if current:
# #                         current["raw_text"] = "\n".join(buffer).strip()
# #                         chapters.append(current)
# #                         buffer = []
# #                     current = {
# #                         "chapter_id": cid,
# #                         "chapter_title": title or "",  # 只保留章节号
# #                         "raw_text": extra or ""
# #                     }
# #                 else:
# #                     buffer.append(line)

# #     if current:
# #         current["raw_text"] = "\n".join(buffer).strip()
# #         chapters.append(current)

# #     tree = build_tree(chapters)
# #     build_full_path(tree)

# #     # 删除第一层空节点
# #     tree = [n for n in tree if n.get("raw_text") or n.get("children")]
# #     return tree

# # # -------------- CLI --------------
# # def main():
# #     parser = argparse.ArgumentParser()
# #     parser.add_argument("--pdf", default="国标_车载事故紧急呼叫系统-征求意见稿.pdf")
# #     parser.add_argument("--out", default="output.json")
# #     args = parser.parse_args()

# #     tree = parse(args.pdf)
# #     with open(args.out, "w", encoding="utf-8") as f:
# #         json.dump(tree, f, ensure_ascii=False, indent=2)
# #     print("✅ 完成 ->", args.out)

# # if __name__ == "__main__":
# #     main()

import pdfplumber
import re
import json
import os
from collections import defaultdict
from typing import List, Dict, Tuple, Optional

# 章节标题正则（支持 1、1.1、1.1.1、附录A、A.1 等）
chapter_patterns = [
    re.compile(r'^(附\s*录\s*[A-Z])\s+(.+)$'),                        # 附录A xxx
    re.compile(r'^([A-Z](?:\.\d+)+)\s+(.+)$'),                        # A.1、B.2.3
    re.compile(r'^(\d+(?:\.\d+)*)(\s+)(.+)$'),                        # 4、4.1、4.1.2
]

# 表格标题正则（表X.x形式）
table_id_regex = re.compile(r'^\s*表\s*([A-Z]*\d+(?:\.[\d]+)*)\s*$')  # 匹配表1.1, 表A.1等

def detect_chapter(line: str):
    for pattern in chapter_patterns:
        m = pattern.match(line)
        if m:
            return {
                "chapter_id": m.group(1).strip(),
                "chapter_title": m.group(len(m.groups())).strip()
            }
    return None

def build_tree(chapter_list: List[Dict]) -> List[Dict]:
    id_map = {}
    root = []

    # 初始化 id_map
    for chap in chapter_list:
        chap["children"] = []
        id_map[chap["chapter_id"]] = chap

    # 构建普通父子关系
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
                # 检查是否是 A.1, B.2 这类格式
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
                    else:
                        appendix_node = id_map[appendix_id]
                    appendix_node["children"].append(chap)
                else:
                    root.append(chap)  # fallback

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
        if 0xFF01 <= code <= 0xFF5E:  # 全角字符范围
            result.append(chr(code - 0xFEE0))
        else:
            result.append(char)
    return ''.join(result)


def is_valid_next_chapter(prev_parts: list, chapter_id: str) -> bool:
    """
    判断 chapter_id 是否可能为前一个章节号的“下一个”合法编号。
    prev_parts: 前一个有效章节号按'.'分割后的 int 列表，例如 [4,1,10]
    chapter_id: 当前待检测的章节号字符串，如 "4.2"
    返回 True 表示合法，False 表示非法
    """
    # 1. 过滤带单位的伪编号
    if re.search(r'\d+\s*(mm|cm|kg|km/h|%|℃)', chapter_id, re.I):
        return False

    # 2. 附录直接放过
    if re.match(r'^[A-Z](?:\.\d+)*$', chapter_id):
        return True

    # 3. 解析为数字列表
    try:
        parts = [int(p) for p in chapter_id.split('.')]
    except ValueError:
        return False

    # # 4. 首章直接通过
    # if not prev_parts:
    #     return True

    # 5. 同层递增：4.1.10 -> 4.1.11
    if len(parts) == len(prev_parts) and parts[:-1] == prev_parts[:-1] and parts[-1] == prev_parts[-1] + 1:
        return True

    # 6. 升层：4.1.10 -> 4.2
    if len(parts) < len(prev_parts) and parts[:-1] == prev_parts[:len(parts)-1] and parts[-1] == prev_parts[len(parts) - 1] + 1:
        return True

    # 7. 子层：4.1.10 -> 4.1.10.1
    if len(parts) == len(prev_parts) + 1 and parts[:-1] == prev_parts and parts[-1] == 1:
        return True

    return False

def build_term_dict(raw_text: str) -> Dict[str, str]:
    """
    返回: {中文术语: 英文术语}
    """
    # 把多个换行压成一个
    text = re.sub(r'\n+', '\n', raw_text.strip())

    # 关键正则：
    # 3.1\n
    # 中文术语英文字符串（中间无换行）
    # 然后一个换行开始描述
    pattern = re.compile(
        r'^\d+\.\d+\n'                     # 3.1
        r'(?P<cn>[^\n]*?)\s*'             # 中文术语（无换行）
        r'(?P<en>[A-Za-z].*?)\s*(?=\n)',  # 英文术语（直到换行）
        re.MULTILINE
    )

    term_map = {}
    for m in pattern.finditer(text):
        cn = m.group("cn").strip()
        en = m.group("en").strip()
        if cn and en:
            term_map[cn] = en
    return term_map

def parse_pdf_to_chapter_tree(pdf_path: str) -> Tuple[List[Dict], Dict[str, str]]:
    with pdfplumber.open(pdf_path) as pdf:
        lines = []
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=3, y_tolerance=3)
            if text:
                lines += text.split("\n")

    chapters = []
    current = None
    buffer = []

    for line in lines:
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

    # ✅ 新增：过滤掉“范围”之前的章节
    start_index = 0
    for i, chap in enumerate(chapters):
        if chap.get("chapter_id") == "1" and chap.get("chapter_title", "") == "范围":
            start_index = i
            break
    print(start_index)
    filtered_chapters = chapters[start_index:]

    # # 当raw_text为空且children都为空列表时，将chapter_title移动到raw_text
    # for chap in filtered_chapters:
    #     if not chap.get("raw_text") and not chap.get("children"):
    #         chap["raw_text"] = chap.get("chapter_title", "")
    #         chap["chapter_title"] = ""


    # 🔍 再做递增校验
    valid_chapters = [filtered_chapters[0]]
    prev_parts = [1,]

    for chap in filtered_chapters[1:]:
        cid = chap["chapter_id"]
        if not is_valid_next_chapter(prev_parts, cid):
            print(f"无效章节: {cid}, 标题: {chap['chapter_title']}")
            # 追加到最近有效章节
            if valid_chapters:                       # 有有效章节
                valid_chapters[-1]["raw_text"] += "\n" + chap['chapter_id'] + chap["chapter_title"]
                print(f"追加到上一有效章节: {valid_chapters[-1]['chapter_id']}")
            continue

        print(f"有效章节: {cid}, 标题: {chap['chapter_title']}")
        valid_chapters.append(chap)                  # 首次加入列表

        try:
            prev_parts = [int(p) for p in cid.split('.')]
        except ValueError:
            # prev_parts = []   # 附录
            prev_parts = [-1]  # 附录用 -1 代替，避免影响递增判断

    # valid_chapters = filtered_chapters  # 直接使用过滤后的章节列表

    # 构建 full_path
    tree = build_tree(valid_chapters)
    build_full_path(tree)
    # # 删除第一层空节点
    # tree = [n for n in tree if n.get("raw_text") or n.get("children")]

    # 假设 third_chapter 是章节树里 chapter_id == "3" 的字典
    third_chapter = valid_chapters[2]               # 你解析到的第三章节点
    raw = third_chapter["raw_text"]
    term_map = build_term_dict(raw)
    # print(term_map)

    return tree, term_map

import re
from collections import defaultdict
from typing import List, Dict
import pdfplumber


def extract_tables_from_pdf(pdf_path: str) -> List[Dict]:
    """
    从PDF中提取所有表格及其标识
    返回格式: [{"table_id": "表X.x 标题", "table_content": 二维数组}, ...]
    """
    all_tables = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            # ---- 1. 先收集页面文本行及其 y 坐标，方便后面找标题 ----
            page_lines = []
            if page.extract_text():
                chars = page.chars
                rows = defaultdict(list)
                for c in chars:
                    rows[int(c['top'])].append(c)
                for top in sorted(rows.keys()):
                    line = ''.join([c['text'] for c in rows[top]]).strip()
                    page_lines.append({'text': line, 'y': top})

            # ---- 2. 提取并排序表格 ----
            tables = page.find_tables()
            if not tables:
                continue
            tables = sorted(tables, key=lambda t: t.bbox[1])  # 从上到下

            # ---- 3. 处理每个表格 ----
            for table_idx, table in enumerate(tables):
                # 过滤：只有 1 列的直接丢弃
                sample_row = table.extract()[0] if table.extract() else []
                if len(sample_row) <= 1:
                    continue

                # 获取表格内容
                table_data = table.extract()
                cleaned_data = [
                    [cell.replace('\n', ' ').strip() if cell else "" for cell in row]
                    for row in table_data
                ]

                # ---- 找标题：在表格上方 50 pt 内找“表 X.Y …”整行 ----
                table_top = table.bbox[1]
                best_line = None
                min_gap = float('inf')
                for item in page_lines:
                    if "表" in item['text'] and 0 < (table_top - item['y']) < 50:
                        gap = table_top - item['y']
                        if gap < min_gap:
                            min_gap = gap
                            best_line = item['text']

                # 【修改】逻辑：找不到标题时，尝试合并到上一张表
                if best_line:
                    # 找到了标题 -> 新增一张表
                    all_tables.append({
                        "table_id": best_line,
                        "table_content": cleaned_data
                    })
                else:
                    if all_tables:
                        # 【修改】找不到标题 -> 把当前表内容追加到上一张表
                        all_tables[-1]["table_content"].extend(cleaned_data)
                    else:
                        # 整个文档第一张表就找不到标题，兜底命名
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
    # parser.add_argument("--pdf_path", help="PDF 文件路径", default="国标_车载事故紧急呼叫系统-征求意见稿.pdf")
    # parser.add_argument("--pdf_path", help="PDF 文件路径", default="GB∕T 38930-2020 民用轻小型无人机系统抗风性要求及试验方法.pdf")
    # parser.add_argument("--pdf_path", help="PDF 文件路径", default="GB 7258-2017 《机动车运行安全技术条件》.pdf")
    # parser.add_argument("--pdf_path", help="PDF 文件路径", default="../示例文件/GB+11551-2014.pdf")
    parser.add_argument("--pdf_path", help="PDF 文件路径", default="GB+45672-2025.pdf")
    parser.add_argument("--output",   help="输出 JSON 文件路径", default="output.json")
    args = parser.parse_args()

    # 提取章节结构
    chapter_tree, term_map = parse_pdf_to_chapter_tree(args.pdf_path)

    # 提取表格
    tables = extract_tables_from_pdf(args.pdf_path)
    
    # 创建输出目录结构
    output_data = {
        "chapters": chapter_tree,
        "tables": tables
    }
    
    # 保存结果
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 提取完成，章节和表格已保存至 {args.output}")
    print(f"   - 共提取 {len(chapter_tree)} 个章节")
    print(f"   - 共提取 {len(tables)} 个表格")


# def main(pdf_path: str) -> dict:
#     # 章节树
#     tree, term_map = parse_pdf_to_chapter_tree(pdf_path)
#     # 表格
#     tables = extract_tables_from_pdf(pdf_path)

#     # 1-3 章（id 为 '1','2','3'）
#     context = str(tree[:3])

#     # 章节内容


#     # 其余章节（非附录、非前三章）
#     chapter_text = []
#     for c in tree:
#         if c['chapter_id'] not in {"1", "2", "3"} and not c['chapter_id'].startswith("附录"):
#             chapter_text.append(c)

#     appendix = str([c for c in tree if c['chapter_id'].startswith("附录")])

#     # 表格内容
#     tables_str = str(tables)

#     return {
#         "context": context,
#         "chapter_text": chapter_text,
#         "appendix": appendix,
#         "tables": tables_str
#     }

if __name__ == "__main__":
    # print(main("国标_车载事故紧急呼叫系统-征求意见稿.pdf"))
    main()



import pdfplumber
import re

def extract_full_text_with_filter(pdf_path, output_txt_path):
    """
    使用 pdfplumber 完整提取 PDF 文本：
    1. 自动过滤水印
    2. 修复特殊字符编码（如犌犅 → GB）
    3. 保留段落结构
    """
    full_text = []
    total_lines = 0

    # 定义水印过滤规则（可根据实际文件调整）
    watermark_patterns = [
        re.compile(r'下载者：.*?批准者：.*?\d{2}:\d{2}:\d{2}'),
        re.compile(r'犌犅／犜[\d—]+'),
    ]

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                full_text.append(f"[Page {i+1}] <no extractable text>")
                continue

            cleaned_lines = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue

                # 水印过滤
                if any(p.search(line) for p in watermark_patterns):
                    continue

                # 特殊字符替换
                line = line.replace('犌犅', 'GB').replace('／', '/')

                cleaned_lines.append(line)

            total_lines += len(cleaned_lines)
            full_text.append("\n".join(cleaned_lines))

    # 写入文件
    with open(output_txt_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(full_text))

    print(f"✅ 文本已提取到 {output_txt_path}")
    print(f"总页数: {len(full_text)}")
    print(f"有效文本行: {total_lines}")

# 示例调用（请按需修改路径）
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("❗用法: python extract_full_text_with_filter_plumber.py <PDF路径> <输出TXT路径>")
    else:
        extract_full_text_with_filter(sys.argv[1], sys.argv[2])
