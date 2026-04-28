"""
Lean 4 工具集 — 将 refs/lean4-skills-main 中的脚本封装为 DS 可调用的 ToolExecutor。
"""
import os
import shutil
import subprocess
import tempfile
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional

from llm_utils.tools.base import ToolExecutor


# 路径配置
_PROJECT_ROOT = Path(__file__).parent.parent
LEAN4_SCRIPTS = _PROJECT_ROOT / "refs" / "lean4-skills-main" / "plugins" / "lean4" / "lib" / "scripts"
LEAN4_PROJECT_DIR = Path(__file__).parent / "lean4_project"
MATHLIB_PATH = LEAN4_PROJECT_DIR / ".lake" / "packages" / "mathlib"


def _ensure_scripts_env(env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """确保环境变量中包含 LEAN4_SCRIPTS 和 MATHLIB_PATH"""
    e = (env or {}).copy()
    e["LEAN4_SCRIPTS"] = str(LEAN4_SCRIPTS)
    e["MATHLIB_PATH"] = str(MATHLIB_PATH)
    elan_bin = Path.home() / ".elan" / "bin"
    if elan_bin.exists():
        e["PATH"] = f"{elan_bin}:{e.get('PATH', os.environ.get('PATH', ''))}"
    return e


def _run_script(
    cmd: list,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: int = 120,
) -> Dict[str, Any]:
    """统一执行脚本，返回标准结果字典"""
    start = time.time()
    merged_env = _ensure_scripts_env(env)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd or str(LEAN4_PROJECT_DIR),
            env={**os.environ, **merged_env},
        )
        elapsed = time.time() - start
        success = result.returncode == 0
        return {
            "success": success,
            "output": result.stdout.strip(),
            "error": result.stderr.strip() if not success else "",
            "execution_time": elapsed,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "error": f"Timeout after {timeout}s",
            "execution_time": time.time() - start,
        }
    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": str(e),
            "execution_time": time.time() - start,
        }


class Lean4SorryAnalyzer(ToolExecutor):
    """分析 .lean 文件中的 sorry 数量和位置（基于 sorry_analyzer.py）"""

    def __init__(self, timeout: int = 60):
        super().__init__(timeout)
        self._script = LEAN4_SCRIPTS / "sorry_analyzer.py"
        self._available = self._script.exists()

    def is_available(self) -> bool:
        return self._available

    def _resolve_path(self, file_path: str) -> Path:
        target = Path(file_path)
        if target.exists():
            return target
        candidate = LEAN4_PROJECT_DIR / target
        if candidate.exists():
            return candidate
        return target

    def execute(self, file_path: str, format: str = "json", **kwargs) -> Dict[str, Any]:
        if not self._available:
            return {"success": False, "output": "", "error": "sorry_analyzer.py not found", "execution_time": 0.0}
        target = self._resolve_path(file_path)
        if not target.exists():
            return {"success": False, "output": "", "error": f"File not found: {file_path}", "execution_time": 0.0}
        python = shutil.which("python3") or shutil.which("python") or "python3"
        cmd = [python, str(self._script), str(target.resolve()), f"--format={format}", "--report-only"]
        return _run_script(cmd, timeout=self.timeout)

    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "analyze_sorries",
                "description": "Analyze a Lean 4 file for 'sorry' statements. Returns locations, contexts, and surrounding declarations. Use this after compilation to precisely check for remaining sorries.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to the .lean file to analyze"},
                        "format": {"type": "string", "enum": ["json", "text", "summary", "markdown"], "description": "Output format", "default": "json"},
                    },
                    "required": ["file_path"],
                },
            },
        }


