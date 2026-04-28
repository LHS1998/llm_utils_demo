"""
LEAN4 代码执行器，用于验证 LEAN4 证明代码
"""
import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

from llm_utils.tools.base import ToolExecutor


def get_lean4_project_dir() -> Path:
    """获取 LEAN4 项目目录"""
    return Path(__file__).parent / "lean4_project"


class Lean4Executor(ToolExecutor):
    """
    LEAN4 代码执行器
    
    用于执行 LEAN4 代码并验证证明。代码会被写入临时文件，
    然后使用 lake env lean 进行类型检查和证明验证。
    """
    
    def __init__(self, timeout: int = 120):
        """
        初始化 LEAN4 执行器
        
        Args:
            timeout: 执行超时时间（秒），默认 120 秒（LEAN 编译可能较慢）
        """
        super().__init__(timeout)
        self._project_dir = get_lean4_project_dir()
        self._scratch_dir = self._project_dir / "Scratch"
        self._lake_cmd = shutil.which("lake")
        self._elan_cmd = shutil.which("elan")
        
        # 检查环境是否可用
        self._available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """检查 LEAN4 环境是否可用"""
        # 检查 elan 或 lake 是否安装
        if not self._lake_cmd and not self._elan_cmd:
            return False
        
        # 检查项目目录是否存在
        if not self._project_dir.exists():
            return False
        
        # 检查 lakefile.toml 是否存在
        lakefile = self._project_dir / "lakefile.toml"
        if not lakefile.exists():
            return False
        
        # 检查 Scratch 目录是否存在
        if not self._scratch_dir.exists():
            try:
                self._scratch_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                return False
        
        return True
    
    def _get_lake_command(self) -> str:
        """获取 lake 命令路径"""
        if self._lake_cmd:
            return self._lake_cmd
        # 如果 lake 不在 PATH 中，尝试通过 elan 调用
        if self._elan_cmd:
            return "lake"
        return "lake"
    
    def _prepare_code(self, code: str) -> str:
        """
        准备要执行的代码
        
        如果代码没有 import 语句，添加常用的 import。
        另外，如果代码中包含 #search 命令，确保其搜索字符串以英文句号结尾。
        """
        code = code.strip()
        
        # 处理 #search 命令：若引号内字符串末尾没有英文句号，则自动追加
        def _fix_search(match: re.Match) -> str:
            content = match.group(1)
            if not content.endswith('.'):
                content += '.'
            return f'#search "{content}"'
        
        code = re.sub(r'#search\s+"([^"]+)"', _fix_search, code)
        
        # 如果代码为空，返回一个简单的检查
        if not code:
            return "-- Empty code\n#check Nat"
        
        return code
    
    def execute(self, code: str, working_dir: Optional[str] = None,
                env_vars: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        执行 LEAN4 代码
        
        Args:
            code: 要执行的 LEAN4 代码
            working_dir: 工作目录（可选，当前未使用）
            env_vars: 环境变量（可选）
        
        Returns:
            执行结果字典：
            {
                "success": bool,      # 代码是否通过类型检查/证明验证
                "output": str,        # 标准输出（#check, #eval 等的结果）
                "error": str,         # 错误信息
                "execution_time": float
            }
        """
        if not self._available:
            return {
                "success": False,
                "output": "",
                "error": self._get_unavailable_reason(),
                "execution_time": 0.0
            }
        
        start_time = time.time()
        
        # 准备代码
        prepared_code = self._prepare_code(code)
        
        # 生成唯一的临时文件名
        temp_filename = f"Temp_{uuid.uuid4().hex[:8]}.lean"
        temp_file = self._scratch_dir / temp_filename
        
        try:
            # 确保 Scratch 目录存在
            self._scratch_dir.mkdir(parents=True, exist_ok=True)
            
            # 写入临时文件
            temp_file.write_text(prepared_code, encoding='utf-8')
            
            # 准备环境变量
            env = os.environ.copy()
            if env_vars:
                env.update(env_vars)
            
            # 添加 elan 路径到 PATH
            elan_bin = Path.home() / ".elan" / "bin"
            if elan_bin.exists():
                env["PATH"] = f"{elan_bin}:{env.get('PATH', '')}"
            
            # 使用 lake env lean 执行代码
            # lake env lean 会在正确的环境中运行 lean 命令
            result = subprocess.run(
                ["lake", "env", "lean", f"Scratch/{temp_filename}"],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(self._project_dir),
                env=env
            )
            
            execution_time = time.time() - start_time
            
            # 解析输出
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            
            # 检查是否成功
            # LEAN 成功时返回码为 0，且没有错误信息
            if result.returncode == 0:
                # 检查 stderr 中是否有错误（有时警告会输出到 stderr）
                has_error = any(
                    indicator in stderr.lower() 
                    for indicator in ['error:', 'error at', 'unknown identifier', 'type mismatch']
                )
                
                if has_error:
                    return {
                        "success": False,
                        "output": stdout,
                        "error": stderr,
                        "execution_time": execution_time
                    }
                
                return {
                    "success": True,
                    "output": stdout if stdout else stderr,  # #check 等输出可能在 stderr
                    "error": "",
                    "execution_time": execution_time
                }
            else:
                # 返回码非 0，表示有错误
                error_msg = stderr if stderr else stdout
                if not error_msg:
                    error_msg = f"LEAN 退出码: {result.returncode}"
                
                return {
                    "success": False,
                    "output": stdout,
                    "error": error_msg,
                    "execution_time": execution_time
                }
                
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            return {
                "success": False,
                "output": "",
                "error": f"执行超时（超过 {self.timeout} 秒）。LEAN 证明可能过于复杂或存在无限循环。",
                "execution_time": execution_time
            }
        except FileNotFoundError as e:
            execution_time = time.time() - start_time
            return {
                "success": False,
                "output": "",
                "error": f"找不到 lake 命令。请确保已安装 LEAN4 并运行 setup_lean4.sh 脚本。",
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
            # 清理临时文件
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception:
                pass
    
    def _get_unavailable_reason(self) -> str:
        """获取不可用的原因"""
        reasons = []
        
        if not self._lake_cmd and not self._elan_cmd:
            reasons.append("elan/lake 未安装或不在 PATH 中")
        
        if not self._project_dir.exists():
            reasons.append(f"项目目录不存在: {self._project_dir}")
        elif not (self._project_dir / "lakefile.toml").exists():
            reasons.append("lakefile.toml 不存在，请运行 setup_lean4.sh 初始化项目")
        
        if reasons:
            return "LEAN4 环境不可用: " + "; ".join(reasons)
        return "LEAN4 环境不可用"
    
    def is_available(self) -> bool:
        """检查工具是否可用"""
        return self._available
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """获取工具定义（用于 DeepSeek API）"""
        return {
            "type": "function",
            "function": {
                "name": "execute_lean4",
                "description": """执行 LEAN4 代码并验证证明。LEAN4 是一个交互式定理证明器和编程语言。
                
此工具可以：
- 验证数学证明的正确性
- 检查类型是否正确
- 执行 #check, #eval 等命令查看类型和计算结果

代码会在配置了 mathlib 的环境中执行，可以使用 `import Mathlib.Tactic` 导入常用策略。

此 lean 配置了 LeanSearchClient, 可以使用 `#search` 用英文搜索定理. 可以通过 execute_script 在地址 `/Users/xi/PycharmProjects/ZhixinUtilities/llm_utils/tools/lean4_project/.lake` 中查看库文件.

示例代码：
```lean
import Mathlib.Tactic

-- 验证简单的等式
example : 1 + 1 = 2 := by norm_num

-- 证明代数等式
example (a b : ℤ) : (a + b) ^ 2 = a ^ 2 + 2 * a * b + b ^ 2 := by ring

-- 逻辑证明
example (p q : Prop) (hp : p) (hq : q) : p ∧ q := ⟨hp, hq⟩
```""",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "要执行的 LEAN4 代码。可以包含 import 语句、定义、定理和证明。"
                        }
                    },
                    "required": ["code"]
                }
            }
        }
    
    def check_and_setup(self) -> Dict[str, Any]:
        """
        检查环境并返回设置状态
        
        Returns:
            包含环境状态的字典
        """
        status = {
            "elan_installed": self._elan_cmd is not None,
            "lake_installed": self._lake_cmd is not None,
            "project_exists": self._project_dir.exists(),
            "lakefile_exists": (self._project_dir / "lakefile.toml").exists(),
            "manifest_exists": (self._project_dir / "lake-manifest.json").exists(),
            "available": self._available,
        }
        
        if self._elan_cmd:
            status["elan_path"] = self._elan_cmd
        if self._lake_cmd:
            status["lake_path"] = self._lake_cmd
        
        status["project_dir"] = str(self._project_dir)
        
        return status


if __name__ == '__main__':
    print("测试 Lean4Executor...")
    print("=" * 60)
    
    executor = Lean4Executor()
    
    # 检查环境状态
    print("\n环境状态:")
    status = executor.check_and_setup()
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    print(f"\nLEAN4 执行器可用: {executor.is_available()}")
    
    if not executor.is_available():
        print("\n警告: LEAN4 环境不可用")
        print("请运行以下命令初始化环境:")
        print(f"  bash {Path(__file__).parent / 'setup_lean4.sh'}")
    else:
        # 测试 1: 简单的证明
        print("\n测试 1: 简单证明 (1 + 1 = 2)")
        result = executor.execute("""
import Mathlib.Tactic

example : 1 + 1 = 2 := by norm_num
""")
        print(f"  成功: {result['success']}")
        print(f"  输出: {result['output']}")
        if result['error']:
            print(f"  错误: {result['error']}")
        print(f"  耗时: {result['execution_time']:.4f}s")
        
        # 测试 2: 使用 #check
        print("\n测试 2: #check 命令")
        result = executor.execute("""
#check Nat.add_comm
#check (1 : Nat)
""")
        print(f"  成功: {result['success']}")
        print(f"  输出: {result['output']}")
        if result['error']:
            print(f"  错误: {result['error']}")
        
        # 测试 3: 错误的证明
        print("\n测试 3: 错误的证明 (应该失败)")
        result = executor.execute("""
example : 1 + 1 = 3 := by norm_num
""")
        print(f"  成功: {result['success']}")
        print(f"  输出: {result['output']}")
        if result['error']:
            print(f"  错误: {result['error'][:200]}...")  # 只显示前 200 字符
        
        # 测试 4: 语法错误
        print("\n测试 4: 语法错误")
        result = executor.execute("""
example : 1 + 1 = 2 := by
""")
        print(f"  成功: {result['success']}")
        if result['error']:
            print(f"  错误: {result['error'][:200]}...")
    
    # 显示工具定义
    print("\n工具定义:")
    import json
    print(json.dumps(executor.get_tool_definition(), indent=2, ensure_ascii=False))
    
    print("\n" + "=" * 60)
    print("测试完成！")
