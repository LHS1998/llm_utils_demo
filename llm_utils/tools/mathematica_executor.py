"""
Mathematica 代码执行器，使用 wolframclient 连接本地 Wolfram Engine
"""
import os
import time
import warnings
from typing import Dict, Any, Optional
from concurrent.futures import TimeoutError as FuturesTimeoutError

from llm_utils.tools.base import ToolExecutor

# 检查 wolframclient 是否可用
# 抑制 pkg_resources 弃用警告（来自 wolframclient 的依赖）
try:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="pkg_resources is deprecated")
        from wolframclient.evaluation import WolframLanguageSession
        from wolframclient.language import wlexpr
    WOLFRAMCLIENT_AVAILABLE = True
except ImportError:
    WOLFRAMCLIENT_AVAILABLE = False


def find_wolfram_kernel() -> Optional[str]:
    """
    查找 Wolfram Kernel 的路径
    
    按以下顺序查找：
    1. 环境变量 WOLFRAM_KERNEL_PATH
    2. 常见安装路径
    
    Returns:
        kernel 路径，如果找不到则返回 None
    """
    # 1. 检查环境变量
    env_path = os.environ.get("WOLFRAM_KERNEL_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path
    
    # 2. 常见安装路径（macOS）
    common_paths = [
        # Wolfram.app (常见的 Mathematica 安装)
        "/Applications/Wolfram.app/Contents/MacOS/WolframKernel",
        # Wolfram Engine
        "/Applications/Wolfram Engine.app/Contents/MacOS/WolframKernel",
        # Mathematica
        "/Applications/Mathematica.app/Contents/MacOS/WolframKernel",
        # Wolfram Desktop
        "/Applications/Wolfram Desktop.app/Contents/MacOS/WolframKernel",
    ]
    
    for path in common_paths:
        if os.path.isfile(path):
            return path
    
    return None


class MathematicaExecutor(ToolExecutor):
    """Mathematica 代码执行器，使用 wolframclient 连接本地 Wolfram Engine"""
    
    def __init__(self, timeout: int = 30, kernel_path: Optional[str] = None):
        """
        初始化 Mathematica 执行器
        
        Args:
            timeout: 执行超时时间（秒）
            kernel_path: Wolfram Kernel 路径（可选，默认自动查找）
        """
        super().__init__(timeout)
        self._session = None
        self._session_started = False
        self._kernel_path = kernel_path or find_wolfram_kernel()
        self._available = WOLFRAMCLIENT_AVAILABLE and self._kernel_path is not None
    
    def _get_session(self):
        """获取或创建 Wolfram 会话（延迟初始化）"""
        if not self._available:
            return None
        
        if self._session is None:
            self._session = WolframLanguageSession(kernel=self._kernel_path)
        
        if not self._session_started:
            try:
                self._session.start(block=True, timeout=self.timeout)
                self._session_started = True
            except Exception as e:
                self._available = False
                raise RuntimeError(f"无法启动 Wolfram Engine: {str(e)}")
        
        return self._session
    
    def execute(self, code: str, working_dir: Optional[str] = None,
                env_vars: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """执行 Mathematica 代码"""
        if not self._available:
            return {
                "success": False,
                "output": "",
                "error": "wolframclient 未安装或 Wolfram Engine 不可用",
                "execution_time": 0.0
            }
        
        start_time = time.time()
        
        try:
            session = self._get_session()
            
            # 使用 wlexpr 将代码字符串转换为 Wolfram 表达式并执行
            result = session.evaluate(wlexpr(code), timeout=self.timeout)
            
            execution_time = time.time() - start_time
            
            # 将结果转换为字符串
            output = str(result) if result is not None else ""
            
            return {
                "success": True,
                "output": output,
                "error": "",
                "execution_time": execution_time
            }
            
        except FuturesTimeoutError:
            execution_time = time.time() - start_time
            return {
                "success": False,
                "output": "",
                "error": f"执行超时（超过 {self.timeout} 秒）",
                "execution_time": execution_time
            }
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            
            # 检查是否是许可证问题
            if "license" in error_msg.lower() or "activate" in error_msg.lower():
                error_msg = f"Wolfram 许可证问题: {error_msg}。请先激活您的 Wolfram 产品。"
            elif "Failed to communicate" in error_msg or "Failed to start" in error_msg:
                error_msg = f"无法与 Wolfram Kernel 通信: {error_msg}。请确保 Wolfram 产品已激活且可正常运行。"
            
            # 如果会话出错，尝试重置
            if self._session is not None:
                try:
                    self._session.terminate()
                except:
                    pass
                self._session = None
                self._session_started = False
            return {
                "success": False,
                "output": "",
                "error": f"执行错误: {error_msg}",
                "execution_time": execution_time
            }
    
    def terminate(self):
        """终止 Wolfram 会话，释放资源"""
        if self._session is not None:
            try:
                self._session.terminate()
            except:
                pass
            self._session = None
            self._session_started = False
    
    def __del__(self):
        """析构时终止会话"""
        self.terminate()
    
    def is_available(self) -> bool:
        return self._available
    
    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "execute_mathematica",
                "description": "执行 Mathematica/Wolfram Language 代码并返回结果。Mathematica 是 Wolfram Research 开发的数学软件，适合符号计算、微积分、方程求解等。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "要执行的 Mathematica/Wolfram Language 代码"
                        },
                        "working_dir": {
                            "type": "string",
                            "description": "工作目录（可选，当前未使用）"
                        },
                        "env_vars": {
                            "type": "object",
                            "description": "环境变量（可选，当前未使用）"
                        }
                    },
                    "required": ["code"]
                }
            }
        }


