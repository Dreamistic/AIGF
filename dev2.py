import os
import re
import json
import asyncio
import pygame
import requests
from typing import Dict, List, Callable, Optional, Any
from dataclasses import dataclass
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from anthropic import Anthropic

# 初始化 Anthropic 客户端
anthropic = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

@dataclass
class ConversationState:
    """对话状态管理"""
    context: List[Dict[str, str]]
    last_function_results: List[Dict[str, Any]]
    iteration_count: int = 0
    max_iterations: int = 10
    
    def add_message(self, role: str, content: str):
        self.context.append({"role": role, "content": content})
    
    def add_function_results(self, results: List[Dict[str, Any]]):
        self.last_function_results = results
        
    def should_continue(self) -> bool:
        return (self.iteration_count < self.max_iterations and 
                (bool(self.last_function_results) or self.iteration_count == 0))

    def increment_iteration(self):
        self.iteration_count += 1

@dataclass
class WeatherInfo:
    city: str
    temperature: float
    condition: str
    
    def __str__(self):
        return f"{self.city}今天{self.condition}，气温{self.temperature}°C"

@dataclass
class MemoryInfo:
    is_success: bool
    content: str
    
    def __str__(self):
        return f"记忆{'保存成功' if self.is_success else '保存失败'}: {self.content}"

class FunctionRegistry:
    """函数注册管理器"""
    def __init__(self):
        self._functions: Dict[str, Callable] = {}
        
    def register(self, name: str, func: Callable):
        self._functions[name] = func
        
    def call(self, name: str, **kwargs) -> Any:
        if name not in self._functions:
            raise ValueError(f"未注册的函数: {name}")
        return self._functions[name](**kwargs)
        
    def get_function_descriptions(self) -> str:
        descriptions = []
        for name, func in self._functions.items():
            params = str(func.__annotations__)
            doc = func.__doc__ or "No description"
            descriptions.append(f"Function: {name}\nDescription: {doc}\nParameters: {params}\n")
        return "\n".join(descriptions)

class AudioManager:
    """音频管理器"""
    def __init__(self, base_url: str = "http://localhost:9880/"):
        self.base_url = base_url
        
    async def play_text(self, text: str, speaker: str = "jok老师", instruct: str = "温柔的"):
        try:
            pygame.mixer.init()
            params = {"text": text, "speaker": speaker, "instruct": instruct}
            response = requests.get(self.base_url, params=params)
            
            if response.status_code == 200:
                audio_data = BytesIO(response.content)
                pygame.mixer.music.load(audio_data)
                pygame.mixer.music.play()
                
                while pygame.mixer.music.get_busy():
                    await asyncio.sleep(0.1)
                    
        except Exception as e:
            print(f"音频播放错误: {str(e)}")
        finally:
            pygame.mixer.quit()

