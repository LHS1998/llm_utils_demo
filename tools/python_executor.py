"""
Python 代码执行器，调用项目自带的 Python interpreter 执行代码
"""
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

from llm_utils.tools.base import ToolExecutor


def get_project_python() -> str:
    """
    获取项目使用的 Python 解释器路径

    优先使用绝对路径，如果不存在则尝试相对路径。

    Returns:
        Python 解释器路径
    """
    abs_path = "/Users/xi/PycharmProjects/ZhixinUtilities/.venv/bin/python3.13"
    rel_path = Path(__file__).resolve().parent.parent / ".venv" / "bin" / "python3.13"

    if os.path.isfile(abs_path):
        return abs_path
    if rel_path.exists():
        return str(rel_path)

    # 兜底：尝试系统中的 python3.13 或 python3
    for fallback in ["python3.13", "python3", "python"]:
        path = shutil.which(fallback)
        if path:
            return path

    return "python3"


class PythonExecutor(ToolExecutor):
    """Python 代码执行器，调用项目自带的 Python interpreter 执行代码"""

    def __init__(self, timeout: int = 30, python_path: Optional[str] = None):
        super().__init__(timeout)
        self._python_path = python_path or get_project_python()
        self._available = (
            os.path.isfile(self._python_path)
            or shutil.which(self._python_path) is not None
        )

    def execute(self, code: str, working_dir: Optional[str] = None,
                env_vars: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """执行 Python 代码"""
        start_time = time.time()

        # 确定工作目录
        if working_dir:
            work_dir = Path(working_dir)
        else:
            work_dir = Path.cwd()

        if not work_dir.exists():
            return {
                "success": False,
                "output": "",
                "error": f"工作目录不存在: {work_dir}",
                "execution_time": time.time() - start_time
            }

        # 准备环境变量
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)

        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.py', delete=False, encoding='utf-8'
            ) as f:
                f.write(code)
                temp_file = f.name

            result = subprocess.run(
                [self._python_path, temp_file],
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
        except FileNotFoundError:
            execution_time = time.time() - start_time
            return {
                "success": False,
                "output": "",
                "error": f"Python 解释器未找到: {self._python_path}",
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
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception:
                    pass

    def is_available(self) -> bool:
        return self._available

    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "execute_python",
                "description": "执行 Python 代码并返回结果。使用项目自带的 Python interpreter 运行代码。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "要执行的 Python 代码"
                        },
                        "working_dir": {
                            "type": "string",
                            "description": "工作目录（可选，默认为当前目录）"
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


class PipInstallExecutor(ToolExecutor):
    """Python 第三方库安装工具，使用 pip 安装所需的库"""

    def __init__(self, timeout: int = 300, python_path: Optional[str] = None):
        super().__init__(timeout)
        self._python_path = python_path or get_project_python()
        self._available = (
            os.path.isfile(self._python_path)
            or shutil.which(self._python_path) is not None
        )

    def _parse_packages(self, code: str) -> List[str]:
        """从输入字符串解析包名列表"""
        packages = []
        try:
            parsed = json.loads(code)
            if isinstance(parsed, list):
                packages = [str(p).strip() for p in parsed if str(p).strip()]
            else:
                packages = [str(parsed).strip()]
        except json.JSONDecodeError:
            packages = [
                p.strip() for p in code.replace(',', '\n').split('\n') if p.strip()
            ]
        return packages

    def _confirm_install(self, packages: List[str]) -> bool:
        """请求用户确认安装"""
        print("\n" + "=" * 60)
        print("📦 安装第三方库确认")
        print("=" * 60)
        print("即将安装以下 Python 包:")
        for pkg in packages:
            print(f"  - {pkg}")
        print("=" * 60)

        while True:
            response = input("是否继续安装? [y/n]: ").strip().lower()
            if response in ('y', 'yes', '是'):
                return True
            elif response in ('n', 'no', '否'):
                print("❌ 已取消安装")
                return False
            else:
                print("请输入 'y' 或 'n'")

    def execute(self, packages: Optional[List[str]] = None,
                working_dir: Optional[str] = None,
                env_vars: Optional[Dict[str, str]] = None,
                code: Optional[str] = None) -> Dict[str, Any]:
        """
        安装 Python 第三方库

        Args:
            packages: 要安装的包名列表
            working_dir: 工作目录（可选）
            env_vars: 环境变量（可选）
            code: 兼容字段，当 packages 为空时尝试解析为包名
        """
        start_time = time.time()

        target_packages = packages
        if target_packages is None and code:
            target_packages = self._parse_packages(code)

        if not target_packages:
            return {
                "success": False,
                "output": "",
                "error": "未指定要安装的包",
                "execution_time": 0.0
            }

        # 去重并保持顺序
        seen = set()
        unique_packages = []
        for pkg in target_packages:
            if pkg not in seen:
                seen.add(pkg)
                unique_packages.append(pkg)

        # 请求用户确认
        if not self._confirm_install(unique_packages):
            return {
                "success": False,
                "output": "",
                "error": "用户取消安装",
                "execution_time": time.time() - start_time
            }

        # 确定工作目录
        work_dir = Path(working_dir) if working_dir else Path.cwd()

        # 准备环境变量
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)

        try:
            print(f"\n▶️  正在安装: {', '.join(unique_packages)}...")

            cmd = [self._python_path, "-m", "pip", "install"] + unique_packages
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(work_dir),
                env=env
            )

            execution_time = time.time() - start_time

            if result.returncode == 0:
                print(f"✅ 安装完成 (耗时: {execution_time:.2f}s)")
                return {
                    "success": True,
                    "output": result.stdout.strip(),
                    "error": result.stderr.strip() if result.stderr else "",
                    "execution_time": execution_time
                }
            else:
                print(f"❌ 安装失败 (退出码: {result.returncode})")
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
                "error": f"安装超时（超过 {self.timeout} 秒）",
                "execution_time": execution_time
            }
        except FileNotFoundError:
            execution_time = time.time() - start_time
            return {
                "success": False,
                "output": "",
                "error": f"Python 解释器未找到: {self._python_path}",
                "execution_time": execution_time
            }
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "success": False,
                "output": "",
                "error": f"安装错误: {str(e)}",
                "execution_time": execution_time
            }

    def is_available(self) -> bool:
        return self._available

    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "install_python_packages",
                "description": "安装 Python 第三方库。安装前会展示需安装的库并征求用户同意。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "packages": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "要安装的包名列表，如 [\"requests\", \"numpy\"]"
                        }
                    },
                    "required": ["packages"]
                }
            }
        }


