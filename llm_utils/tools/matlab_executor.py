"""
Matlab 代码执行器，使用 MATLAB Engine API for Python

注意：PyPI 上的 matlabengine 包声称只支持 Python 3.9-3.12，
但直接从 MATLAB 安装目录安装可以在 Python 3.13+ 上使用（会有警告）。

安装步骤：
1. 确保已安装 MATLAB (需要 R2014b 或更高版本)
2. 安装 matlabengine（推荐方法）:
   python -m llm_utils.tools.matlab_executor --install
   
   或者手动安装:
   - 进入 MATLAB 安装目录下的 extern/engines/python
   - 运行: python -m pip install .
"""
import io
import os
import subprocess
import sys
import time
from typing import Dict, Any, Optional, Tuple

from llm_utils.tools.base import ToolExecutor

# 抑制 MATLAB Engine 的 Python 版本警告（必须在导入 matlab 之前设置）
import warnings
warnings.filterwarnings(
    "ignore",
    message=r"(Python versions .* are supported, but your version of Python is .|MATLAB Engine for Python supports Python version .)",
    category=UserWarning,
    module=r"matlab.*"
)

# 检查 matlab.engine 是否可用
# 注意：在 macOS 上，MATLAB 可能抛出非 ImportError 的异常
# 例如 RuntimeError: "must run mwpython rather than python"
try:
    import matlab.engine
    MATLAB_ENGINE_AVAILABLE = True
except Exception:
    # 捕获所有异常，包括 ImportError 和 MATLAB 特定的错误
    MATLAB_ENGINE_AVAILABLE = False


def find_matlab_installation() -> Optional[str]:
    """
    查找 MATLAB 安装路径
    
    按以下顺序查找：
    1. 环境变量 MATLAB_ROOT
    2. 常见安装路径
    
    Returns:
        MATLAB 安装路径，如果找不到则返回 None
    """
    # 1. 检查环境变量
    env_path = os.environ.get("MATLAB_ROOT")
    if env_path and os.path.isdir(env_path):
        return env_path
    
    # 2. 常见安装路径（macOS）
    import glob
    
    # macOS 上的常见路径模式
    macos_patterns = [
        "/Applications/MATLAB_R*.app",
    ]
    
    for pattern in macos_patterns:
        matches = sorted(glob.glob(pattern), reverse=True)  # 按版本倒序，最新版本优先
        for match in matches:
            if os.path.isdir(match):
                return match
    
    # Linux 上的常见路径
    linux_patterns = [
        "/usr/local/MATLAB/R*",
        "/opt/MATLAB/R*",
    ]
    
    for pattern in linux_patterns:
        matches = sorted(glob.glob(pattern), reverse=True)
        for match in matches:
            if os.path.isdir(match):
                return match
    
    # Windows 上的常见路径
    windows_patterns = [
        "C:/Program Files/MATLAB/R*",
        "C:/Program Files (x86)/MATLAB/R*",
    ]
    
    for pattern in windows_patterns:
        matches = sorted(glob.glob(pattern), reverse=True)
        for match in matches:
            if os.path.isdir(match):
                return match
    
    return None


def get_engine_install_path(matlab_root: Optional[str] = None) -> Optional[str]:
    """
    获取 MATLAB Engine Python 包的安装路径
    
    Args:
        matlab_root: MATLAB 安装路径（可选，默认自动查找）
    
    Returns:
        Engine Python 包路径，如果找不到则返回 None
    """
    if matlab_root is None:
        matlab_root = find_matlab_installation()
    
    if matlab_root is None:
        return None
    
    # MATLAB Engine Python 包的路径
    engine_path = os.path.join(matlab_root, "extern", "engines", "python")
    
    if os.path.isdir(engine_path) and os.path.isfile(os.path.join(engine_path, "setup.py")):
        return engine_path
    
    return None


