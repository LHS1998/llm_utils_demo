"""
工具执行器模块，支持 Python、SageMath、Mathematica、Matlab、LEAN4 等计算工具。

使用示例:
    # 获取默认工具（仅 Python）
    from llm_utils.tools import get_default_tools
    tools = get_default_tools()
    
    # 获取所有可用工具
    from llm_utils.tools import get_all_tools
    tools = get_all_tools()
    
    # 获取指定工具
    from llm_utils.tools import get_tools, PYTHON, SAGEMATH, LEAN4
    tools = get_tools(PYTHON, SAGEMATH)
    
    # 创建执行器
    from llm_utils.tools import create_executors
    executors = create_executors()  # 默认只创建 Python 执行器
    executors = create_executors(PYTHON, SAGEMATH)  # 创建指定执行器
    executors = create_executors(LEAN4)  # 创建 LEAN4 执行器用于证明验证
"""
from typing import Dict, Any, List

from llm_utils.tools.base import ToolExecutor
from llm_utils.tools.python_executor import PythonExecutor, PipInstallExecutor
from llm_utils.tools.sagemath_executor import SageMathExecutor
from llm_utils.tools.mathematica_executor import MathematicaExecutor
from llm_utils.tools.matlab_executor import MatlabExecutor
from llm_utils.tools.script_executor import ScriptExecutor
from llm_utils.tools.lean4_executor import Lean4Executor
from llm_utils.tools.lean4_toolkit import (
    Lean4SorryAnalyzer,
    Lean4SearchMathlib,
    Lean4CheckAxioms,
    Lean4ParseErrors,
    Lean4SolverCascade,
    Lean4TryExact,
    Lean4MinimizeImports,
)
from llm_utils.tools.ask_user import AskUserExecutor


# 工具名称常量
PYTHON = "execute_python"
SAGEMATH = "execute_sagemath"
MATHEMATICA = "execute_mathematica"
MATLAB = "execute_matlab"
SCRIPT = "execute_script"
LEAN4 = "execute_lean4"
LEAN4_SORRY_ANALYZER = "analyze_sorries"
LEAN4_SEARCH_MATHLIB = "search_mathlib"
LEAN4_CHECK_AXIOMS = "check_axioms"
LEAN4_PARSE_ERRORS = "parse_lean_errors"
LEAN4_SOLVER_CASCADE = "solver_cascade"
LEAN4_TRY_EXACT = "try_exact_at_step"
LEAN4_MINIMIZE_IMPORTS = "minimize_imports"
ASK_USER = "ask_user"
INSTALL_PYTHON_PACKAGES = "install_python_packages"

# 工具名称到执行器类的映射
TOOL_EXECUTOR_MAP = {
    PYTHON: PythonExecutor,
    SAGEMATH: SageMathExecutor,
    MATHEMATICA: MathematicaExecutor,
    MATLAB: MatlabExecutor,
    SCRIPT: ScriptExecutor,
    LEAN4: Lean4Executor,
    LEAN4_SORRY_ANALYZER: Lean4SorryAnalyzer,
    LEAN4_SEARCH_MATHLIB: Lean4SearchMathlib,
    LEAN4_CHECK_AXIOMS: Lean4CheckAxioms,
    LEAN4_PARSE_ERRORS: Lean4ParseErrors,
    LEAN4_SOLVER_CASCADE: Lean4SolverCascade,
    LEAN4_TRY_EXACT: Lean4TryExact,
    LEAN4_MINIMIZE_IMPORTS: Lean4MinimizeImports,
    ASK_USER: AskUserExecutor,
    INSTALL_PYTHON_PACKAGES: PipInstallExecutor,
}

# 简短名称到完整名称的映射（方便使用）
TOOL_NAME_ALIASES = {
    "python": PYTHON,
    "py": PYTHON,
    "sagemath": SAGEMATH,
    "sage": SAGEMATH,
    "mathematica": MATHEMATICA,
    "wolfram": MATHEMATICA,
    "matlab": MATLAB,
    "script": SCRIPT,
    "sh": SCRIPT,
    "shell": SCRIPT,
    "lean4": LEAN4,
    "lean": LEAN4,
    "analyze_sorries": LEAN4_SORRY_ANALYZER,
    "search_mathlib": LEAN4_SEARCH_MATHLIB,
    "check_axioms": LEAN4_CHECK_AXIOMS,
    "parse_lean_errors": LEAN4_PARSE_ERRORS,
    "solver_cascade": LEAN4_SOLVER_CASCADE,
    "try_exact_at_step": LEAN4_TRY_EXACT,
    "minimize_imports": LEAN4_MINIMIZE_IMPORTS,
    "ask_user": ASK_USER,
    "ask": ASK_USER,
    "install_python_packages": INSTALL_PYTHON_PACKAGES,
    "pip": INSTALL_PYTHON_PACKAGES,
}


def _resolve_tool_name(name: str) -> str:
    """将工具名称（包括别名）解析为完整的工具名称"""
    name_lower = name.lower()
    if name_lower in TOOL_NAME_ALIASES:
        return TOOL_NAME_ALIASES[name_lower]
    if name in TOOL_EXECUTOR_MAP:
        return name
    raise ValueError(f"未知的工具名称: {name}")


def get_default_tools() -> List[Dict[str, Any]]:
    """
    获取默认工具列表（仅 Python）
    
    Returns:
        工具定义列表
    """
    executor = PythonExecutor()
    if executor.is_available():
        return [executor.get_tool_definition()]
    return []


def get_all_tools() -> List[Dict[str, Any]]:
    """
    获取所有可用工具的列表
    
    Returns:
        工具定义列表
    """
    tools = []
    for executor_class in TOOL_EXECUTOR_MAP.values():
        executor = executor_class()
        if executor.is_available():
            tools.append(executor.get_tool_definition())
    return tools


