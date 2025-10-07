import fitz  # PyMuPDF
import re

def fix_broken_chapters(lines: list[str]) -> list[str]:
    merged_final = []
    j = 0
    m = len(lines)

    # 复用你的 chapter_patterns，但去掉捕获组
    num_pattern = re.compile(r'^\d+(?:\.\d+)*$')
    alpha_pattern = re.compile(r'^[A-Z](?:\.\d+)*$')

    while j < m:
        line = lines[j].strip()
        next_line = lines[j + 1].strip() if j + 1 < m else ""

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

def extract_full_text_with_filter(pdf_path: str, output_txt_path: str, y_tol=2.5, x_tol=5):
    doc = fitz.open(pdf_path)
    all_lines = []

    for page in doc:
        spans_all = []

        h = page.rect.height
        clip_rect = fitz.Rect(0, h*0.10, page.rect.width, h*0.90)

        # 提取所有 span 信息
        for block in page.get_text("dict", clip=clip_rect)["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if not text:
                        continue
                    x0, y0, x1, y1 = span["bbox"]
                    spans_all.append({
                        "text": text,
                        "x0": x0,
                        "x1": x1,
                        "y0": y0,
                        "y1": y1
                    })

        # 按 y 排序，确保自上而下
        spans_all.sort(key=lambda s: (round(s["y0"], 1), s["x0"]))

        merged_lines = []
        current_line = []
        current_y = None

        for span in spans_all:
            y = span["y0"]

            if current_y is None or abs(y - current_y) <= y_tol:
                current_line.append(span)
                current_y = y if current_y is None else (current_y + y) / 2
            else:
                merged_lines.append(current_line)
                current_line = [span]
                current_y = y

        if current_line:
            merged_lines.append(current_line)

        # 合并每一行内的 span（按 x0 顺序 + 控制空格）
        for line in merged_lines:
            line.sort(key=lambda s: s["x0"])
            merged_text = ""
            last_x1 = None
            for span in line:
                if last_x1 is not None and span["x0"] - last_x1 > x_tol:
                    merged_text += " "
                merged_text += span["text"]
                last_x1 = span["x1"]
            all_lines.append(merged_text.strip())

    all_lines = fix_broken_chapters(all_lines)

    # 写入文件
    with open(output_txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(all_lines))




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
    output_txt_path="extracted_full_text_3.txt"
)
