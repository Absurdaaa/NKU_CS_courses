import PyPDF2

def pdf_to_text(pdf_path, txt_path, batch_size=10):
  try:
    # 打开 PDF 文件
    with open(pdf_path, 'rb') as pdf_file:
      reader = PyPDF2.PdfReader(pdf_file)
      total_pages = len(reader.pages)
      print(f"PDF 文件共有 {total_pages} 页。")

      # 分批读取并写入文本文件
      with open(txt_path, 'w', encoding='utf-8') as txt_file:
        for start_page in range(0, total_pages, batch_size):
          end_page = min(start_page + batch_size, total_pages)
          print(f"正在处理第 {start_page + 1} 到第 {end_page} 页...")
          for page_num in range(start_page, end_page):
            page = reader.pages[page_num]
            txt_file.write(page.extract_text())
            txt_file.write("\n")
      print(f"转换完成，文本已保存到 {txt_path}")
  except Exception as e:
    print(f"发生错误: {e}")

# 使用示例
pdf_path = "Architecture Reference Manual ArmV8.pdf"  # 替换为你的 PDF 文件路径
txt_path = "Architecture Reference Manual ArmV8_output.txt"          # 替换为输出的文本文件路径
pdf_to_text(pdf_path, txt_path, batch_size=20)