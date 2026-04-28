"""
SageMath 代码执行器
"""
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional

from llm_utils.tools.base import ToolExecutor


class SageMathExecutor(ToolExecutor):
    """SageMath 代码执行器"""
    
    def __init__(self, timeout: int = 30):
        super().__init__(timeout)
        self._sage_cmd = shutil.which("sage")
        self._available = self._sage_cmd is not None
    
    def execute(self, code: str, working_dir: Optional[str] = None,
                env_vars: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """执行 SageMath 代码"""
        if not self._available:
            return {
                "success": False,
                "output": "",
                "error": "SageMath 未安装或不在 PATH 中",
                "execution_time": 0.0
            }
        
        start_time = time.time()
        
        # 创建临时工作目录
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(working_dir) if working_dir else Path(tmpdir)
            work_dir.mkdir(parents=True, exist_ok=True)
            
            # 准备环境变量
            env = os.environ.copy()
            if env_vars:
                env.update(env_vars)
            
            try:
                # 使用 sage -c 执行代码
                result = subprocess.run(
                    [self._sage_cmd, "-c", code],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=str(work_dir),
                    env=env
                )
                
                execution_time = time.time() - start_time
                
                if result.returncode == 0:
                    return {
                        "success": True,
                        "output": result.stdout.strip(),
                        "error": result.stderr.strip() if result.stderr else "",
                        "execution_time": execution_time
                    }
                else:
                    return {
                        "success": False,
                        "output": result.stdout.strip(),
                        "error": result.stderr.strip() or f"退出码: {result.returncode}",
                        "execution_time": execution_time
                    }
                    
            except subprocess.TimeoutExpired:
                execution_time = time.time() - start_time
                return {
                    "success": False,
                    "output": "",
                    "error": f"执行超时（超过 {self.timeout} 秒）",
                    "execution_time": execution_time
                }
            except Exception as e:
                execution_time = time.time() - start_time
                return {
                    "success": False,
                    "output": "",
                    "error": f"执行错误: {str(e)}",
                    "execution_time": execution_time
                }
    
    def is_available(self) -> bool:
        return self._available
    
    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "execute_sagemath",
                "description": "执行 SageMath 代码并返回结果。SageMath 是一个开源的数学软件系统。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "要执行的 SageMath 代码"
                        },
                        "working_dir": {
                            "type": "string",
                            "description": "工作目录（可选）"
                        },
                        "env_vars": {
                            "type": "object",
                            "description": "环境变量（可选）"
                        }
                    },
                    "required": ["code"]
                }
            }
        }


if __name__ == '__main__':
    print("测试 SageMathExecutor...")
    print("=" * 50)
    
    executor = SageMathExecutor()
    
    # 测试可用性
    print(f"SageMath 可用: {executor.is_available()}")
    if executor._sage_cmd:
        print(f"SageMath 路径: {executor._sage_cmd}")
    
    if not executor.is_available():
        print("警告: SageMath 未安装或不在 PATH 中")
        print("请安装 SageMath: https://www.sagemath.org/")
    else:
        # 测试 1: 简单计算
        print("\n测试 1: 简单计算 (factor(100))")
        result = executor.execute("print(factor(100))")
        print(f"  成功: {result['success']}")
        print(f"  输出: {result['output']}")
        print(f"  耗时: {result['execution_time']:.4f}s")
        
        # 测试 2: 符号计算
        print("\n测试 2: 符号计算 (expand((x+y)^3))")
        result = executor.execute("var('x y'); print(expand((x+y)^3))")
        print(f"  成功: {result['success']}")
        print(f"  输出: {result['output']}")
        
        # 测试 3: 数论
        print("\n测试 3: 数论 (is_prime(97))")
        result = executor.execute("print(is_prime(97))")
        print(f"  成功: {result['success']}")
        print(f"  输出: {result['output']}")
    
    # 测试工具定义
    print("\n工具定义:")
    import json
    print(json.dumps(executor.get_tool_definition(), indent=2, ensure_ascii=False))
    
    print("\n" + "=" * 50)
    print("测试完成！")
