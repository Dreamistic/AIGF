import re
import requests
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Dict, List, Callable, Tuple
from dataclasses import dataclass
from mistralai import Mistral
import time
from asyncio import Semaphore
from anthropic import Anthropic

client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

context = []

#宏量
MAX_DEPTH = 5
FUNCTION_SUCCESS = "函数调用成功"

@dataclass
class WeatherInfo:
    city: str
    temperature: float
    condition: str

@dataclass
class MemoryInfo:
    is_success: bool

class FunctionRegistry:
    """函数注册器，用于管理可调用的函数"""
    def __init__(self):
        self._functions: Dict[str, Callable] = {}
        self._descriptions: Dict[str, dict] = {}  # 存储函数的详细描述
    
    def register(self, name: str, func: Callable, description: str = None, parameters: Dict[str, dict] = None):
        """注册函数，同时记录其描述和参数信息"""
        self._functions[name] = func
        self._descriptions[name] = {
            "description": description or func.__doc__ or "No description available",
            "parameters": parameters or {}
        }
    
    def call(self, name: str, **kwargs):
        """调用已注册的函数"""
        if name not in self._functions:
            raise ValueError(f"Function '{name}' not found in registry")
        return self._functions[name](**kwargs)
    
    def generate_xml(self) -> str:
        """生成XML格式的函数描述"""
        xml_parts = []
        
        for name, info in self._descriptions.items():
            function_xml = [f'      <function name="{name}">']
            function_xml.append(f'        <description>{info["description"]}</description>')
            
            if info["parameters"]:
                for param_name, param_info in info["parameters"].items():
                    param_xml = [f'          <parameter name="{param_name}" type="{param_info["type"]}">']
                    param_xml.append(f'            <description>{param_info["description"]}</description>')
                    
                    if "options" in param_info:
                        param_xml.append('            <options>')
                        for option in param_info["options"]:
                            option_xml = [f'              <option value="{option["value"]}">']
                            option_xml.append(f'                <description>{option["description"]}</description>')
                            if "usage" in option:
                                option_xml.append(f'                <usage>{option["usage"]}</usage>')
                            option_xml.append('              </option>')
                        param_xml.append('\n'.join(option_xml))
                        param_xml.append('            </options>')
                    
                    param_xml.append('          </parameter>')
                    function_xml.append('\n'.join(param_xml))
            
            function_xml.append('      </function>')
            xml_parts.append('\n'.join(function_xml))
        
        return '\n'.join(xml_parts)
    def update_system_prompt(self, system_prompt: str) -> str:
        """更新system_prompt中的functions部分"""
        import re
        
        # 生成新的functions内容
        new_functions = self.generate_xml()
        #print(new_functions)
        updated_prompt = re.sub(r'<function_system>.*?</function_system>', f"""<function_system>\n      <rule>请在请求函数调用后立即停止回复，等待函数调用</rule>\n{new_functions}\n    <function_rules>
      <rule>使用XML格式调用函数</rule>
      <rule>调用前告知用户</rule>
      <rule>等待函数响应后继续</rule>
      <example>
        <function_calls>
          <invoke name="function_name">
            <parameter name="param_name">param_value</parameter>
          </invoke>
        </function_calls>
      </example>
    </function_rules>\n</function_system>""", system_prompt, flags=re.DOTALL)
    #    return new_functions
        current_time = time.strftime("%Y-%m-%d %H:%M")
        updated_prompt = re.sub(r'<current_time>.*?</current_time>', f'<current_time>{current_time}</current_time>', updated_prompt, flags=re.DOTALL)
        return updated_prompt
    
def parse_and_execute_function_calls(xml_content: str, registry: FunctionRegistry) -> List[Dict]:
    """解析XML格式的function calls并执行函数"""
    results = []
    
    function_blocks = re.findall(
        r'<function_calls>(.*?)</function_calls>',
        xml_content,
        re.DOTALL
    )
    
    for block in function_blocks:
        invokes = re.findall(
            r'<invoke name="(.*?)">(.*?)</invoke>',
            block,
            re.DOTALL
        )
        
        for func_name, params in invokes:
            parameters = {}
            param_matches = re.findall(
                r'<parameter name="(.*?)">(.*?)</parameter>',
                params,
                re.DOTALL
            )
            
            for param_name, param_value in param_matches:
                parameters[param_name] = param_value.strip()
            
            try:
                result = registry.call(func_name, **parameters)
                results.append({
                    "function": func_name,
                    "parameters": parameters,
                    "result": result
                })
            except Exception as e:
                results.append({
                    "function": func_name,
                    "parameters": parameters,
                    "error": str(e)
                })
    
    return results

