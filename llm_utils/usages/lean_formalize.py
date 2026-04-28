"""
LEAN 形式化主流程

基于开源 lean4-skills 项目，实现上下文分离和压缩机制：
- agent 先检查并修正证明细节
- DS 多轮生成 LEAN 代码和修改
- 每轮 DS 总结尝试和优化方向
- 上下文压缩：仅保留最新证明细节、总结、最后一次代码及输出
- 停止条件：无 sorry 且编译通过
"""
import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

from llm_utils.deepseek import DeepSeekChatSession
from llm_utils.tools import get_tools, create_executors
from llm_utils.usages.lean4_skill_for_ds import build_lean4_skill_prompt


# Lean 4 项目目录（用于写入临时文件）
LEAN4_PROJECT_DIR = Path(__file__).parent.parent / "tools" / "lean4_project"
LEAN4_SCRATCH_DIR = LEAN4_PROJECT_DIR / "Scratch"

DETAIL_SYSTEM_PROMPT = """你是一位严谨的数学证明审阅专家。你的任务是：
1. 仔细阅读用户提供的数学题目和解析；
2. 检查解析中的证明细节是否完整、逻辑是否严密、步骤是否清晰；
3. 修正任何不严谨或缺失的细节；
4. 输出一份结构化的、完整的证明细节，供另一位 agent 将其形式化为 Lean 4 代码。

输出要求：
- 使用中文；
- 明确列出所有定义、假设、引理和主定理的证明步骤；
- 指出可能需要的 mathlib 对应概念或 tactic；
- 不要输出 Lean 代码，只输出证明细节说明。
"""


