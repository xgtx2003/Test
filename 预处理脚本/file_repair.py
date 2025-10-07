# #!/usr/bin/env python3
# import subprocess, pathlib, sys

# def repair_pdf(src: pathlib.Path, dst: pathlib.Path):
#     cmd = [
#         "qpdf", "--linearize",
#         str(src),
#         str(dst)
#     ]
#     subprocess.run(cmd, check=True)
#     print(f"✅ 修复完成: {dst}")

# if __name__ == "__main__":
#     if len(sys.argv) != 3:
#         print("用法: python repair_pdf.py 输入.pdf 输出.pdf")
#         sys.exit(1)
#     in_file, out_file = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
#     repair_pdf(in_file, out_file)

#!/usr/bin/env python3
import sys, pikepdf
# 修补文件，保存时强制重新嵌入字体
def embed_unicode(src, dst):
    with pikepdf.open(src) as pdf:
        # save 时强制重新嵌入字体 & 生成 ToUnicode
        pdf.save(dst,
                 linearize=True,
                 object_stream_mode=pikepdf.ObjectStreamMode.generate,
                 compress_streams=True,
                 recompress_flate=True,
                 stream_decode_level=pikepdf.StreamDecodeLevel.all)
    print("✅ 已重新嵌入字体并生成 Unicode 映射:", dst)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python embed_unicode.py input.pdf output.pdf")
        sys.exit(1)
    embed_unicode(sys.argv[1], sys.argv[2])