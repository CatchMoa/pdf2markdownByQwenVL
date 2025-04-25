# pdf2markdownByQwenVL
使用Qwen/Qwen2.5-VL-7B-Instruct模型进行OCR文本提取并保存为markdown格式文本，同时会提取pdf中的图片，但目前图片的位置提取不太稳定。


1. 安装依赖库：
pip install uv

2. 配置config.py文件：
'api_key' : "本地部署的Qwen OpenAI-API-compatible 服务api key",
'base_url' : "本地部署的Qwen OpenAI-API-compatible 服务地址",

3. 运行
uv run pdf2markdown.py pdf_file_path save_dir satrt_page end_page

4. 运行示例：
uv run pdf2markdown.py ./Memorandum.pdf ./save_dir 1 2

注意:
如果需要使用在线的Qwen OpenAI-API-compatible 服务，请将config.py中的api_key和base_url设置为你的服务地址和api key，并修改model_idx。