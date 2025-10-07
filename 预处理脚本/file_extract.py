# # # import pdfplumber

# # # text_all = []
# # # with pdfplumber.open("国标_车载事故紧急呼叫系统-征求意见稿.pdf") as pdf:
# # #     for page in pdf.pages:
# # #         text_all.append(page.extract_text(x_tolerance=2, y_tolerance=3))
# # # full_text = "\n".join(text_all)

# # # # 如想落盘
# # # with open("full_text.txt", "w", encoding="utf-8") as f:
# # #     f.write(full_text)


# # # import pdfplumber, csv

# # # with pdfplumber.open("国标_车载事故紧急呼叫系统-征求意见稿.pdf") as pdf:
# # #     for page_no, page in enumerate(pdf.pages, 1):
# # #         tables = page.extract_tables()          # list[list[list[str]]]
# # #         for table_id, table in enumerate(tables, 1):
# # #             with open(f"page{page_no}_table{table_id}.csv",
# # #                       "w", newline="", encoding="utf-8") as f:
# # #                 writer = csv.writer(f)
# # #                 writer.writerows(table)
# import pdfplumber
# import re
# import json
# from collections import defaultdict

# # 正则用于识别章节标题（支持 1、1.1、1.1.1、1.1.1.1 等）
# chapter_regex = re.compile(r'^(\d+(\.\d+)*)(\s+)(.+)$')

# # 构建树形结构
# def build_tree(chapter_list):
#     root = []
#     id_map = {}

#     for chapter in chapter_list:
#         parts = chapter["chapter_id"].split(".")
#         if len(parts) == 1:
#             root.append(chapter)
#         else:
#             parent_id = ".".join(parts[:-1])
#             parent = id_map.get(parent_id)
#             if parent:
#                 parent.setdefault("children", []).append(chapter)
#         id_map[chapter["chapter_id"]] = chapter
#     return root

# # 主处理逻辑
# def parse_pdf_to_structure(pdf_path):
#     with pdfplumber.open(pdf_path) as pdf:
#         all_text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

#     chapters = []
#     buffer = []
#     current = None

#     for line in all_text.split("\n"):
#         line = line.strip()
#         match = chapter_regex.match(line)
#         if match:
#             if current:
#                 current["raw_text"] = "\n".join(buffer).strip()
#                 chapters.append(current)
#                 buffer = []
#             chapter_id = match.group(1)
#             chapter_title = match.group(4)
#             current = {
#                 "chapter_id": chapter_id,
#                 "chapter_title": chapter_title,
#                 "raw_text": "",
#                 "full_path": "",  # 稍后生成
#                 "children": []
#             }
#         else:
#             buffer.append(line)

#     if current:
#         current["raw_text"] = "\n".join(buffer).strip()
#         chapters.append(current)

#     # 构造 full_path
#     chapter_dict = {c["chapter_id"]: c for c in chapters}
#     for chapter in chapters:
#         parts = chapter["chapter_id"].split(".")
#         path = []
#         for i in range(1, len(parts)+1):
#             cid = ".".join(parts[:i])
#             if cid in chapter_dict:
#                 path.append(f"{cid} {chapter_dict[cid]['chapter_title']}")
#         chapter["full_path"] = "/".join(path)

#     tree = build_tree(chapters)
#     return tree

# tree = parse_pdf_to_structure("国标_车载事故紧急呼叫系统-征求意见稿.pdf")
# with open("output.json", "w", encoding="utf-8") as f:
#     json.dump(tree, f, ensure_ascii=False, indent=2)
# import pdfplumber
# import re
# import json
# from collections import defaultdict
# from typing import List, Dict

# # 章节标题正则（支持 1、1.1、1.1.1、附录A、A.1 等）
# chapter_patterns = [
#     re.compile(r'^(附\s*录\s*[A-Z])\s+(.+)$'),                        # 附录A xxx
#     re.compile(r'^([A-Z](?:\.\d+)+)\s+(.+)$'),                        # A.1、B.2.3
#     re.compile(r'^(\d+(?:\.\d+)*)(\s+)(.+)$'),                        # 4、4.1、4.1.2
# ]

# def detect_chapter(line: str):
#     for pattern in chapter_patterns:
#         m = pattern.match(line)
#         if m:
#             return {
#                 "chapter_id": m.group(1).strip(),
#                 "chapter_title": m.group(len(m.groups())).strip()
#             }
#     return None

# def build_tree(chapter_list: List[Dict]) -> List[Dict]:
#     id_map = {}
#     root = []

#     for chap in chapter_list:
#         chap["children"] = []
#         id_map[chap["chapter_id"]] = chap

#     for chap in chapter_list:
#         parts = chap["chapter_id"].split(".")
#         if len(parts) == 1 or chap["chapter_id"].startswith("附录"):
#             root.append(chap)
#         else:
#             parent_id = ".".join(parts[:-1])
#             parent = id_map.get(parent_id)
#             if parent:
#                 parent["children"].append(chap)
#             else:
#                 root.append(chap)  # fallback

