import os
from datetime import datetime
import pathlib
from pathlib import Path
from typing import Optional, List, Dict, Any
import uuid
from openai import OpenAI
import atexit
import httpx
import sys
from utils import json
from llm_utils.tools import get_default_tools, create_executors, create_all_executors, ToolExecutor
from tenacity import retry, stop_after_attempt, wait_exponential


# 创建自定义 httpx 客户端
http_client = httpx.Client(
    timeout=httpx.Timeout(
        connect=10.0,     # 建立连接超时
        read=1200.0,      # 读取响应超时（与之前一致）
        write=10.0,       # 发送请求超时
        pool=5.0          # 从连接池获取连接的超时
    ),
    limits=httpx.Limits(
        max_keepalive_connections=5,
        max_connections=10,
        keepalive_expiry=30.0   # 连接空闲 30 秒后关闭，避免服务端主动关闭
    )
)


def get_deepseek_api_key() -> Optional[str]:
    """
    获取 DeepSeek API Key，按以下顺序查找：
    1. .env 文件（在 llm_utils 目录下）
    2. 系统环境变量 DEEPSEEK_API_KEY
    
    Returns:
        API Key 字符串，如果找不到则返回 None
    """
    # 1. 先查找 .env 文件
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('DEEPSEEK_API_KEY='):
                        api_key = line.split('=', 1)[1].strip().strip('"').strip("'")
                        if api_key:
                            return api_key
        except Exception:
            pass
    
    # 2. 查找系统环境变量
    api_key = os.environ.get('DEEPSEEK_API_KEY')
    if api_key:
        return api_key
    
    return None


def check_deepseek_api_key() -> bool:
    """
    检查 DeepSeek API Key 是否已配置
    
    Returns:
        如果已配置返回 True，否则返回 False
    """
    return get_deepseek_api_key() is not None