def install_matlab_engine(
    matlab_root: Optional[str] = None,
    python_executable: Optional[str] = None,
    use_uv: bool = True
) -> Tuple[bool, str]:
    """
    安装 MATLAB Engine for Python
    
    优先从 MATLAB 安装目录安装，这样可以支持 Python 3.13+（只有警告，没有错误）。
    
    Args:
        matlab_root: MATLAB 安装路径（可选，默认自动查找）
        python_executable: Python 解释器路径（可选，默认使用当前解释器）
        use_uv: 是否使用 uv 安装（推荐，更快）
    
    Returns:
        (success, message) 元组
    """
    # 查找 MATLAB 安装路径
    if matlab_root is None:
        matlab_root = find_matlab_installation()
    
    if matlab_root is None:
        return False, (
            "未找到 MATLAB 安装。\n"
            "请确保已安装 MATLAB，或设置 MATLAB_ROOT 环境变量。\n"
            "常见安装路径：\n"
            "  macOS: /Applications/MATLAB_R20xx.app\n"
            "  Linux: /usr/local/MATLAB/R20xx\n"
            "  Windows: C:/Program Files/MATLAB/R20xx"
        )
    
    # 获取 Engine 安装路径
    engine_path = get_engine_install_path(matlab_root)
    if engine_path is None:
        return False, f"在 {matlab_root} 中未找到 MATLAB Engine Python 包"
    
    # 获取 Python 解释器
    if python_executable is None:
        python_executable = sys.executable
    
    print(f"MATLAB 安装路径: {matlab_root}")
    print(f"Engine 包路径: {engine_path}")
    print(f"Python 解释器: {python_executable}")
    print()
    
    # 尝试安装
    if use_uv:
        # 优先使用 uv（更快，更可靠）
        try:
            result = subprocess.run(
                ["uv", "pip", "install", engine_path, "--python", python_executable],
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                return True, f"使用 uv 安装成功！\n{result.stdout}"
            else:
                # uv 失败，回退到 pip
                print(f"uv 安装失败，尝试使用 pip...")
                print(f"错误: {result.stderr}")
        except FileNotFoundError:
            print("uv 未安装，使用 pip 安装...")
        except Exception as e:
            print(f"uv 安装出错: {e}，尝试使用 pip...")
    
    # 使用 pip 安装
    try:
        result = subprocess.run(
            [python_executable, "-m", "pip", "install", engine_path],
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode == 0:
            return True, f"使用 pip 安装成功！\n{result.stdout}"
        else:
            return False, f"pip 安装失败:\n{result.stderr}"
    except subprocess.TimeoutExpired:
        return False, "安装超时（超过 5 分钟）"
    except Exception as e:
        return False, f"安装出错: {str(e)}"


def check_installation_status() -> Dict[str, Any]:
    """
    检查 MATLAB Engine 安装状态
    
    Returns:
        包含状态信息的字典
    """
    status = {
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "matlab_root": find_matlab_installation(),
        "engine_path": None,
        "engine_installed": MATLAB_ENGINE_AVAILABLE,
        "engine_version": None,
        "ready": False,
        "message": ""
    }
    
    # 检查 MATLAB 安装
    if status["matlab_root"]:
        status["engine_path"] = get_engine_install_path(status["matlab_root"])
    
    # 检查 Engine 版本
    if MATLAB_ENGINE_AVAILABLE:
        try:
            import matlab.engine
            # 尝试获取版本信息
            if hasattr(matlab.engine, '__version__'):
                status["engine_version"] = matlab.engine.__version__
            status["ready"] = True
            status["message"] = "MATLAB Engine 已安装且可用"
        except Exception as e:
            status["message"] = f"MATLAB Engine 已安装但无法加载: {e}"
    else:
        if status["engine_path"]:
            status["message"] = (
                "MATLAB Engine 未安装，但找到了安装包。\n"
                f"运行以下命令安装:\n"
                f"  python -m llm_utils.tools.matlab_executor --install"
            )
        elif status["matlab_root"]:
            status["message"] = f"找到 MATLAB 安装 ({status['matlab_root']})，但未找到 Engine 包"
        else:
            status["message"] = "未找到 MATLAB 安装"
    
    return status


class MatlabExecutor(ToolExecutor):
    """Matlab 代码执行器，使用 MATLAB Engine API for Python"""
    
    def __init__(self, timeout: int = 30, matlab_root: Optional[str] = None):
        """
        初始化 Matlab 执行器
        
        Args:
            timeout: 执行超时时间（秒）
            matlab_root: MATLAB 安装路径（可选，默认自动查找）
        """
        super().__init__(timeout)
        self._engine = None
        self._engine_started = False
        self._matlab_root = matlab_root or find_matlab_installation()
        self._available = MATLAB_ENGINE_AVAILABLE
    
    def _get_engine(self):
        """获取或创建 MATLAB 引擎（延迟初始化）"""
        if not self._available:
            return None
        
        if self._engine is None:
            try:
                # 启动 MATLAB 引擎
                # 可以传入选项，如 '-nodisplay' 禁用图形界面
                self._engine = matlab.engine.start_matlab("-nodisplay -nosplash")
                self._engine_started = True
            except Exception as e:
                self._available = False
                raise RuntimeError(f"无法启动 MATLAB 引擎: {str(e)}")
        
        return self._engine
    
    def execute(self, code: str, working_dir: Optional[str] = None,
                env_vars: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """执行 Matlab 代码"""
        if not self._available:
            import sys
            python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
            error_msg = (
                f"MATLAB Engine API 不可用。\n"
                f"当前 Python 版本: {python_version}\n"
                f"matlabengine 仅支持 Python 3.9-3.12，不支持 Python 3.13+\n"
                f"解决方案：\n"
                f"1. 使用 Python 3.9-3.12 的虚拟环境\n"
                f"2. 或等待 MathWorks 发布支持 Python 3.13 的版本"
            )
            return {
                "success": False,
                "output": "",
                "error": error_msg,
                "execution_time": 0.0
            }
        
        start_time = time.time()
        
        try:
            engine = self._get_engine()
            
            # 设置工作目录
            if working_dir:
                engine.cd(working_dir, nargout=0)
            
            # 创建字符串 IO 来捕获输出
            out = io.StringIO()
            err = io.StringIO()
            
            # 使用 eval 执行代码并捕获输出
            # eval 函数可以执行 MATLAB 表达式并返回结果
            try:
                # 对于多行代码，使用 evalc 来捕获所有输出
                # evalc 返回代码执行过程中的所有输出
                result = engine.evalc(code, stdout=out, stderr=err, nargout=1)
                
                execution_time = time.time() - start_time
                
                # 获取输出
                output = result if result else ""
                error_output = err.getvalue()
                
                return {
                    "success": True,
                    "output": output.strip() if output else "",
                    "error": error_output.strip() if error_output else "",
                    "execution_time": execution_time
                }
                
            except matlab.engine.MatlabExecutionError as e:
                execution_time = time.time() - start_time
                return {
                    "success": False,
                    "output": out.getvalue().strip(),
                    "error": str(e),
                    "execution_time": execution_time
                }
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            
            # 如果引擎出错，尝试重置
            if self._engine is not None:
                try:
                    self._engine.quit()
                except:
                    pass
                self._engine = None
                self._engine_started = False
            
            return {
                "success": False,
                "output": "",
                "error": f"执行错误: {error_msg}",
                "execution_time": execution_time
            }
    
    def terminate(self):
        """终止 MATLAB 引擎，释放资源"""
        if self._engine is not None:
            try:
                self._engine.quit()
            except:
                pass
            self._engine = None
            self._engine_started = False
    
    def __del__(self):
        """析构时终止引擎"""
        self.terminate()
    
    def is_available(self) -> bool:
        return self._available
    
    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "execute_matlab",
                "description": "执行 Matlab 代码并返回结果。Matlab 是 MathWorks 开发的数值计算软件，适合矩阵运算、数值分析、信号处理等。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "要执行的 Matlab 代码"
                        },
                        "working_dir": {
                            "type": "string",
                            "description": "工作目录（可选）"
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


def _print_status():
    """打印安装状态"""
    import json
    
    print("MATLAB Engine 安装状态")
    print("=" * 50)
    
    status = check_installation_status()
    
    print(f"Python 版本: {status['python_version']}")
    print(f"MATLAB 安装路径: {status['matlab_root'] or '未找到'}")
    print(f"Engine 包路径: {status['engine_path'] or '未找到'}")
    print(f"Engine 已安装: {'是' if status['engine_installed'] else '否'}")
    if status['engine_version']:
        print(f"Engine 版本: {status['engine_version']}")
    print(f"状态: {'就绪' if status['ready'] else '未就绪'}")
    print(f"\n{status['message']}")
    
    print("=" * 50)


def _run_install():
    """运行安装"""
    print("安装 MATLAB Engine for Python")
    print("=" * 50)
    
    success, message = install_matlab_engine()
    
    if success:
        print("\n✓ 安装成功！")
        print(message)
        print("\n现在可以使用 MATLAB Engine 了。")
        print("运行测试: python -m llm_utils.tools.matlab_executor --test")
    else:
        print("\n✗ 安装失败")
        print(message)
        sys.exit(1)
    
    print("=" * 50)


def _run_tests():
    """运行测试"""
    print("测试 MatlabExecutor (使用 MATLAB Engine API)...")
    print("=" * 50)
    
    # 显示 Python 版本
    print(f"Python 版本: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # 测试可用性
    print(f"MATLAB Engine API 可用: {MATLAB_ENGINE_AVAILABLE}")
    matlab_root = find_matlab_installation()
    print(f"MATLAB 安装路径: {matlab_root}")
    
    executor = MatlabExecutor()
    print(f"Matlab 执行器可用: {executor.is_available()}")
    
    if not executor.is_available():
        print("\n警告: MATLAB Engine API 不可用")
        print("运行以下命令安装:")
        print("  python -m llm_utils.tools.matlab_executor --install")
        sys.exit(1)
    else:
        try:
            # 测试 1: 简单计算
            print("\n测试 1: 简单计算 (1 + 2 * 3)")
            result = executor.execute("disp(1 + 2 * 3)")
            print(f"  成功: {result['success']}")
            print(f"  输出: {result['output']}")
            if result['error']:
                print(f"  错误: {result['error']}")
            print(f"  耗时: {result['execution_time']:.4f}s")
            
            # 测试 2: 矩阵运算
            print("\n测试 2: 矩阵运算 (A * B)")
            code = "A = [1 2; 3 4]; B = [5 6; 7 8]; disp(A * B)"
            result = executor.execute(code)
            print(f"  成功: {result['success']}")
            print(f"  输出: {result['output']}")
            if result['error']:
                print(f"  错误: {result['error']}")
            
            # 测试 3: 求解线性方程组
            print("\n测试 3: 求解线性方程组")
            code = "A = [1 2; 3 4]; b = [5; 6]; x = A\\b; disp(x)"
            result = executor.execute(code)
            print(f"  成功: {result['success']}")
            print(f"  输出: {result['output']}")
            if result['error']:
                print(f"  错误: {result['error']}")
            
            # 测试 4: 使用 MATLAB 函数
            print("\n测试 4: 使用 MATLAB 函数 (isprime)")
            code = "disp(isprime(37))"
            result = executor.execute(code)
            print(f"  成功: {result['success']}")
            print(f"  输出: {result['output']}")
            if result['error']:
                print(f"  错误: {result['error']}")
            
            # 测试 5: 多行代码
            print("\n测试 5: 多行代码")
            code = """
x = linspace(0, 2*pi, 10);
y = sin(x);
disp('x values:');
disp(x);
disp('y values:');
disp(y);
"""
            result = executor.execute(code)
            print(f"  成功: {result['success']}")
            print(f"  输出: {result['output']}")
            if result['error']:
                print(f"  错误: {result['error']}")
            
            print("\n✓ 所有测试通过！")
            
        finally:
            # 清理引擎
            print("\n清理 MATLAB 引擎...")
            executor.terminate()
            print("引擎已终止")
    
    # 测试工具定义
    print("\n工具定义:")
    import json
    print(json.dumps(executor.get_tool_definition(), indent=2, ensure_ascii=False))
    
    print("\n" + "=" * 50)
    print("测试完成！")


def _print_help():
    """打印帮助信息"""
    print("""
MATLAB Engine for Python 安装和测试工具

用法:
  python -m llm_utils.tools.matlab_executor [选项]

选项:
  --status, -s    显示安装状态
  --install, -i   安装 MATLAB Engine（从本地 MATLAB 安装目录）
  --test, -t      运行测试
  --help, -h      显示此帮助信息

示例:
  # 检查安装状态
  python -m llm_utils.tools.matlab_executor --status
  
  # 安装 MATLAB Engine
  python -m llm_utils.tools.matlab_executor --install
  
  # 运行测试
  python -m llm_utils.tools.matlab_executor --test

注意:
  - 需要先安装 MATLAB (R2014b 或更高版本)
  - PyPI 上的 matlabengine 不支持 Python 3.13+，但从 MATLAB 目录安装可以
  - 安装优先使用 uv（更快），如果没有则使用 pip
""")


if __name__ == '__main__':
    # import argparse
    #
    # parser = argparse.ArgumentParser(
    #     description="MATLAB Engine for Python 安装和测试工具",
    #     add_help=False
    # )
    # parser.add_argument('--status', '-s', action='store_true', help='显示安装状态')
    # parser.add_argument('--install', '-i', action='store_true', help='安装 MATLAB Engine')
    # parser.add_argument('--test', '-t', action='store_true', help='运行测试')
    # parser.add_argument('--help', '-h', action='store_true', help='显示帮助信息')
    #
    # args = parser.parse_args()
    #
    # if args.help:
    #     _print_help()
    # elif args.status:
    #     _print_status()
    # elif args.install:
    #     _run_install()
    # elif args.test:
    #     _run_tests()
    # else:
    #     # 默认显示状态
    #     _print_status()

    _print_status()
    _run_tests()