#     return root

# def build_full_path(chapters: List[Dict], path_prefix=""):
#     for chap in chapters:
#         if path_prefix:
#             chap["full_path"] = f"{path_prefix}/{chap['chapter_id']} {chap['chapter_title']}"
#         else:
#             chap["full_path"] = f"{chap['chapter_id']} {chap['chapter_title']}"
#         if chap.get("children"):
#             build_full_path(chap["children"], chap["full_path"])

# def parse_pdf_to_chapter_tree(pdf_path: str) -> List[Dict]:
#     with pdfplumber.open(pdf_path) as pdf:
#         lines = []
#         for page in pdf.pages:
#             text = page.extract_text()
#             if text:
#                 lines += text.split("\n")

#     chapters = []
#     current = None
#     buffer = []

#     for line in lines:
#         line = line.strip()
#         chapter_info = detect_chapter(line)

#         if chapter_info:
#             if current:
#                 current["raw_text"] = "\n".join(buffer).strip()
#                 chapters.append(current)
#                 buffer = []
#             current = {
#                 "chapter_id": chapter_info["chapter_id"],
#                 "chapter_title": chapter_info["chapter_title"],
#                 "raw_text": ""
#             }
#         else:
#             buffer.append(line)

#     if current:
#         current["raw_text"] = "\n".join(buffer).strip()
#         chapters.append(current)

#     # 构建 full_path
#     tree = build_tree(chapters)
#     build_full_path(tree)
#     # 删除第一层空节点
#     tree = [n for n in tree if n.get("raw_text") or n.get("children")]
#     return tree

# def main():
#     import argparse
#     parser = argparse.ArgumentParser()
#     # parser.add_argument("--pdf_path", "-o", help="PDF 文件路径", default="国标_车载事故紧急呼叫系统-征求意见稿.pdf")
#     # parser.add_argument("--output", "-o", help="输出 JSON 文件路径", default="output.json")
#     parser.add_argument("--pdf_path", help="PDF 文件路径", default="国标_车载事故紧急呼叫系统-征求意见稿.pdf")
#     parser.add_argument("--output",   help="输出 JSON 文件路径", default="output.json")
#     args = parser.parse_args()

#     tree = parse_pdf_to_chapter_tree(args.pdf_path)
#     with open(args.output, "w", encoding="utf-8") as f:
#         json.dump(tree, f, ensure_ascii=False, indent=2)
#     print(f"✅ 提取完成，已保存至 {args.output}")

# if __name__ == "__main__":
#     main()


# # import pdfplumber
# # import re
# # import json
# # from typing import List, Dict

# # # 章节标题正则（支持 1、1.1、1.1.1、附录A、A.1 等）
# # chapter_patterns = [
# #     re.compile(r'^(附\s*录\s*([A-Z]))\s+(.+)$'),        # 附录A xxx
# #     re.compile(r'^([A-Z](?:\.\d+)+)\s+(.+)$'),           # A.1、B.2.3
# #     re.compile(r'^(\d+(?:\.\d+)*)(\s+)(.+)$'),           # 4、4.1、4.1.2
# # ]

# # def detect_chapter(line: str):
# #     for pattern in chapter_patterns:
# #         m = pattern.match(line)
# #         if m:
# #             if '附' in m.group(1):  # 附录A
# #                 return {
# #                     "chapter_id": f"附录{m.group(2)}",
# #                     "chapter_title": m.group(3).strip()
# #                 }
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
# #         cid = chap["chapter_id"]
# #         # 附录处理
# #         if cid.startswith("附录"):
# #             if "." in cid:
# #                 # 附录A.1 → 挂在附录A
# #                 prefix = "附录" + cid.split(".")[0]
# #             else:
# #                 prefix = None  # 顶层附录
# #         else:
# #             prefix = ".".join(cid.split(".")[:-1]) if "." in cid else None

# #         if not prefix or prefix not in id_map:
# #             root.append(chap)
# #         else:
# #             id_map[prefix]["children"].append(chap)

# #     return root

# # def build_full_path(chapters: List[Dict], path_prefix=""):
# #     for chap in chapters:
# #         title_part = f"{chap['chapter_id']} {chap['chapter_title']}".strip()
# #         chap["full_path"] = f"{path_prefix}/{title_part}" if path_prefix else title_part
# #         if chap.get("children"):
# #             build_full_path(chap["children"], chap["full_path"])

# # def parse_pdf_to_chapter_tree(pdf_path: str) -> List[Dict]:
# #     with pdfplumber.open(pdf_path) as pdf:
# #         lines = []
# #         for page in pdf.pages:
# #             text = page.extract_text()
# #             if text:
# #                 lines += text.split("\n")

# #     chapters = []
# #     current = None
# #     buffer = []

# #     for line in lines:
# #         line = line.strip()
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
# #     return tree

