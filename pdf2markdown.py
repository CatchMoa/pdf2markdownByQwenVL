import os
import fitz  # PyMuPDF
import os
from agent import VLAgent
import re
import sys

def find_missing_markdown_images(image_paths_list, markdown_string):
    """
    检查图片路径列表中哪些路径未在Markdown字符串中作为图片链接出现。

    Args:
        image_paths_list (list): 一个包含图片路径字符串的列表。
        markdown_string (str): 一个Markdown格式的字符串。

    Returns:
        list: 一个包含缺失的图片路径的列表。
    """
    # 正则表达式匹配 Markdown 图片语法: ![alt text](image_path)
    # 它会捕获括号内的内容，即图片路径。
    # !\[.*?\]\((.*?)\)
    # !\[.*?\] : 匹配 ![alt text] 的部分，非贪婪匹配
    # \( : 匹配左括号 (
    # (.*?) : 捕获括号内的任意字符 (图片路径)，非贪婪匹配
    # \) : 匹配右括号 )
    markdown_image_pattern = re.compile(r'!\[.*?\]\((.*?)\)')

    # 查找Markdown字符串中所有的图片路径
    found_image_paths_in_md = set(markdown_image_pattern.findall(markdown_string))

    # 检查输入的图片路径列表中的每个路径是否在找到的路径集合中
    missing_paths = []
    for path in image_paths_list:
        if path not in found_image_paths_in_md:
            missing_paths.append(path)

    return missing_paths


def extract_images_from_pdf_page(page, pdf_document, output_folder: str):
    images_on_page = page.get_images(full=True)
    seen_images_xrefs = set()
    extracted_images = []
    for img_index, img_info in enumerate(images_on_page):
        xref = img_info[0] # 图片的 XRef (交叉引用) 号
        
        # 如果这个图片对象之前已经处理过，就跳过
        if xref in seen_images_xrefs:
            continue

        # 将 XRef 添加到已处理集合
        seen_images_xrefs.add(xref)

        # 提取图片数据
        img_data = pdf_document.extract_image(xref)
        
        if img_data:
            # img_data 是一个字典，包含 'ext', 'image', 'smask', 'width', 'height', 'colorspace', 'bpc' 等信息
            image_extension = img_data['ext'] # 图片格式扩展名 (jpg, png, jpx, etc.)
            image_bytes = img_data['image']   # 图片的原始字节数据

            # 构建输出文件名。使用 XRef 可以确保文件名对于同一个 PDF 内的唯一图片是唯一的。
            output_filename = f"image_xref{xref}.{image_extension}"
            output_image_path = os.path.join(output_folder, output_filename)

            # 保存图片文件
            try:
                with open(output_image_path, "wb") as img_file:
                    img_file.write(image_bytes)
                extracted_images.append(output_image_path)
                print(f"提取并保存图片: {output_image_path}")
            except IOError as e:
                print(f"错误: 保存图片文件失败 {output_image_path}: {e}")
    return extracted_images



def pdf2markdown(pdf_path: str, output_folder: str, start_page:int, end_page: int, dpi: int = 300, image_format: str = 'png'):
    os.makedirs(output_folder, exist_ok=True)
    converted_images = list()
    vl_agent = VLAgent("QwenVLLocal")
    result_txt_file_path = os.path.join(output_folder, "result.txt")
    if pdf_path and os.path.exists(pdf_path):
        print(f"正在将 PDF ({pdf_path}) 转换为图片...")
        pdf_document = fitz.open(pdf_path)
        # extract_images_from_pdf(pdf_path, output_folder)
        # 设置缩放矩阵，用于控制输出图片的 DPI
        # 1 point = 1/72 inch
        zoom_matrix = fitz.Matrix(dpi / 72.0, dpi / 72.0)
        page_count = pdf_document.page_count
        if(end_page > page_count):
            end_page = page_count
        if(end_page < 0):
            end_page = page_count
        for page_num in range(start_page - 1, end_page):
            page = pdf_document.load_page(page_num)  # 获取页面
            pixmap = page.get_pixmap(matrix=zoom_matrix) # 渲染页面为 pixmap
            # 构建输出文件名，使用页码补零，方便排序
            output_filename = f"page_{page_num + 1:04d}.{image_format}"
            output_image_path = os.path.join(output_folder, output_filename)
            
            pixmap.save(output_image_path) # 保存 pixmap 为图片文件
            converted_images.append(output_image_path)
            print(f"已保存页面 {page_num + 1} 为 {output_image_path}")
            extract_images = extract_images_from_pdf_page(page, pdf_document, output_folder)
            # if(page_num == 0):
            query = "这是文档中提取的图片的路径 " + str(extract_images) + "替换截图中的图片位置"
            response = vl_agent.run(output_image_path, query)

            # while(True):
            markdown_text_list = vl_agent.extract_maskdown_content(response)
            last_markdown_text = ""
            for markdown_text in markdown_text_list:
                last_markdown_text = last_markdown_text + markdown_text
            missing_paths = find_missing_markdown_images(extract_images, last_markdown_text)
            if(len(missing_paths) != 0):
                for missing_path in missing_paths:
                    last_markdown_text += "\n" + f"![missing image]({missing_path})"
                check_response = "你没有找到所有从pdf中提取的图片路径，缺少了" + str(missing_paths) + "你可能需要重新看看我输入的文档截图。"  #如果你坚持认为缺失的图片路径未出现在文档内容中，则将我给出的图片路径按Markdown图片语法输出至原有markdown文本最后即可。
                print("\n", check_response)
                response = vl_agent.continue_run(check_response)
                markdown_text_list = vl_agent.extract_maskdown_content(response)

            current_markdown_text = ""
            for markdown_text in markdown_text_list:
                current_markdown_text = current_markdown_text + markdown_text
            missing_paths = find_missing_markdown_images(extract_images, current_markdown_text)
            if(len(missing_paths) != 0):
                print("\n use last_markdown_text")
                current_markdown_text = last_markdown_text

            vl_agent.reset_interlocution_message()
            # markdown_text_list = vl_agent.extract_maskdown_content(response)
            with open(result_txt_file_path, "a+") as f:
                # for markdown_text in markdown_text_list:
                f.write(current_markdown_text)

        pdf_document.close() # 关闭 PDF 文档
        print(f"成功转换 {len(converted_images)} 页。")
        return converted_images
    

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: uv run pdf2markdown.py <path_to_pdf> <path_to_save_folder> <pdf_start page> <pdf end page>")
        sys.exit(1) 
    server_paths = sys.argv[1:]
    pdf_path = sys.argv[1]
    output_folder = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(pdf_path)[0]
    start_page = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    end_page = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    pdf2markdown(pdf_path, output_folder, start_page, end_page)