class Lean4SearchMathlib(ToolExecutor):
    """搜索 mathlib 引理（基于 search_mathlib.sh / smart_search.sh）"""

    def __init__(self, timeout: int = 60):
        super().__init__(timeout)
        self._script_search = LEAN4_SCRIPTS / "search_mathlib.sh"
        self._script_smart = LEAN4_SCRIPTS / "smart_search.sh"
        self._available = self._script_search.exists() and MATHLIB_PATH.exists()

    def is_available(self) -> bool:
        return self._available

    def execute(self, query: str, search_type: str = "name", source: str = "mathlib", **kwargs) -> Dict[str, Any]:
        if not self._available:
            return {"success": False, "output": "", "error": "search_mathlib.sh or mathlib not found", "execution_time": 0.0}

        if source != "mathlib" and self._script_smart.exists():
            cmd = ["bash", str(self._script_smart), query, f"--source={source}"]
            return _run_script(cmd, timeout=self.timeout)

        cmd = ["bash", str(self._script_search), query, search_type]
        return _run_script(cmd, timeout=self.timeout)

    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "search_mathlib",
                "description": "Search for lemmas, theorems, and definitions in mathlib. Use this BEFORE trying to prove something from scratch. search_type can be 'name', 'type', or 'content'. source can be 'mathlib' (fast local grep), 'leansearch' (semantic API), 'loogle' (type-pattern API), or 'all'.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query, e.g. 'continuous.*compact' or 'Cauchy Schwarz'"},
                        "search_type": {"type": "string", "enum": ["name", "type", "content"], "default": "name"},
                        "source": {"type": "string", "enum": ["mathlib", "leansearch", "loogle", "all"], "default": "mathlib"},
                    },
                    "required": ["query"],
                },
            },
        }


class Lean4CheckAxioms(ToolExecutor):
    """检查非标准公理（基于 check_axioms_inline.sh）"""

    def __init__(self, timeout: int = 120):
        super().__init__(timeout)
        self._script = LEAN4_SCRIPTS / "check_axioms_inline.sh"
        self._available = self._script.exists()

    def is_available(self) -> bool:
        return self._available

    @staticmethod
    def _resolve_path(file_path: str) -> Path:
        target = Path(file_path)
        if target.exists():
            return target
        candidate = LEAN4_PROJECT_DIR / target
        if candidate.exists():
            return candidate
        return target

    def execute(self, file_path: str, report_only: bool = True, **kwargs) -> Dict[str, Any]:
        if not self._available:
            return {"success": False, "output": "", "error": "check_axioms_inline.sh not found", "execution_time": 0.0}
        target = self._resolve_path(file_path)
        if not target.exists():
            return {"success": False, "output": "", "error": f"File not found: {file_path}", "execution_time": 0.0}
        cmd = ["bash", str(self._script), str(target.resolve())]
        if report_only:
            cmd.append("--report-only")
        return _run_script(cmd, timeout=self.timeout)

    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "check_axioms",
                "description": "Scan a Lean 4 file for non-standard axioms (anything other than propext, Quot.sound, Classical.choice). Run this as a final quality gate before declaring success.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to the .lean file to scan"},
                        "report_only": {"type": "boolean", "default": True},
                    },
                    "required": ["file_path"],
                },
            },
        }


class Lean4ParseErrors(ToolExecutor):
    """将 Lean 编译错误解析为结构化 JSON（基于 parse_lean_errors.py）"""

    def __init__(self, timeout: int = 30):
        super().__init__(timeout)
        self._script = LEAN4_SCRIPTS / "parse_lean_errors.py"
        self._available = self._script.exists()

    def is_available(self) -> bool:
        return self._available

    def execute(self, error_text: str, **kwargs) -> Dict[str, Any]:
        if not self._available:
            return {"success": False, "output": "", "error": "parse_lean_errors.py not found", "execution_time": 0.0}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(error_text)
            tmp_path = f.name
        try:
            python = shutil.which("python3") or shutil.which("python") or "python3"
            cmd = [python, str(self._script), tmp_path]
            result = _run_script(cmd, timeout=self.timeout)
            try:
                parsed = json.loads(result["output"])
                result["parsed"] = parsed
            except Exception:
                result["parsed"] = None
            return result
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "parse_lean_errors",
                "description": "Parse raw Lean compiler error output into structured JSON (error type, location, goal, local context, suggestion keywords). Call this immediately after a failed compilation to get machine-readable error diagnostics.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "error_text": {"type": "string", "description": "Raw error text from Lean compiler (stderr/stdout)"},
                    },
                    "required": ["error_text"],
                },
            },
        }


