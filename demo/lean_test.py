from pathlib import Path
from llm_utils.usages.lean_formalize import *

if __name__ == '__main__':

    from utils.save_print import capture_output_to_file
    from time import time

    with capture_output_to_file(f'output/Demo'):
        start = time()

        with open("input/pb") as f:
            problem = f.read()
        with open("input/sol") as f:
            analysis = f.read()

        formalizer = LeanFormalizer(max_iterations=50, output_dir=Path(__file__).parent)
        result = formalizer.formalize(problem, analysis)

        print(f"\n成功: {result['success']}")
        print(f"迭代次数: {result['iterations']}")
        print(f"文件路径: {result['file_path']}")
        print("\n--- 最终代码 ---")
        print(result["code"])
        if result["error"]:
            print("\n--- 错误信息 ---")
            print(result["error"])

        # Agent 路由与上下文摘要
        print("\n--- Agent 路由摘要 ---")
        for entry in result.get("conversation_log", []):
            print(f"[{entry['agent']:6}] {entry['routing']:20} | iteration={entry['iteration']} | tools={len(entry.get('tool_calls', []))}")

        print("\n--- 最终上下文摘要 ---")
        if result.get("conversation_log"):
            last_ctx = result["conversation_log"][-1]["context_snapshot"]
            print(f"proof_details (前200字): {last_ctx['proof_details'][:200]}...")
            print(f"last_lean_output (前200字): {last_ctx['last_lean_output'][:200]}...")

        print("\n--- 尝试总结 ---")
        print(result.get("attempt_summary", "无")[:500])

        end = time() - start
        print("Time Consumed: " + str(end / 60) + " minutes")