if __name__ == '__main__':
    print("测试 PythonExecutor...")
    print("=" * 50)

    executor = PythonExecutor()

    # 测试可用性
    print(f"Python 解释器路径: {get_project_python()}")
    print(f"Python 执行器可用: {executor.is_available()}")

    if not executor.is_available():
        print("警告: Python 解释器不可用，无法执行测试")
    else:
        # 测试 1: 简单计算
        print("\n测试 1: 简单计算 (1 + 2 * 3)")
        result = executor.execute("print(1 + 2 * 3)")
        print(f"  成功: {result['success']}")
        print(f"  输出: {result['output']}")
        if result['error']:
            print(f"  错误: {result['error']}")
        print(f"  耗时: {result['execution_time']:.4f}s")

        # 测试 2: 多行代码
        print("\n测试 2: 多行代码")
        code = """
x = 10
y = 20
print(f"x + y = {x + y}")
"""
        result = executor.execute(code)
        print(f"  成功: {result['success']}")
        print(f"  输出: {result['output']}")
        if result['error']:
            print(f"  错误: {result['error']}")

        # 测试 3: 语法错误
        print("\n测试 3: 语法错误")
        result = executor.execute("print(")
        print(f"  成功: {result['success']}")
        print(f"  错误: {result['error']}")

        # 测试 4: 运行时错误
        print("\n测试 4: 运行时错误 (除零)")
        result = executor.execute("print(1/0)")
        print(f"  成功: {result['success']}")
        print(f"  错误: {result['error']}")

        # 测试 5: 多次打印
        print("\n测试 5: 多次打印")
        code = """
for i in range(5):
    print(i)
"""
        result = executor.execute(code)
        print(f"  成功: {result['success']}")
        print(f"  输出: {repr(result['output'])}")
        if result['error']:
            print(f"  错误: {result['error']}")

    # 测试工具定义
    print("\n工具定义:")
    import json
    print(json.dumps(executor.get_tool_definition(), indent=2, ensure_ascii=False))

    # 测试 PipInstallExecutor
    print("\n" + "=" * 50)
    print("测试 PipInstallExecutor...")
    print("=" * 50)

    pip_executor = PipInstallExecutor()
    print(f"Pip 安装工具可用: {pip_executor.is_available()}")
    print("\n工具定义:")
    print(json.dumps(pip_executor.get_tool_definition(), indent=2, ensure_ascii=False))

    print("\n" + "=" * 50)
    print("测试完成！")