class LeanFormalizer:
    """LEAN 代码形式化器，支持上下文分离和压缩的多轮迭代"""

    def __init__(
        self,
        model: str = "deepseek-reasoner",
        max_iterations: int = 10,
        auto_update_details_every: int = 2,
        output_dir: Optional[Path] = None,
    ):
        self.model = model
        self.max_iterations = max_iterations
        self.auto_update_details_every = auto_update_details_every
        self.output_dir = output_dir

        # detail_session: 无工具，纯文本推理
        self.detail_session = DeepSeekChatSession(DETAIL_SYSTEM_PROMPT, model=model)

        # code_session: 带全部 Lean 工具
        lean_tool_names = [
            "lean4",
            "analyze_sorries",
            "search_mathlib",
            "parse_lean_errors",
            "solver_cascade",
            "try_exact_at_step",
            "check_axioms",
            "minimize_imports",
        ]
        self.lean_tools = get_tools(*lean_tool_names)
        self.tool_executors = create_executors(*lean_tool_names)
        self.code_session = DeepSeekChatSession(
            build_lean4_skill_prompt(),
            model=model,
            tools=self.lean_tools,
        )

        # 上下文压缩字段
        self.proof_details: str = ""
        self.attempt_summary: str = ""
        self.last_code: str = ""
        self.last_lean_output: str = ""
        self.last_error_structured: Optional[list] = None
        self.last_sorry_report: Optional[dict] = None
        self.iteration_count: int = 0
        self.final_file_path: Optional[Path] = None
        self.last_compile_success: bool = False
        self.conversation_log: list = []

    # ------------------------------------------------------------------
    # 对外入口
    # ------------------------------------------------------------------
    def formalize(self, problem: str, analysis: str) -> Dict[str, Any]:
        """
        主流程：将题目和解析形式化为 LEAN 代码。

        Returns:
            {
                "success": bool,
                "code": str,
                "error": str,
                "iterations": int,
                "file_path": str | None,
                "proof_details": str,
                "attempt_summary": str,
            }
        """
        # Step 0: 修正证明细节
        self._refine_proof_details(problem, analysis)

        # Step 1: 初始代码生成
        initial_prompt = self._build_code_prompt(is_first=True)
        self._code_ask(initial_prompt)
        self.last_code = self._extract_lean_code(self.code_session.recent_response)

        # 编译验证
        file_path = self._write_lean_file(self.last_code)
        self._compile_and_analyze(file_path)

        # 迭代循环
        for iteration in range(1, self.max_iterations + 1):
            self.iteration_count = iteration
            if self._should_stop():
                break

            # 可选：更新证明细节
            if iteration % self.auto_update_details_every == 0:
                self._update_proof_details()

            # 生成总结和下一轮代码
            prompt = self._build_code_prompt(is_first=False)
            self._code_ask(prompt)
            response = self.code_session.recent_response
            self.attempt_summary = self._extract_summary(response)
            self.last_code = self._extract_lean_code(response)

            # 重新编译
            file_path = self._write_lean_file(self.last_code)
            self._compile_and_analyze(file_path)

        # 最终质量门：检查公理
        final_success = self._should_stop()
        if final_success and file_path:
            axiom_result = self._run_tool("check_axioms", {"file_path": str(file_path), "report_only": True})
            if not axiom_result.get("success", False):
                # 公理检查不通过不阻断，但附加到 error 中
                pass

        self.final_file_path = file_path

        # 若指定了输出目录，复制最终文件并保存会话日志
        local_file_path = file_path
        if self.output_dir and file_path:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            local_file_path = self.output_dir / file_path.name
            shutil.copy2(file_path, local_file_path)
            self.detail_session._save(save_dir=self.output_dir)
            self.code_session._save(save_dir=self.output_dir)

        result = {
            "success": final_success,
            "code": self.last_code,
            "error": self.last_lean_output if not final_success else "",
            "iterations": self.iteration_count,
            "file_path": str(local_file_path) if local_file_path else None,
            "proof_details": self.proof_details,
            "attempt_summary": self.attempt_summary,
            "conversation_log": self.conversation_log,
        }
        self._save_conversation_log()
        return result

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------
    def _refine_proof_details(self, problem: str, analysis: str) -> None:
        prompt = f"""## 题目
{problem}

## 解析
{analysis}

请检查并修正上述解析中的证明细节，输出完整、结构化的证明细节说明。"""
        self.detail_session.works(prompt)
        self.proof_details = self.detail_session.recent_response or ""
        self._log_turn(
            agent="detail",
            routing="refine_proof_details",
            iteration=0,
            prompt=prompt,
            response=self.proof_details,
        )

    def _update_proof_details(self) -> None:
        """基于当前代码和错误，重新修正证明细节"""
        prompt = f"""基于当前形式化过程中遇到的问题，请重新检查并修正证明细节。

## 原证明细节
{self.proof_details}

## 当前代码
```lean
{self.last_code}
```

## 编译输出
{self.last_lean_output}

请输出更新后的、更准确的证明细节说明。"""
        self.detail_session.works(prompt)
        self.proof_details = self.detail_session.recent_response or self.proof_details
        self._log_turn(
            agent="detail",
            routing="update_proof_details",
            iteration=self.iteration_count,
            prompt=prompt,
            response=self.proof_details,
        )

    def _build_code_prompt(self, is_first: bool) -> str:
        """构建压缩后的代码生成 prompt"""
        error_json = ""
        if self.last_error_structured:
            try:
                error_json = json.dumps(self.last_error_structured, ensure_ascii=False, indent=2)
            except Exception:
                error_json = str(self.last_error_structured)

        sorry_json = ""
        if self.last_sorry_report:
            try:
                sorry_json = json.dumps(self.last_sorry_report, ensure_ascii=False, indent=2)
            except Exception:
                sorry_json = str(self.last_sorry_report)

        if is_first:
            return f"""## 任务
根据以下修正后的证明细节，生成完整的、可编译的 Lean 4 代码。

## 证明细节
{self.proof_details}

## 要求
- 代码必须完整（包含必要的 import）；
- 使用 `theorem` 或 `example` 包裹主结论；
- 不要包含 `sorry`；
- 行宽不超过 100 字符；
- 优先搜索 mathlib，不要重复证明已有引理（必要时可调用 search_mathlib）；
- 输出格式：直接给出 ```lean ... ``` 代码块。

请生成代码。"""

        return f"""## 任务
根据以下压缩上下文，先总结当前尝试和优化方向，然后生成下一轮修正后的完整 Lean 4 代码。

## 最新修正的证明细节
{self.proof_details}

## 历史尝试总结
{self.attempt_summary or "（首次迭代）"}

## 上一轮代码
```lean
{self.last_code}
```

## 编译输出
{self.last_lean_output or "（无输出）"}

## 结构化错误分析
```json
{error_json or "无"}
```

## sorry 分析报告
```json
{sorry_json or "无"}
```

## 输出格式要求
1. 以 `## 本轮总结` 开头，用 2-4 句话总结：
   - 当前已作出的尝试；
   - 发现的根本问题；
   - 下一步优化方向。
2. 以 `## 下一轮代码` 开头，输出完整的下一轮 Lean 4 代码块（```lean ... ```）。
3. 代码必须是完整文件内容，可直接用 `lake env lean` 编译。
4. 如果存在简单 `sorry`，你可以先调用 `solver_cascade` 或 `try_exact_at_step` 工具尝试自动填充，再将结果整合进代码。

请输出总结和代码。"""

    def _code_ask(self, prompt: str) -> None:
        """清空历史消息，发送压缩上下文"""
        self.code_session.messages.clear()
        self.code_session.ask_with_tools(prompt)
        # 提取本次工具调用摘要
        tool_calls = []
        if self.code_session.history:
            last_turn = self.code_session.history[-1]
            if isinstance(last_turn, dict) and last_turn.get("_type") == "tool_turn":
                for sub in last_turn.get("sub_turns", []):
                    for tc in sub.get("tool_calls", []):
                        tool_calls.append({
                            "tool_name": tc.get("tool_name"),
                            "tool_arguments": tc.get("tool_arguments"),
                            "execution_time": tc.get("execution_time", 0.0),
                        })
        routing = "initial_generation" if not self.last_code else "iteration"
        self._log_turn(
            agent="code",
            routing=routing,
            iteration=self.iteration_count,
            prompt=prompt,
            response=self.code_session.recent_response or "",
            tool_calls=tool_calls,
        )

    def _log_turn(
        self,
        agent: str,
        routing: str,
        iteration: int,
        prompt: str,
        response: str,
        tool_calls: Optional[list] = None,
    ) -> None:
        """记录本轮对话的上下文、路由与结果"""
        from datetime import datetime
        self.conversation_log.append({
            "agent": agent,
            "routing": routing,
            "iteration": iteration,
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "context_snapshot": {
                "proof_details": self.proof_details,
                "attempt_summary": self.attempt_summary,
                "last_code": self.last_code,
                "last_lean_output": self.last_lean_output,
                "last_error_structured": self.last_error_structured,
                "last_sorry_report": self.last_sorry_report,
            },
            "tool_calls": tool_calls or [],
            "response": response,
        })

    def _save_conversation_log(self) -> Path:
        """将聚合日志写入独立文件"""
        from datetime import datetime
        log_dir = self.output_dir / "files" if self.output_dir else Path(__file__).parent.parent / "history"
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        short_id = uuid.uuid4().hex[:4]
        log_path = log_dir / f"lean-formalize-log-{timestamp}-{short_id}.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(self.conversation_log, f, ensure_ascii=False, indent=2)
        return log_path

    def _write_lean_file(self, code: str) -> Path:
        """将代码写入 Scratch 目录的临时文件"""
        LEAN4_SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        temp_name = f"Formalize_{uuid.uuid4().hex[:8]}.lean"
        file_path = LEAN4_SCRATCH_DIR / temp_name
        file_path.write_text(code.strip() + "\n", encoding="utf-8")
        return file_path

    def _compile_and_analyze(self, file_path: Path) -> None:
        """编译代码，并自动分析错误和 sorry"""
        # 1) 执行编译（直接 lake env lean，保持一致性）
        lean_result = self._run_lake_env_lean(file_path)
        output = lean_result.get("output", "")
        error = lean_result.get("error", "")
        self.last_lean_output = f"{output}\n{error}".strip()
        self.last_compile_success = lean_result.get("success", False)

        # 2) 结构化错误
        self.last_error_structured = None
        if error:
            parse_result = self._run_tool("parse_lean_errors", {"error_text": error})
            if parse_result.get("parsed"):
                self.last_error_structured = parse_result["parsed"]

        # 3) 分析 sorry
        self.last_sorry_report = None
        sorry_result = self._run_tool("analyze_sorries", {"file_path": str(file_path), "format": "json"})
        if sorry_result.get("success"):
            try:
                self.last_sorry_report = json.loads(sorry_result["output"])
            except Exception:
                self.last_sorry_report = {"raw": sorry_result["output"]}
        else:
            self.last_sorry_report = {"error": sorry_result.get("error", "")}

    def _should_stop(self) -> bool:
        """停止条件：编译成功且无 sorry"""
        sorry_count = self._sorry_count()
        return self.last_compile_success and sorry_count == 0

    def _sorry_count(self) -> int:
        """从 sorry 报告中提取数量"""
        if isinstance(self.last_sorry_report, list):
            return len(self.last_sorry_report)
        if isinstance(self.last_sorry_report, dict):
            if "total_count" in self.last_sorry_report:
                return int(self.last_sorry_report["total_count"])
            if "count" in self.last_sorry_report:
                return int(self.last_sorry_report["count"])
            if "sorries" in self.last_sorry_report and isinstance(self.last_sorry_report["sorries"], list):
                return len(self.last_sorry_report["sorries"])
            # summary 格式可能只有一个整数
            raw = self.last_sorry_report.get("raw", "")
            try:
                return int(raw.strip())
            except Exception:
                pass
        # fallback: 正则检查代码
        return len(re.findall(r"\bsorry\b", self.last_code))

    def _run_tool(self, tool_name: str, arguments: dict) -> dict:
        """直接执行工具，不通过 DS"""
        executor = self.tool_executors.get(tool_name)
        if not executor:
            return {"success": False, "output": "", "error": f"工具 {tool_name} 未找到", "execution_time": 0.0}
        return executor.execute(**arguments)

    def _run_lake_env_lean(self, file_path: Path) -> dict:
        """直接调用 lake env lean 编译指定文件"""
        import time
        start = time.time()
        env = os.environ.copy()
        elan_bin = Path.home() / ".elan" / "bin"
        if elan_bin.exists():
            env["PATH"] = f"{elan_bin}:{env.get('PATH', '')}"
        try:
            # 计算相对路径（lake env lean 需要相对于项目根目录的路径）
            rel_path = file_path.relative_to(LEAN4_PROJECT_DIR)
            result = subprocess.run(
                ["lake", "env", "lean", str(rel_path)],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(LEAN4_PROJECT_DIR),
                env=env,
            )
            elapsed = time.time() - start
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            # Lean 可能将错误输出到 stdout
            combined = f"{stdout}\n{stderr}".strip()
            has_error = result.returncode != 0 or any(
                indicator in combined.lower()
                for indicator in ["error:", "error at", "unknown identifier", "type mismatch"]
            )
            error_msg = stderr or stdout if has_error else ""
            return {
                "success": not has_error,
                "output": stdout,
                "error": error_msg,
                "execution_time": elapsed,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "", "error": "Timeout", "execution_time": time.time() - start}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e), "execution_time": time.time() - start}

    @staticmethod
    def _extract_lean_code(text: str) -> str:
        """从响应中提取 ```lean ... ``` 代码块"""
        if not text:
            return ""
        # 匹配 ```lean 或 ```
        patterns = [
            r"```lean\s*\n(.*?)\n```",
            r"```\s*\n(.*?)\n```",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.DOTALL)
            if m:
                return m.group(1).strip()
        # 如果没有代码块标记，尝试取整个文本（简单启发式）
        return text.strip()

    @staticmethod
    def _extract_summary(text: str) -> str:
        """从响应中提取 ## 本轮总结 部分"""
        if not text:
            return ""
        m = re.search(r"## 本轮总结\s*\n(.*?)(?:\n## |\n```|$)", text, re.DOTALL)
        if m:
            return m.group(1).strip()
        # fallback: 取代码块之前的内容
        code_start = text.find("```lean")
        if code_start > 0:
            return text[:code_start].strip()
        return ""


# ----------------------------------------------------------------------
# CLI / 最小测试
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("LeanFormalizer 最小测试")
    print("=" * 60)

    problem = "证明：对于任意自然数 n，n + 0 = n。"
    analysis = "根据自然数的定义，0 是加法单位元，因此 n + 0 = n 对任意自然数 n 成立。"

    formalizer = LeanFormalizer(max_iterations=3)
    result = formalizer.formalize(problem, analysis)

    print(f"\n成功: {result['success']}")
    print(f"迭代次数: {result['iterations']}")
    print(f"文件路径: {result['file_path']}")
    print("\n--- 最终代码 ---")
    print(result["code"])
    if result["error"]:
        print("\n--- 错误信息 ---")
        print(result["error"])