class Lean4SolverCascade(ToolExecutor):
    """在指定行自动尝试 tactic 序列（基于 solver_cascade.py）"""

    def __init__(self, timeout: int = 60):
        super().__init__(timeout)
        self._script = LEAN4_SCRIPTS / "solver_cascade.py"
        self._available = self._script.exists()

    def is_available(self) -> bool:
        return self._available

    def execute(self, file_path: str, line: int, column: int = 0, **kwargs) -> Dict[str, Any]:
        if not self._available:
            return {"success": False, "output": "", "error": "solver_cascade.py not found", "execution_time": 0.0}
        target = Path(file_path)
        if target.exists():
            pass
        else:
            candidate = LEAN4_PROJECT_DIR / target
            if candidate.exists():
                target = candidate
        if not target.exists():
            return {"success": False, "output": "", "error": f"File not found: {file_path}", "execution_time": 0.0}

        context = {"line": line, "column": column, "errorType": kwargs.get("error_type", "")}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(context, f)
            ctx_path = f.name
        try:
            python = shutil.which("python3") or shutil.which("python") or "python3"
            cmd = [python, str(self._script), ctx_path, str(target.resolve())]
            result = _run_script(cmd, timeout=self.timeout)
            return result
        finally:
            try:
                os.unlink(ctx_path)
            except Exception:
                pass

    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "solver_cascade",
                "description": "Automatically try a sequence of solvers (rfl -> simp -> ring -> linarith -> nlinarith -> omega -> exact? -> apply? -> grind -> aesop) at a specific line in a Lean file. Useful for mechanically resolving simple sorries or goals. Returns a diff if any solver succeeds.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to the .lean file"},
                        "line": {"type": "integer", "description": "Line number to target (1-indexed)"},
                        "column": {"type": "integer", "default": 0, "description": "Column number"},
                        "error_type": {"type": "string", "description": "Optional error type to help decide whether to skip cascade"},
                    },
                    "required": ["file_path", "line"],
                },
            },
        }


class Lean4TryExact(ToolExecutor):
    """在指定 proof block 尝试 exact?（基于 try_exact_at_step.py）"""

    def __init__(self, timeout: int = 120):
        super().__init__(timeout)
        self._script = LEAN4_SCRIPTS / "try_exact_at_step.py"
        self._available = self._script.exists()

    def is_available(self) -> bool:
        return self._available

    def execute(self, file_path: str, line: int, **kwargs) -> Dict[str, Any]:
        if not self._available:
            return {"success": False, "output": "", "error": "try_exact_at_step.py not found", "execution_time": 0.0}
        target = Path(file_path)
        if target.exists():
            pass
        else:
            candidate = LEAN4_PROJECT_DIR / target
            if candidate.exists():
                target = candidate
        if not target.exists():
            return {"success": False, "output": "", "error": f"File not found: {file_path}", "execution_time": 0.0}
        python = shutil.which("python3") or shutil.which("python") or "python3"
        cmd = [python, str(self._script), f"{target.resolve()}:{line}"]
        return _run_script(cmd, timeout=self.timeout)

    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "try_exact_at_step",
                "description": "Try replacing a proof block with 'exact?' to see if Lean can find a one-liner proof. Provide the file path and a line inside the proof block. Returns the suggestion if found.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to the .lean file"},
                        "line": {"type": "integer", "description": "A line inside the proof block (1-indexed)"},
                    },
                    "required": ["file_path", "line"],
                },
            },
        }


class Lean4MinimizeImports(ToolExecutor):
    """移除未使用的 import（基于 minimize_imports.py）"""

    def __init__(self, timeout: int = 60):
        super().__init__(timeout)
        self._script = LEAN4_SCRIPTS / "minimize_imports.py"
        self._available = self._script.exists()

    def is_available(self) -> bool:
        return self._available

    def execute(self, file_path: str, dry_run: bool = False, **kwargs) -> Dict[str, Any]:
        if not self._available:
            return {"success": False, "output": "", "error": "minimize_imports.py not found", "execution_time": 0.0}
        target = Path(file_path)
        if target.exists():
            pass
        else:
            candidate = LEAN4_PROJECT_DIR / target
            if candidate.exists():
                target = candidate
        if not target.exists():
            return {"success": False, "output": "", "error": f"File not found: {file_path}", "execution_time": 0.0}
        python = shutil.which("python3") or shutil.which("python") or "python3"
        cmd = [python, str(self._script), str(target.resolve())]
        if dry_run:
            cmd.append("--dry-run")
        return _run_script(cmd, timeout=self.timeout)

    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "minimize_imports",
                "description": "Remove unused imports from a Lean 4 file. Use this as a cleanup step after the proof is complete. Set dry_run=True to preview changes without applying them.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to the .lean file"},
                        "dry_run": {"type": "boolean", "default": False},
                    },
                    "required": ["file_path"],
                },
            },
        }