def get_tools(*tool_names: str) -> List[Dict[str, Any]]:
    """
    获取指定工具的定义列表
    
    Args:
        *tool_names: 工具名称（支持别名，如 "python", "sage", "mathematica", "matlab"）
    
    Returns:
        工具定义列表
    
    Example:
        tools = get_tools("python", "sagemath")
        tools = get_tools(PYTHON, SAGEMATH)
    """
    tools = []
    for name in tool_names:
        resolved_name = _resolve_tool_name(name)
        executor_class = TOOL_EXECUTOR_MAP.get(resolved_name)
        if executor_class:
            executor = executor_class()
            if executor.is_available():
                tools.append(executor.get_tool_definition())
    return tools


def create_executors(*tool_names: str) -> Dict[str, ToolExecutor]:
    """
    创建工具执行器实例
    
    Args:
        *tool_names: 工具名称（支持别名）。如果不传入参数，默认只创建 Python 执行器。
    
    Returns:
        工具名称到执行器实例的映射
    
    Example:
        executors = create_executors()  # 默认只创建 Python 执行器
        executors = create_executors("python", "sagemath")
        executors = create_executors(PYTHON, SAGEMATH, MATHEMATICA, MATLAB)
    """
    # 如果没有指定工具，默认只创建 Python 执行器
    if not tool_names:
        tool_names = (PYTHON,)
    
    executors = {}
    for name in tool_names:
        resolved_name = _resolve_tool_name(name)
        executor_class = TOOL_EXECUTOR_MAP.get(resolved_name)
        if executor_class:
            executor = executor_class()
            if executor.is_available():
                executors[resolved_name] = executor
    return executors


def create_all_executors() -> Dict[str, ToolExecutor]:
    """
    创建所有可用工具的执行器实例
    
    Returns:
        工具名称到执行器实例的映射
    """
    executors = {}
    for tool_name, executor_class in TOOL_EXECUTOR_MAP.items():
        executor = executor_class()
        if executor.is_available():
            executors[tool_name] = executor
    return executors


# 向后兼容的别名
def create_tool_executors() -> Dict[str, ToolExecutor]:
    """
    创建所有可用工具的执行器实例（向后兼容）
    
    注意：此函数为向后兼容保留，建议使用 create_all_executors() 或 create_executors()
    
    Returns:
        工具名称到执行器实例的映射
    """
    return create_all_executors()


# 导出
__all__ = [
    # 基类
    "ToolExecutor",
    # 执行器类
    "PythonExecutor",
    "SageMathExecutor",
    "MathematicaExecutor",
    "MatlabExecutor",
    "ScriptExecutor",
    "Lean4Executor",
    "Lean4SorryAnalyzer",
    "Lean4SearchMathlib",
    "Lean4CheckAxioms",
    "Lean4ParseErrors",
    "Lean4SolverCascade",
    "Lean4TryExact",
    "Lean4MinimizeImports",
    "AskUserExecutor",
    "PipInstallExecutor",
    # 工具名称常量
    "PYTHON",
    "SAGEMATH",
    "MATHEMATICA",
    "MATLAB",
    "SCRIPT",
    "LEAN4",
    "LEAN4_SORRY_ANALYZER",
    "LEAN4_SEARCH_MATHLIB",
    "LEAN4_CHECK_AXIOMS",
    "LEAN4_PARSE_ERRORS",
    "LEAN4_SOLVER_CASCADE",
    "LEAN4_TRY_EXACT",
    "LEAN4_MINIMIZE_IMPORTS",
    "ASK_USER",
    "INSTALL_PYTHON_PACKAGES",
    # 函数
    "get_default_tools",
    "get_all_tools",
    "get_tools",
    "create_executors",
    "create_all_executors",
    "create_tool_executors",  # 向后兼容
    # 映射
    "TOOL_EXECUTOR_MAP",
]


if __name__ == '__main__':
    print("测试工具模块...")
    print("=" * 50)
    
    # 测试默认工具
    print("\n1. 默认工具 (get_default_tools):")
    default_tools = get_default_tools()
    print(f"   数量: {len(default_tools)}")
    for tool in default_tools:
        print(f"   - {tool['function']['name']}")
    
    # 测试所有工具
    print("\n2. 所有可用工具 (get_all_tools):")
    all_tools = get_all_tools()
    print(f"   数量: {len(all_tools)}")
    for tool in all_tools:
        print(f"   - {tool['function']['name']}")
    
    # 测试指定工具
    print("\n3. 指定工具 (get_tools('python', 'sage')):")
    specified_tools = get_tools("python", "sage")
    print(f"   数量: {len(specified_tools)}")
    for tool in specified_tools:
        print(f"   - {tool['function']['name']}")
    
    # 测试默认执行器
    print("\n4. 默认执行器 (create_executors()):")
    default_executors = create_executors()
    print(f"   数量: {len(default_executors)}")
    for name, executor in default_executors.items():
        print(f"   - {name}: {type(executor).__name__}")
    
    # 测试所有执行器
    print("\n5. 所有执行器 (create_all_executors()):")
    all_executors = create_all_executors()
    print(f"   数量: {len(all_executors)}")
    for name, executor in all_executors.items():
        print(f"   - {name}: {type(executor).__name__}")
    
    # 测试执行
    print("\n6. 测试 Python 执行器:")
    if PYTHON in default_executors:
        result = default_executors[PYTHON].execute("print(1 + 2 * 3)")
        print(f"   代码: print(1 + 2 * 3)")
        print(f"   成功: {result['success']}")
        print(f"   输出: {result['output']}")
    else:
        print("   Python 执行器不可用")
    
    print("\n" + "=" * 50)
    print("测试完成！")
