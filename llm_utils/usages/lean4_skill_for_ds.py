"""
Lean4 Skill Loader for DeepSeek

读取 refs/lean4-skills-main/ 中的核心 reference 文件，组装成 DS 可用的 system prompt。
不修改原文，仅做最小适配（在顶部添加环境说明）。
"""
from pathlib import Path
from typing import Optional, Dict

_PROJECT_ROOT = Path(__file__).parent.parent
_SKILL_BASE = _PROJECT_ROOT / "refs" / "lean4-skills-main" / "plugins" / "lean4" / "skills" / "lean4"
_REFERENCES_DIR = _SKILL_BASE / "references"

# 核心 reference 文件（默认加载）
CORE_REFERENCES = [
    (_SKILL_BASE / "SKILL.md", "SKILL.md"),
    (_REFERENCES_DIR / "tactics-reference.md", "tactics-reference.md"),
    (_REFERENCES_DIR / "tactic-patterns.md", "tactic-patterns.md"),
    (_REFERENCES_DIR / "lean-phrasebook.md", "lean-phrasebook.md"),
    (_REFERENCES_DIR / "compilation-errors.md", "compilation-errors.md"),
    (_REFERENCES_DIR / "mathlib-guide.md", "mathlib-guide.md"),
    (_REFERENCES_DIR / "sorry-filling.md", "sorry-filling.md"),
    (_REFERENCES_DIR / "proof-templates.md", "proof-templates.md"),
]

# 扩展 reference 文件（可通过 load_lean4_reference 动态加载）
EXTRA_REFERENCES: Dict[str, Path] = {
    "cycle-engine": _REFERENCES_DIR / "cycle-engine.md",
    "agent-workflows": _REFERENCES_DIR / "agent-workflows.md",
    "proof-golfing": _REFERENCES_DIR / "proof-golfing.md",
    "proof-golfing-patterns": _REFERENCES_DIR / "proof-golfing-patterns.md",
    "performance-optimization": _REFERENCES_DIR / "performance-optimization.md",
    "measure-theory": _REFERENCES_DIR / "measure-theory.md",
    "domain-patterns": _REFERENCES_DIR / "domain-patterns.md",
    "simp-reference": _REFERENCES_DIR / "simp-reference.md",
    "calc-patterns": _REFERENCES_DIR / "calc-patterns.md",
    "instance-pollution": _REFERENCES_DIR / "instance-pollution.md",
    "mathlib-style": _REFERENCES_DIR / "mathlib-style.md",
    "grind-tactic": _REFERENCES_DIR / "grind-tactic.md",
    "verso-docs": _REFERENCES_DIR / "verso-docs.md",
    "compiler-guided-repair": _REFERENCES_DIR / "compiler-guided-repair.md",
    "learn-pathways": _REFERENCES_DIR / "learn-pathways.md",
    "command-examples": _REFERENCES_DIR / "command-examples.md",
}


ENVIRONMENT_ADAPTATION = """
# 环境适配说明（DS 专用）

你正在一个无 LSP/MCP 实时目标查看能力的环境中工作。
编译验证统一通过 `execute_lean4` 工具完成（底层调用 `lake env lean`）。

## 可用工具清单

1. **execute_lean4(code)** — 执行/验证 LEAN 代码，返回编译结果。
2. **search_mathlib(query, search_type="name", source="mathlib")** — 搜索 mathlib 引理。优先在尝试证明前使用。
3. **analyze_sorries(file_path)** — 精确分析文件中 `sorry` 的数量和位置。
4. **parse_lean_errors(error_text)** — 将编译错误解析为结构化 JSON。
5. **solver_cascade(file_path, line)** — 在指定行自动尝试 `rfl→simp→ring→...`  tactic 序列。
6. **try_exact_at_step(file_path, line)** — 在 proof block 尝试 `exact?` 获取 one-liner 建议。
7. **check_axioms(file_path)** — 扫描非标准公理，用于最终质量门。
8. **minimize_imports(file_path)** — 清理未使用的 import。

## 工作流要求

- **Search before prove.** 写任何非平凡证明前，先调用 `search_mathlib`。
- **Build incrementally.** 每次修改后调用 `execute_lean4` 验证。
- **Use 100-character line width.** Lean 和 mathlib 的惯例是 100 字符行宽。
- **Never use `sorry` in final output.** 停止条件是：编译通过且不含 `sorry`。
- **No silent axiom additions.** 最终代码应只使用标准公理（`propext`, `Quot.sound`, `Classical.choice`）。

---
"""


def _read_file_safely(path: Path, max_lines: Optional[int] = None) -> str:
    """安全读取文件，可选截断"""
    if not path.exists():
        return f"\n<!-- 文件缺失: {path.name} -->\n"
    try:
        text = path.read_text(encoding="utf-8")
        if max_lines is not None:
            lines = text.splitlines()
            if len(lines) > max_lines:
                lines = lines[:max_lines]
                lines.append(f"\n<!-- {path.name} 已截断至前 {max_lines} 行 -->\n")
            text = "\n".join(lines)
        return text
    except Exception as e:
        return f"\n<!-- 读取 {path.name} 失败: {e} -->\n"


def build_lean4_skill_prompt(
    max_lines_per_ref: Optional[int] = None,
    include_core: bool = True,
    extra_refs: Optional[list] = None,
) -> str:
    """
    构建 DS 可用的 Lean4 system prompt。

    Args:
        max_lines_per_ref: 每个 reference 文件最大加载行数，None 表示不截断。
        include_core: 是否加载核心 reference 文件。
        extra_refs: 额外加载的 reference 名称列表，对应 EXTRA_REFERENCES 的键。
    """
    parts = [ENVIRONMENT_ADAPTATION.strip()]

    if include_core:
        parts.append("\n# Core Lean 4 Skill References\n")
        for path, name in CORE_REFERENCES:
            content = _read_file_safely(path, max_lines_per_ref)
            parts.append(f"\n## Source: {name}\n")
            parts.append(content)

    if extra_refs:
        parts.append("\n# Extra Lean 4 Skill References (Dynamically Loaded)\n")
        for ref_name in extra_refs:
            path = EXTRA_REFERENCES.get(ref_name)
            if path:
                content = _read_file_safely(path, max_lines_per_ref)
                parts.append(f"\n## Source: {ref_name}.md\n")
                parts.append(content)
            else:
                parts.append(f"\n<!-- 未知 reference: {ref_name} -->\n")

    return "\n".join(parts)


def load_lean4_reference(ref_name: str) -> str:
    """
    动态加载单个 reference 文件的完整内容。
    用于 DS 在需要时获取 specialist reference。
    """
    path = EXTRA_REFERENCES.get(ref_name)
    if not path:
        available = ", ".join(EXTRA_REFERENCES.keys())
        return f"错误: 未找到 reference '{ref_name}'。可用 reference: {available}"
    return _read_file_safely(path, max_lines=None)


def list_available_references() -> list:
    """返回所有可动态加载的 reference 名称列表"""
    return list(EXTRA_REFERENCES.keys())


if __name__ == "__main__":
    # 快速检查
    print("Core references:")
    for p, n in CORE_REFERENCES:
        print(f"  {n}: exists={p.exists()}")
    print("\nExtra references:")
    for k, p in EXTRA_REFERENCES.items():
        print(f"  {k}: exists={p.exists()}")
    print("\nBuilding prompt (first 2000 chars)...")
    prompt = build_lean4_skill_prompt()
    print(prompt[:2000])