# # def extract_tables(pdf_path: str) -> List[Dict]:
# #     tables = []
# #     with pdfplumber.open(pdf_path) as pdf:
# #         for page_no, page in enumerate(pdf.pages, 1):
# #             page_tables = page.extract_tables()
# #             for table_id, table in enumerate(page_tables, 1):
# #                 tables.append({
# #                     "page": page_no,
# #                     "table_id": f"{page_no}_{table_id}",
# #                     "content": table
# #                 })
# #     return tables

# # def main():
# #     import argparse
# #     parser = argparse.ArgumentParser()
# #     parser.add_argument("--pdf_path", help="PDF 文件路径", default="国标_车载事故紧急呼叫系统-征求意见稿.pdf")
# #     parser.add_argument("--output",   help="输出 JSON 文件路径", default="output.json")
# #     args = parser.parse_args()

# #     chapter_tree = parse_pdf_to_chapter_tree(args.pdf_path)
# #     table_data = extract_tables(args.pdf_path)

# #     result = {
# #         "chapters": chapter_tree,
# #         "tables": table_data
# #     }

# #     with open(args.output, "w", encoding="utf-8") as f:
# #         json.dump(result, f, ensure_ascii=False, indent=2)

# #     print(f"✅ 提取完成，共提取章节：{len(chapter_tree)}，表格：{len(table_data)}")
# #     print(f"✅ 已保存至：{args.output}")

# # if __name__ == "__main__":
# #     main()
import re
import pdfplumber
from collections import defaultdict

pdf_path = "国标_车载事故紧急呼叫系统-征求意见稿.pdf"

# 1. 预扫描：拿到“表 X.Y 标题”及其页码
title_map = defaultdict(list)          # page_num(从1开始) -> list[dict]

with pdfplumber.open(pdf_path) as pdf:
    for page_num, page in enumerate(pdf.pages, start=1):
        # 宽松参数：容忍 2pt 水平、3pt 垂直偏差
        text = page.extract_text(x_tolerance=2, y_tolerance=3)
        if "表" in text:
            print(f"预扫描：第 {page_num} 页有表标题")
        if not text:
            continue
        for line in text.splitlines():
            line = line.strip()
            if "表" in line:
                print(f"预扫描：第 {page_num} 页找到表标题：{line}")
            m = re.match(r'^\s*(表\s+[A-Z]?\d+\.\d+)\s+(.+)', line)
            if m:
                # 拿到整行
                title_map[page_num].append({
                    'id': m.group(1).strip(),
                    'text': line,
                    'y': None   # 下面会补
                })



print(f"预扫描完成，共找到 {sum(len(titles) for titles in title_map.values())} 个表标题")

def extract_tables_from_pdf(pdf_path: str, title_map: dict) -> list[dict]:
    """
    title_map: {page_num(1开始): [{'id':..., 'text':..., 'y':None}, ...]}
    返回: [{"table_id":"表X.Y 标题", "table_content":[[...]]}, ...]
    """
    all_tables = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            # 同样宽松参数
            text = page.extract_text(x_tolerance=2, y_tolerance=3)
            if not text:
                continue

            # 先给 title_map 补 y 坐标
            titles = title_map.get(page_num, [])
            for t in titles:
                # 找到对应文本在页面中的 y 坐标（取首字符 top）
                for c in page.chars:
                    if c['text'] and t['text'].startswith(c['text']):
                        t['y'] = c['top']
                        break

            # 页面里的所有表格（从上到下）
            tables = page.find_tables()
            tables = sorted(tables, key=lambda tb: tb.bbox[1])

            for tbl_idx, tbl in enumerate(tables):
                # 过滤：只有 1 列
                rows = tbl.extract()
                if not rows or len(rows[0]) <= 1:
                    continue

                # 清理内容
                cleaned = [[(cell or '').replace('\n', ' ').strip() for cell in row]
                           for row in rows]

                # 找标题：表格顶部上方 60 pt 内最近的“表 X.Y …”
                tbl_top = tbl.bbox[1]
                best = None
                min_gap = 60
                for t in titles:
                    if t['y'] is None:
                        continue
                    gap = tbl_top - t['y']
                    if 0 < gap < min_gap:
                        min_gap = gap
                        best = t['text']

                table_id = best if best else f"表-页{page_num}-{tbl_idx+1}"

                all_tables.append({
                    "table_id": table_id,
                    "table_content": cleaned
                })

    return all_tables


# 1. 预扫描
import json
title_map = defaultdict(list)
with pdfplumber.open(pdf_path) as pdf:
    for page_num, page in enumerate(pdf.pages, start=1):
        text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
        for line in text.splitlines():
            line = line.strip()
            m = re.match(r'^\s*(表\s*[A-Z]?\d+(?:\.\d+)*)\s+(.+)', line)
            if m:
                title_map[page_num].append({'id': m.group(1), 'text': line, 'y': None})

# 2. 正式提取
tables = extract_tables_from_pdf(pdf_path, title_map)

# 3. 存盘
with open("tables.json", "w", encoding="utf-8") as f:
    json.dump(tables, f, ensure_ascii=False, indent=2)

print("共提取", len(tables), "个表")