if __name__ == '__main__':
    print("测试 MathematicaExecutor (使用 wolframclient)...")
    print("=" * 50)
    
    executor = MathematicaExecutor()
    
    # 测试可用性
    print(f"wolframclient 可用: {WOLFRAMCLIENT_AVAILABLE}")
    kernel_path = find_wolfram_kernel()
    print(f"Wolfram Kernel 路径: {kernel_path}")
    print(f"Mathematica 执行器可用: {executor.is_available()}")
    
    if not executor.is_available():
        print("\n警告: wolframclient 未安装或 Wolfram Engine 不可用")
        print("请安装:")
        print("  pip install wolframclient")
        print("  并确保本地安装了 Wolfram Engine 或 Mathematica")
        print("\n或者设置环境变量指向 WolframKernel:")
        print("  export WOLFRAM_KERNEL_PATH=/path/to/WolframKernel")
    else:
        try:
            # 测试 1: 简单计算
            print("\n测试 1: 简单计算 (1 + 2 * 3)")
            result = executor.execute("1 + 2 * 3")
            print(f"  成功: {result['success']}")
            print(f"  输出: {result['output']}")
            if result['error']:
                print(f"  错误: {result['error']}")
            print(f"  耗时: {result['execution_time']:.4f}s")
            
            # 测试 2: 符号计算
            print("\n测试 2: 符号计算 (Expand[(x+y)^3])")
            result = executor.execute("Expand[(x+y)^3]")
            print(f"  成功: {result['success']}")
            print(f"  输出: {result['output']}")
            if result['error']:
                print(f"  错误: {result['error']}")
            
            # 测试 3: 求解方程
            print("\n测试 3: 求解方程 (Solve[x^2 - 5x + 6 == 0, x])")
            result = executor.execute("Solve[x^2 - 5x + 6 == 0, x]")
            print(f"  成功: {result['success']}")
            print(f"  输出: {result['output']}")
            if result['error']:
                print(f"  错误: {result['error']}")
            
            # 测试 4: 数值计算
            print("\n测试 4: 数值计算 (N[Pi, 50])")
            result = executor.execute("N[Pi, 50]")
            print(f"  成功: {result['success']}")
            print(f"  输出: {result['output']}")
            if result['error']:
                print(f"  错误: {result['error']}")
            
            # 测试 5: 列表操作
            print("\n测试 5: 列表操作 (Range[10])")
            result = executor.execute("Range[10]")
            print(f"  成功: {result['success']}")
            print(f"  输出: {result['output']}")
            if result['error']:
                print(f"  错误: {result['error']}")
            
        finally:
            # 清理会话
            print("\n清理 Wolfram 会话...")
            executor.terminate()
            print("会话已终止")
    
    # 测试工具定义
    print("\n工具定义:")
    import json
    print(json.dumps(executor.get_tool_definition(), indent=2, ensure_ascii=False))
    
    print("\n" + "=" * 50)
    print("测试完成！")