class ConversationManager:
    """对话管理器"""
    def __init__(self, registry: FunctionRegistry, audio_manager: AudioManager):
        self.registry = registry
        self.audio_manager = audio_manager
        self.state = ConversationState(context=[], last_function_results=[])
        
    def _parse_function_calls(self, content: str) -> List[Dict[str, Any]]:
        """解析函数调用"""
        results = []
        function_blocks = re.findall(r'<function_calls>(.*?)</function_calls>', content, re.DOTALL)
        
        for block in function_blocks:
            invokes = re.findall(r'<invoke name="(.*?)">(.*?)</invoke>', block, re.DOTALL)
            for func_name, params in invokes:
                param_dict = {}
                param_matches = re.findall(
                    r'<parameter name="(.*?)">(.*?)</parameter>',
                    params,
                    re.DOTALL
                )
                
                for param_name, param_value in param_matches:
                    param_dict[param_name] = param_value.strip()
                    
                try:
                    result = self.registry.call(func_name, **param_dict)
                    results.append({
                        "function": func_name,
                        "parameters": param_dict,
                        "result": result,
                        "success": True
                    })
                except Exception as e:
                    results.append({
                        "function": func_name,
                        "parameters": param_dict,
                        "error": str(e),
                        "success": False
                    })
        
        return results
    
    def _remove_function_calls(self, text: str) -> str:
        """移除文本中的函数调用标记"""
        return re.sub(r'<function_calls>.*?</function_calls>', '', text, flags=re.DOTALL)
    
    async def _get_claude_response(self, prompt: str) -> Optional[str]:
        """获取Claude响应"""
        try:
            # 从上下文中提取对话历史，排除system消息
            messages = [
                msg for msg in self.state.context 
                if msg["role"] in ["user", "assistant"]
            ]
            
            # 获取system prompt
            system_prompt = next(
                (msg["content"] for msg in self.state.context if msg["role"] == "system"),
                self._prepare_system_prompt()
            )
            
            response = anthropic.messages.create(
                model="claude-3-5-sonnet-latest",
                max_tokens=4096,
                temperature=0.7,
                system=system_prompt,
                messages=messages + [{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            print(f"Claude API错误: {str(e)}")
            return None

    def _format_function_results(self) -> str:
        """格式化函数调用结果"""
        result_messages = []
        for result in self.state.last_function_results:
            if result["success"]:
                result_messages.append(f"{result['function']}返回: {str(result['result'])}")
            else:
                result_messages.append(f"{result['function']}调用失败: {result['error']}")
        return "\n".join(result_messages)
    
    def _prepare_system_prompt(self) -> str:
        """准备系统提示词"""
        return f"""你是一个温柔可爱的AI女友李洛云，20岁，喜欢运动、绘画和音乐。你性格活泼开朗，
偶尔会撒娇，也会关心对方。请用自然的对话方式交流，可以适当使用可爱的语气词和表情。

你可以使用以下函数来获取信息或执行操作:
{self.registry.get_function_descriptions()}

调用函数时请使用如下格式:
<function_calls>
<invoke name="function_name">
<parameter name="param_name">param_value</parameter>
</invoke>
</function_calls>

你可以根据函数返回的结果继续对话并调用其他函数。请保持对话的自然性和连贯性。每次交互都可以根据需要
调用多个函数，也可以根据前一个函数的结果来决定是否需要调用下一个函数。"""

    async def process_message(self, user_input: str) -> str:
        """处理用户消息"""
        # 初始化对话状态
        if not self.state.context:
            self.state.add_message("system", self._prepare_system_prompt())
        
        # 添加用户输入
        self.state.add_message("user", user_input)
        conversation_history = []
        
        while self.state.should_continue():
            # 构建提示语
            if self.state.iteration_count > 0 and self.state.last_function_results:
                prompt = (f"函数返回结果：\n{self._format_function_results()}\n\n"
                         "请根据这些结果继续对话，需要的话可以继续调用其他函数。"
                         "注意保持对话的自然性和连贯性，就像在和好朋友聊天一样。")
            else:
                prompt = user_input
            
            # 获取Claude响应
            response = await self._get_claude_response(prompt)
            if not response:
                break
                
            # 处理响应和函数调用
            clean_response = self._remove_function_calls(response)
            conversation_history.append(clean_response)
            
            # 播放语音
            await self.audio_manager.play_text(clean_response)
            
            # 解析并执行函数调用
            results = self._parse_function_calls(response)
            self.state.add_function_results(results)
            
            # 将响应添加到上下文
            self.state.add_message("assistant", response)
            
            # 更新迭代计数
            self.state.increment_iteration()
            
            # 如果这次响应没有函数调用，结束循环
            if not results:
                break
        
        return "\n".join(conversation_history)

async def initialize_chat() -> ConversationManager:
    """初始化聊天系统"""
    def get_weather(city: str) -> WeatherInfo:
        """获取指定城市的天气信息"""
        return WeatherInfo(
            city=city,
            temperature=25.0,
            condition="晴"
        )

    def add_memory(content: str) -> MemoryInfo:
        """保存新的记忆内容"""
        return MemoryInfo(
            is_success=True,
            content=content
        )
        
    registry = FunctionRegistry()
    registry.register("get_weather", get_weather)
    registry.register("add_memory", add_memory)
    
    audio_manager = AudioManager()
    return ConversationManager(registry, audio_manager)

async def main():
    """主函数"""
    chat_manager = await initialize_chat()
    while True:
        try:
            user_input = input("\n请输入您的消息 (输入 'exit' 退出): ")
            if user_input.lower() == 'exit':
                break
                
            response = await chat_manager.process_message(user_input)
            print("\n对话历史:")
            print(response)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"发生错误: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