def remove_function_calls(text):
    """删除文本中的function_calls部分"""
    pattern = r'<function_calls>.*?</function_calls>'
    result = re.sub(pattern, '', text, flags=re.DOTALL)
    return result


def get_ai_response(system_prompt: str) -> Tuple[str, bool]:
    """获取AI响应，返回响应内容和是否包含函数调用"""

    response = client.messages.create(
        model="claude-3-5-sonnet-latest",
        system=system_prompt,
        messages=context,
        max_tokens=4086,
        temperature=0.7,
    )

    #content = response.content
    content = response.content[0].text
    has_function_calls = '<function_calls>' in content
    
    #调试部分

    context.append({"role": "assistant", "content": content})
    return content, has_function_calls
def process_conversation_turn(
    system_prompt: str,
    registry: FunctionRegistry,
    depth: int = 0
) -> str:
    if depth >= MAX_DEPTH:
        return "DepthError:达到最大对话深度限制。"
        
    response_content, has_function_calls = get_ai_response(system_prompt)
    print(f"depth{depth}: {response_content}\nhas_function_call:{has_function_calls}\n")
    # 如果没有函数调用，直接返回响应内容
    if has_function_calls:

        print("开始处理函数调用\n")    
        # 处理函数调用
        results = parse_and_execute_function_calls(response_content, registry)
        print(results)
        if results:
            function_responses = []
            for result in results:
                if "error" in result:
                    function_responses.append(f"调用失败: {result['error']}")
                else:
                    function_responses.append(str(result["result"]))
            
            # 更新对话上下文
            context.extend([
                {"role": "assistant", "content": f"<function_response>{function_responses}</function_response>"}
            ])
            print(f"Context: {context}\n")
            # 继续对话并返回结果
            return process_conversation_turn(
                system_prompt,
                registry,
                depth + 1
            )
    
    return response_content
 

def read_system_prompt():
    try:
        with open('system_prompt.xml', 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        print(f"读取system_prompt.xml时出错: {str(e)}")
        return None


def create_memory(content: str, priority: str):
    """创建新的记忆"""
    print(f"创建新的记忆：{content}，优先级：{priority}")
    return FUNCTION_SUCCESS

def delete_memory(content: str, reason: str):
    """删除记忆"""
    print(f"删除记忆：{content},原因:{reason}")

def run_conversation(system_prompt: str):
    """运行对话"""
    #
    update_prompt = registry.update_system_prompt(system_prompt)
    #print(update_prompt)
    try:
        output_content = process_conversation_turn(update_prompt, registry, 0)
        return output_content
    except Exception as e:
        return f"Error during chat: {str(e)}"

if __name__ == "__main__":
    #读入system_prompt
    system_prompt = read_system_prompt()
    #print(system_prompt)
    # 创建注册器
    registry = FunctionRegistry()

    # 注册create_memory函数
    registry.register(
        "create_memory",
        create_memory,  
        "创建新的记忆",
        {
            "content": {
                "type": "string",
                "description": "要存储的内容"
            },
            "priority": {
                "type": "string",
                "description": "记忆优先级：core/long/short",
                "options": [
                    {
                        "value": "core",
                        "description": "核心记忆，永久保存",
                        "usage": "重要约定、关键事件、深度交流"
                    },
                    {
                        "value": "long",
                        "description": "长期记忆",
                        "usage": "日常互动、习惯偏好"
                    },
                    {
                        "value": "short",
                        "description": "短期记忆",
                        "usage": "一般对话、临时信息"
                    }
                ]
            }
        }
    )
    # 注册delete_memory函数
    registry.register(
        "delete_memory",
        delete_memory,  
        "删除记忆",
        {
            "content": {
                "type": "string",
                "description": "要删除的内容"
            },
            "reason": {
                "type": "string",
                "description": "删除原因"
            }
        }
    )
    
    while True:
        input_text = input("请输入你的对话内容：")
        if input_text.lower() == "exit":
            break
        if input_text.lower() == "clear":
            context.clear()
            continue
        if input_text.lower() == "show":
            print(context)
            continue
        context.append({"role": "user", "content": input_text})
        response = run_conversation(system_prompt)
        print(response)