class DeepSeekChatSession:

    def __init__(self, system_prompt, model="deepseek-reasoner", tools=None):
        """
        初始化 DeepSeek 聊天会话
        
        Args:
            system_prompt: 系统提示词
            model: 模型名称，默认为 "deepseek-reasoner"
            tools: 工具列表（可选）。如果为 None，则默认只使用 Python 工具。
                   如果为 []，则不使用任何工具。
                   如果为列表，则使用指定的工具定义（可通过 get_all_tools() 或 get_tools() 获取）。
        """
        api_key = get_deepseek_api_key()
        if not api_key:
            # 如果找不到 API key，尝试弹窗提醒（仅在 GUI 环境中）
            try:
                from tkinter import messagebox
                messagebox.showwarning(
                    "DeepSeek API Key 未配置",
                    "未找到 DeepSeek API Key。\n\n"
                    "请通过以下方式配置：\n"
                    "1. 在主界面点击 'DS API 配置' 按钮\n"
                    "2. 或创建 .env 文件并添加: DEEPSEEK_API_KEY=your_key\n"
                    "3. 或设置系统环境变量: DEEPSEEK_API_KEY=your_key\n\n"
                    "配置后请重启应用。"
                )
            except Exception:
                # 非 GUI 环境，打印警告
                print("警告: 未找到 DeepSeek API Key。请配置 DEEPSEEK_API_KEY 环境变量或创建 .env 文件。")
            raise ValueError("DeepSeek API Key 未配置")
        
        self._client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            timeout=120000,
            http_client=http_client
        )
        self.model = model
        self.system_prompt = system_prompt
        # stores conversation turns in API message format (excluding system)
        self.messages = []
        # stores raw responses for later persistence
        self.history = []
        atexit.register(self._save)
        self.recent_response = None
        
        # 工具相关初始化
        if tools is None:
            # 默认只使用 Python 工具（便于逐步扩展）
            self.tools = get_default_tools()
            self.tool_executors = create_executors()  # 默认只创建 Python 执行器
        elif isinstance(tools, list):
            # 使用指定的工具列表
            self.tools = tools
            # 根据工具列表创建对应的执行器
            tool_names = {tool["function"]["name"] for tool in tools if isinstance(tool, dict) and "function" in tool}
            # 创建所有可用执行器，然后只保留指定的
            all_executors = create_all_executors()
            self.tool_executors = {name: executor for name, executor in all_executors.items() if name in tool_names}
        else:
            self.tools = []
            self.tool_executors = {}

    def ask(self, prompt):
        # accumulate multi-turn conversation by replaying prior messages
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.messages)
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            messages=messages,
            model=self.model,
            stream=False
        )

        # update conversation state and expose latest response
        self.recent_response = response.choices[0].message.content
        self.messages.append({"role": "user", "content": prompt})
        self.messages.append({"role": "assistant", "content": self.recent_response})
        return response

    def ask_stream(self, prompt, callback=None):
        """
        流式输出方法，通过 callback 实时返回文本片段
        
        Args:
            prompt: 用户输入的 prompt
            callback: 回调函数，接收每个文本片段，签名为 callback(text: str)
        
        Returns:
            str: 完整的响应内容
        """
        # 构建消息列表
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.messages)
        messages.append({"role": "user", "content": prompt})
        
        # 流式请求
        response = self._client.chat.completions.create(
            messages=messages,
            model=self.model,
            stream=True
        )
        
        full_content = ""
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                full_content += text
                if callback:
                    callback(text)
        
        # 更新会话状态
        self.messages.append({"role": "user", "content": prompt})
        self.messages.append({"role": "assistant", "content": full_content})
        self.recent_response = full_content
        return full_content

    def work(self, fp):
        self.history.append(self.ask(fp.read()))
        return self.history[-1]

    def workp(self, path):
        with open(path) as fp:
            self.history.append(self.ask(fp.read()))
        return self.history[-1]

    def works(self, s):
        self.history.append(self.ask(s))
        return self.history[-1]
    
    def _clear_reasoning_content(self, messages):
        """
        清理消息列表中的 reasoning_content，以节省网络带宽
        
        Args:
            messages: 消息列表
        """
        for message in messages:
            if isinstance(message, dict) and "reasoning_content" in message:
                message["reasoning_content"] = None
            elif hasattr(message, "reasoning_content"):
                message.reasoning_content = None

    def _print_reasoning_content(self, reasoning_content):
        """打印思维链内容"""
        if not reasoning_content:
            return
        print("=" * 50)
        print("[思维链]")
        print(reasoning_content)

    def _print_tool_call(self, tool_name, tool_arguments, tool_result):
        """拆分打印工具调用信息，不再直接打印整个 dict"""
        print("=" * 50)
        print(f"[工具调用] {tool_name}")
        print("参数:")
        if isinstance(tool_arguments, dict):
            for key, value in tool_arguments.items():
                if isinstance(value, str) and "\n" in value:
                    print(f"  {key}:")
                    print(value)
                else:
                    print(f"  {key}: {value}")
        else:
            print(f"  {tool_arguments}")
        print("结果:")
        if isinstance(tool_result, dict):
            for key, value in tool_result.items():
                if isinstance(value, str) and "\n" in value:
                    print(f"  {key}:")
                    print(value)
                else:
                    print(f"  {key}: {value}")
        else:
            print(f"  {tool_result}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def ask_with_tools(self, prompt, tools=None):
        """
        使用工具调用功能进行对话
        
        Args:
            prompt: 用户输入的 prompt
            tools: 可选的工具列表，如果为 None 则使用 self.tools
        
        Returns:
            API 响应对象
        """
        # 使用传入的 tools 或实例的 tools
        active_tools = tools if tools is not None else self.tools
        
        # 如果没有工具，回退到普通 ask 方法
        if not active_tools:
            return self.ask(prompt)
        
        # 清理历史消息中的 reasoning_content（节省带宽）
        self._clear_reasoning_content(self.messages)
        
        # 添加用户消息
        self.messages.append({"role": "user", "content": prompt})
        
        # 记录当前 turn（用于日志）
        current_turn = len([h for h in self.history if isinstance(h, dict) and h.get("_type") == "tool_turn"]) + 1
        sub_turn = 1
        
        # 存储整个工具调用过程的记录
        turn_history = {
            "_type": "tool_turn",
            "turn": current_turn,
            "prompt": prompt,
            "sub_turns": []
        }
        
        # 多轮工具调用循环
        while True:
            # 构建消息列表（包含系统提示）
            messages = [{"role": "system", "content": self.system_prompt}]
            messages.extend(self.messages)
            
            # 调用 API
            api_kwargs = {
                "model": self.model,
                "messages": messages,
                "tools": active_tools,
                "stream": False
            }
            
            # 如果使用思考模式，添加 extra_body
            if "reasoner" in self.model.lower() or "chat" in self.model.lower():
                api_kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
            
            response = self._client.chat.completions.create(**api_kwargs)
            
            # 获取响应消息
            message = response.choices[0].message
            reasoning_content = getattr(message, "reasoning_content", None)
            content = message.content or ""
            tool_calls = message.tool_calls
            
            # 记录子轮次信息
            sub_turn_record = {
                "sub_turn": sub_turn,
                "reasoning_content": reasoning_content,
                "content": content,
                "tool_calls": []
            }
            
            # 将 assistant 消息添加到消息列表
            assistant_message = {
                "role": "assistant",
                "content": content,
            }
            if reasoning_content:
                assistant_message["reasoning_content"] = reasoning_content
            if tool_calls:
                assistant_message["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in tool_calls
                ]
            
            self.messages.append(assistant_message)
            
            # 打印思维链内容
            if reasoning_content:
                self._print_reasoning_content(reasoning_content)
            
            # 如果没有工具调用，说明已经得到最终答案，退出循环
            if not tool_calls:
                self.recent_response = content
                turn_history["final_response"] = content
                turn_history["response"] = response
                self.history.append(turn_history)
                return response
            
            # 执行工具调用
            import json as json_lib
            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                tool_arguments_str = tool_call.function.arguments
                tool_arguments = None
                
                # 解析工具参数
                try:
                    tool_arguments = json_lib.loads(tool_arguments_str)
                except Exception as e:
                    tool_result = {
                        "success": False,
                        "output": "",
                        "error": f"参数解析错误: {str(e)}",
                        "execution_time": 0.0
                    }
                    tool_result_str = json_lib.dumps(tool_result, ensure_ascii=False)
                else:
                    # 执行工具
                    executor = self.tool_executors.get(tool_name)
                    if executor:
                        tool_result = executor.execute(**tool_arguments)
                    else:
                        tool_result = {
                            "success": False,
                            "output": "",
                            "error": f"工具 '{tool_name}' 的执行器未找到",
                            "execution_time": 0.0
                        }
                    
                    # 将结果转换为字符串
                    tool_result_str = json_lib.dumps(tool_result, ensure_ascii=False)
                
                # 记录工具调用
                tool_call_record = {
                    "tool_name": tool_name,
                    "tool_arguments": tool_arguments if tool_arguments is not None else tool_arguments_str,
                    "tool_result": tool_result,
                    "execution_time": tool_result.get("execution_time", 0.0),
                    "timestamp": datetime.now().isoformat()
                }
                sub_turn_record["tool_calls"].append(tool_call_record)
                self._print_tool_call(tool_name, tool_arguments if tool_arguments is not None else tool_arguments_str, tool_result)
                
                # 将工具结果添加到消息列表
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result_str
                })
            
            turn_history["sub_turns"].append(sub_turn_record)
            sub_turn += 1
            
            # 防止无限循环（最多 20 轮）
            if sub_turn > 100:
                turn_history["warning"] = "达到最大工具调用轮次限制（100 轮）"
                turn_history["response"] = response
                self.history.append(turn_history)
                break

    def ask_json(self, prompt, max_tokens: int = 2000):
        """
        专门用于返回 JSON 格式的方法。
        使用 response_format 参数确保返回 JSON 格式，并自动清理响应中的 markdown 代码块标记。
        注意：此方法不实施多轮对话，不会修改 self.messages，但会将完整的对话记录保存到 history。
        
        Args:
            prompt: 用户输入的 prompt（必须包含 "json" 关键字）
            max_tokens: 最大 token 数，防止 JSON 被截断（默认 2000）
        
        Returns:
            str: 清理后的 JSON 字符串，如果失败返回 None
        """
        # 构建强调返回 JSON 的 prompt
        json_prompt = f"{prompt}\n\n重要提示：请只返回有效的 JSON 格式数据，不要包含任何 markdown 代码块标记（如 ```json 或 ```），也不要包含任何其他说明文字。"
        # 构建完整的消息列表（包含系统提示和历史消息）
        full_messages = [{"role": "system", "content": self.system_prompt}]
        full_messages.extend(self.messages)
        full_messages.append({"role": "user", "content": json_prompt})

        response = self._client.chat.completions.create(
            messages=full_messages,
            model=self.model,
            stream=False,
            response_format={"type": "json_object"},
            max_tokens=max_tokens
        )

        content = response.choices[0].message.content
        if not content:
            # API 可能返回空的 content
            self.recent_response = None
            # 保存完整对话记录到 history（但不修改 self.messages）
            history_item = {
                "_type": "json_call",
                "response": response,
                "prompt": prompt,  # 原始 prompt
                "json_prompt": json_prompt,  # 实际发送的 prompt
                "system_prompt": self.system_prompt,
                "messages_before": self.messages.copy(),  # 调用前的消息历史
                "assistant_content": "",
            }
            self.history.append(history_item)
            return None
        
        # 清理 markdown 代码块标记
        cleaned = content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]  # 移除 ```json
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]  # 移除 ```
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]  # 移除结尾的 ```
        cleaned = cleaned.strip()
        
        self.recent_response = cleaned
        # 保存完整对话记录到 history（但不修改 self.messages）
        history_item = {
            "_type": "json_call",
            "response": response,
            "prompt": prompt,  # 原始 prompt
            "json_prompt": json_prompt,  # 实际发送的 prompt
            "system_prompt": self.system_prompt,
            "messages_before": self.messages.copy(),  # 调用前的消息历史
            "assistant_content": content,  # 原始响应内容
            "cleaned_content": cleaned,  # 清理后的内容
        }
        self.history.append(history_item)
        return cleaned

    def _save(self, save_dir=pathlib.Path(__file__).parent / "history"):
        root = pathlib.Path(save_dir)
        os.makedirs(root, exist_ok=True)
        session_id = uuid.uuid4().hex[:6]
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        filepath = root / f"llm-chat-{timestamp}-{session_id}.json"

        turns = []
        for h in self.history:
            # 工具调用 turn
            if isinstance(h, dict) and h.get("_type") == "tool_turn":
                response = h.get("response")
                base = {
                    "type": "tool_turn",
                    "turn": h.get("turn", 0),
                    "prompt": h.get("prompt", ""),
                    "final_response": h.get("final_response", ""),
                    "sub_turns": h.get("sub_turns", []),
                    "warning": h.get("warning", ""),
                }
                if response:
                    base.update({
                        "model": response.model,
                        "id": response.id,
                        "usage": {
                            "completed": response.usage.completion_tokens,
                            "cached": response.usage.model_extra.get("prompt_cache_hit_tokens", 0),
                            "missed": response.usage.model_extra.get("prompt_cache_miss_tokens", 0),
                            "total": response.usage.total_tokens,
                        },
                        "output": response.choices[0].message.content if response.choices else "",
                        "reasoning_content": response.choices[0].message.model_extra.get('reasoning_content', '') if response.choices and response.model == 'deepseek-reasoner' else '',
                        "finish_reason": response.choices[0].finish_reason if response.choices else "",
                        "detail": response.model_dump() if response else {},
                    })
                turns.append(base)
            # ask_json 调用
            elif isinstance(h, dict) and h.get("_type") == "json_call":
                response = h["response"]
                turns.append({
                    "type": "json_call",
                    "model": response.model,
                    "id": response.id,
                    "prompt": h["prompt"],
                    "json_prompt": h["json_prompt"],
                    "system_prompt": h["system_prompt"],
                    "messages_before": h["messages_before"],
                    "usage": {
                        "completed": response.usage.completion_tokens,
                        "cached": response.usage.model_extra.get("prompt_cache_hit_tokens", 0),
                        "missed": response.usage.model_extra.get("prompt_cache_miss_tokens", 0),
                        "total": response.usage.total_tokens,
                    },
                    "output": response.choices[0].message.content,
                    "cleaned_output": h.get("cleaned_content", ""),
                    "reasoning_content": response.choices[0].message.model_extra.get('reasoning_content', '') if response.model == 'deepseek-reasoner' else '',
                    "finish_reason": response.choices[0].finish_reason,
                    "detail": response.model_dump(),
                })
            else:
                # 普通 ask / works 调用保存的 response 对象
                turns.append({
                    "type": "chat",
                    "model": h.model,
                    "id": h.id,
                    "usage": {
                        "completed": h.usage.completion_tokens,
                        "cached": h.usage.model_extra.get("prompt_cache_hit_tokens", 0),
                        "missed": h.usage.model_extra.get("prompt_cache_miss_tokens", 0),
                        "total": h.usage.total_tokens,
                    },
                    "output": h.choices[0].message.content,
                    "reasoning_content": h.choices[0].message.model_extra.get('reasoning_content', '') if h.model == 'deepseek-reasoner' else '',
                    "finish_reason": h.choices[0].finish_reason,
                    "detail": h.model_dump(),
                })

        payload = {
            "meta": {
                "model": self.model,
                "system_prompt": self.system_prompt,
                "saved_at": datetime.now().isoformat(),
                "session_id": session_id,
                "empty": (not self.messages and not self.history),
            },
            "messages": self.messages,
            "turns": turns,
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(json.dumps(payload))
            return payload
        except Exception as e:
            print(f"[DeepSeekChatSession] 保存日志失败 ({filepath}): {e}", file=sys.stderr)
            return None

