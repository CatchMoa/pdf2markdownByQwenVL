import json
from openai import OpenAI
import re
import base64
from config import *

 
class Agent():
    def __init__(self, engine):
        self.engine_config = engine_config
        self.current_engine_config = self.engine_config[engine]
        self.client = OpenAI(
            api_key=self.current_engine_config['api_key'], 
            base_url=self.current_engine_config['base_url'],
        )
        self.chat_model_list = self.load_model_list()
        self.system_prompt = "You are a helpful assistant."
        self.interlocution_message = [
                {'role': 'system', 'content': self.system_prompt},  # 'You are a helpful assistant.'
                ]
        self.model_idx = 0

    def load_model_list(self):
        chat_model_list = list()
        models_list = self.client.models.list()
        for model in models_list.data: # Access the 'data' attribute for the list of models
            chat_model_list.append(model.id)
        return chat_model_list
        
    def changeEngine(self, engine):
        self.current_engine_config = self.engine_config[engine]
        self.client = OpenAI(
            api_key=self.current_engine_config['api_key'], 
            base_url=self.current_engine_config['base_url'],
        )
        self.chat_model_list = self.load_model_list()
        
    def run_model_with_stream(self, model_name, interlocution_message, temperature=0.2, outprint=True):
        data_info = list()
        try:
            response = ""
            completion = self.client.chat.completions.create(
                model=model_name,
                messages=interlocution_message,
                temperature = temperature,
                stream=True,
                stream_options={"include_usage": True},
                )
            for chunk in completion:
                data = json.loads(chunk.model_dump_json())
                if(data['choices'] !=None):
                    if(len(data['choices']) > 0): 
                        if((data['choices'][0]['delta']['content'] != None) and len(data['choices'][0]['delta']['content']) > 0):
                            if(outprint):
                                print(data['choices'][0]['delta']['content'], end='')
                            response += data['choices'][0]['delta']['content']
                        elif("reasoning_content" in data['choices'][0]['delta']):
                            if((data['choices'][0]['delta']['reasoning_content'] != None) and len(data['choices'][0]['delta']['reasoning_content']) > 0):
                                if(outprint):
                                    print(data['choices'][0]['delta']['reasoning_content'], end='')
                                response += data['choices'][0]['delta']['reasoning_content']
                elif(data['usage'] != None):
                    data_info.append(data)
                
        except Exception as e: 
            data = "error for chat api"
            response = "error for chat api"
            print(f"{response}, thie error is {e}")
        return response
    
    def chat(self, interlocution_message, model_idx=0, temperature=0.2):
        model_name = self.chat_model_list[model_idx]
        response = self.run_model_with_stream(model_name, interlocution_message, temperature)
        return response

    def reset_interlocution_message(self):
        self.interlocution_message = [
        {'role': 'system', 'content': self.system_prompt},  # 'You are a helpful assistant.'
        ]

    def set_model_idx(self, model_idx):
        self.model_idx = model_idx
    
    def run(self, text):
        self.interlocution_message.append({'role': 'user', 'content': [{'type' : 'text', 'text' : text}]})
        response = self.chat(self.interlocution_message, self.model_idx)
        self.interlocution_message.append({'role': 'assistant', 'content': response})
        return response

    

class VLAgent(Agent):
    def __init__(self, engine):
        super().__init__(engine)
        self.system_prompt = "在这个场景下，用户会输入一张图片，图片为一张文档的截图，你需要逐行的识别图片中的内容，提取图片中的目录，文本，表格等，按照原有布局，格式，以markdown格式输出。注意以下几点: \
            1.你必须保证输出的内容完整，并且不要省略任何信息。 \
            2.用户可能会按顺序给出图片路径列表，截图中会包含图片内容，你需要检查是否存在图片，表格，结构图，流程图等等图表，将这些图片，表格，结构图，流程图等图片位置替换为图片的路径。\
            3.不要被'..........'陷入迷失。\
            " 
        self.interlocution_message = [
        {'role': 'system', 'content': self.system_prompt},  # 'You are a helpful assistant.'
        ]
        self.model_id = 0

    def extract_and_replace_image_paths(self, text, placeholder_fomat ="IMAGE"):
        image_pattern = r'[^\s]+\.(?:jpg|jpeg|png|gif|bmp|tiff|webp)(?![\w\.])'
        matches = [(m.group(0), m.start(), m.end()) for m in re.finditer(image_pattern, text, re.IGNORECASE)]
        extracted_images = []
        replaced_text = text
        last_placeholder_length = 0
        last_image_path_length = 0
        for index, (path, start, end) in enumerate(matches):
            placeholder = " "
            new_start = start - (last_image_path_length - last_placeholder_length)
            new_end = end - (last_image_path_length - last_placeholder_length)
            extracted_images.append({
                'path': path,
                'start': start,
                'end': end,
                'placeholder': placeholder
            })
            replaced_text = replaced_text[:new_start] + placeholder + replaced_text[new_end:]
            last_image_path_length = end - start
            last_placeholder_length = len(placeholder)
        
        return replaced_text, extracted_images
    
    def encode_base64_content_from_file(self, image_path: str) -> str:
        """Encodes the content of a local image file to Base64."""
        try:
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
            return encoded_string
        except FileNotFoundError:
            print(f"Error: File not found at {image_path}")
            return None


    def extract_maskdown_content(self, text):
        """
        从字符串中提取所有 ```markdown ... ``` 格式的文本块。

        Args:
            text: 包含一个或多个 markdown 块的输入字符串。

        Returns:
            一个列表，其中包含所有提取到的 markdown 块的文本内容（不包括```markdown 和 ``` 标记）。
            如果没有找到匹配的块，则返回空列表。
        """
        # 定义正则表达式模式
        # ```markdown  : 匹配字面量 ```markdown 开始标记
        # (             : 开始捕获组 1 (这将是我们要提取的内容)
        # [\s\S]*?      : 匹配任何字符 (包括换行符 \s 和非换行符 \S) 零次或多次，
        #               : 非贪婪匹配 (?) 确保只匹配到最近的 ```
        # )             : 结束捕获组 1
        # ```         : 匹配字面量 ``` 结束标记
        pattern = r"```markdown([\s\S]*?)```"
        # 使用 re.findall 查找所有匹配项。
        # re.findall 当模式包含捕获组时，会返回一个列表，列表中的每个元素是每个匹配项中
        # 捕获组的内容。
        markdown_blocks = re.findall(pattern, text)

        return markdown_blocks


    def run(self, image_text, text):
        modified_text, images_info = self.extract_and_replace_image_paths(image_text)
        if(len(images_info) == 0):
            self.interlocution_message.append({'role': 'user', 'content': text})
        else:
            content_list = list()
            content_list.append( {
                            "type": "text",
                            "text": modified_text + text
                        })
            print(modified_text)
            for image_info in images_info:
                image_base64 = self.encode_base64_content_from_file(image_info['path'])
                print(image_info)
                content_list.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            },
                        })
            self.interlocution_message.append({'role': 'user', 'content': content_list})
        response = self.chat(self.interlocution_message, self.model_id)
        self.interlocution_message.append({'role': 'assistant', 'content': response})
        return response
    
    def continue_run(self, text):
        self.interlocution_message.append({'role': 'user', 'content': text})
        response = self.chat(self.interlocution_message, self.model_idx)
        self.interlocution_message.append({'role': 'assistant', 'content': response})
        return response


if __name__ == "__main__":
    vl_agent = VLAgent("QwenVLLocal")
    vl_agent.run("test.png")
