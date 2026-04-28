#!/usr/bin/env python3
"""
使用 DeepSeek 为工具执行器生成并运行测试用例

此脚本让用户选择一个工具，然后使用 DeepSeek 为该工具生成 10 个测试用例，
并自动执行每个测试来验证结果的正确性。
"""
import json
import sys
from typing import Dict, Any, List, Optional

from llm_utils.deepseek import DeepSeekChatSession
from llm_utils.tools import (
    PYTHON, SAGEMATH, MATHEMATICA, MATLAB, SCRIPT, LEAN4,
    get_tools, create_executors, TOOL_EXECUTOR_MAP
)


# 工具描述信息，用于帮助 DeepSeek 理解每个工具的用途
TOOL_DESCRIPTIONS = {
    PYTHON: {
        "name": "Python",
        "description": "在受限沙箱环境中执行 Python 代码（使用 RestrictedPython），无法访问文件系统和网络",
        "examples": [
            "print(1 + 2 * 3)",
            "for i in range(5): print(i)",
            "x = [1, 2, 3]; print(sum(x))",
        ]
    },
    SAGEMATH: {
        "name": "SageMath",
        "description": "执行 SageMath 代码，支持符号计算、数论、代数等高级数学运算",
        "examples": [
            "print(factor(100))",
            "var('x y'); print(expand((x+y)^3))",
            "print(is_prime(97))",
        ]
    },
    MATHEMATICA: {
        "name": "Mathematica",
        "description": "执行 Mathematica/Wolfram Language 代码，支持符号计算、微积分、方程求解等",
        "examples": [
            "1 + 2 * 3",
            "Expand[(x+y)^3]",
            "Solve[x^2 - 5x + 6 == 0, x]",
        ]
    },
    MATLAB: {
        "name": "MATLAB",
        "description": "执行 MATLAB 代码，支持矩阵运算、数值分析、信号处理等",
        "examples": [
            "disp(1 + 2 * 3)",
            "A = [1 2; 3 4]; disp(det(A))",
            "disp(isprime(37))",
        ]
    },
    SCRIPT: {
        "name": "Shell Script",
        "description": "在项目根目录下执行 Shell 命令（需要用户确认）",
        "examples": [
            "echo 'Hello, World!'",
            "python --version",
            "date",
        ]
    },
    LEAN4: {
        "name": "LEAN4",
        "description": "执行 LEAN4 代码，用于数学定理证明和类型检查，支持 Mathlib",
        "examples": [
            "import Mathlib.Tactic\nexample : 1 + 1 = 2 := by norm_num",
            "#check Nat.add_comm",
            "example (a b : ℤ) : (a + b) ^ 2 = a ^ 2 + 2 * a * b + b ^ 2 := by ring",
        ]
    }
}


def get_system_prompt(tool_name: str, tool_info: Dict[str, Any]) -> str:
    """生成用于测试生成的系统提示词"""
    return f"""你是一个专业的测试工程师，负责为 {tool_info['name']} 工具执行器生成测试用例。

## 工具信息
- 工具名称: {tool_name}
- 工具描述: {tool_info['description']}
- 示例代码:
{chr(10).join(f"  - {ex}" for ex in tool_info['examples'])}

## 你的任务
你需要为这个工具生成 10 个测试用例，并通过调用工具来验证每个测试。

## 测试要求
1. 测试应该覆盖不同的功能场景
2. 包含基础功能测试和边界条件测试
3. 每个测试应该有明确的预期结果
4. 测试应该能够验证工具是否正常工作

## 输出格式
对于每个测试，请：
1. 说明测试目的
2. 调用工具执行代码
3. 检查执行结果是否符合预期
4. 给出测试是否通过的判断

请开始生成并执行测试用例。"""


def select_tool() -> Optional[str]:
    """让用户选择要测试的工具"""
    print("\n" + "=" * 60)
    print("📋 可用的工具执行器")
    print("=" * 60)
    
    # 检查每个工具的可用性
    available_tools = []
    executors = create_executors(*TOOL_EXECUTOR_MAP.keys())
    
    tool_list = [PYTHON, SAGEMATH, MATHEMATICA, MATLAB, SCRIPT, LEAN4]
    
    for i, tool_name in enumerate(tool_list, 1):
        info = TOOL_DESCRIPTIONS[tool_name]
        is_available = tool_name in executors
        status = "✅ 可用" if is_available else "❌ 不可用"
        print(f"  {i}. {info['name']:15} - {info['description'][:40]}... [{status}]")
        if is_available:
            available_tools.append(tool_name)
    
    print("\n  0. 退出")
    print("=" * 60)
    
    if not available_tools:
        print("\n❌ 没有可用的工具执行器，请检查依赖是否已安装。")
        return None
    
    while True:
        try:
            choice = input("\n请选择要测试的工具 [1-6] 或 0 退出: ").strip()
            if choice == "0":
                return None
            
            idx = int(choice) - 1
            if 0 <= idx < len(tool_list):
                selected = tool_list[idx]
                if selected in available_tools:
                    return selected
                else:
                    print(f"❌ {TOOL_DESCRIPTIONS[selected]['name']} 当前不可用，请选择其他工具。")
            else:
                print("❌ 无效的选择，请输入 1-6 或 0")
        except ValueError:
            print("❌ 请输入有效的数字")


def run_tool_tests(tool_name: str) -> Dict[str, Any]:
    """使用 DeepSeek 为指定工具生成并运行测试"""
    tool_info = TOOL_DESCRIPTIONS[tool_name]
    
    print(f"\n🔧 正在为 {tool_info['name']} 生成测试用例...")
    print("=" * 60)
    
    # 获取工具定义和执行器
    tools = get_tools(tool_name)
    
    if not tools:
        return {
            "success": False,
            "error": f"无法获取工具 {tool_name} 的定义",
            "tests": []
        }
    
    # 创建 DeepSeek 会话
    system_prompt = get_system_prompt(tool_name, tool_info)
    
    try:
        session = DeepSeekChatSession(
            system_prompt=system_prompt,
            model="deepseek-chat",  # 使用 chat 模型，支持工具调用
            tools=tools
        )
    except ValueError as e:
        return {
            "success": False,
            "error": f"无法创建 DeepSeek 会话: {str(e)}",
            "tests": []
        }
    
    # 发送测试请求
    prompt = f"""请为 {tool_info['name']} 工具生成 10 个测试用例。

每个测试用例应该:
1. 有明确的测试目的
2. 调用工具执行代码
3. 验证结果是否正确
4. 判断测试是否通过

请按顺序执行每个测试，并在最后给出测试总结：
- 通过的测试数量
- 失败的测试数量
- 总体评估

现在开始测试！"""
    
    print("\n📤 发送测试请求到 DeepSeek...")
    print("-" * 60)
    
    try:
        response = session.ask_with_tools(prompt)
        
        # 获取最终响应
        final_response = session.recent_response
        
        print("\n📥 测试执行完成！")
        print("=" * 60)
        print("\n📝 DeepSeek 测试报告:")
        print("-" * 60)
        print(final_response)
        print("-" * 60)
        
        # 从 history 中提取测试信息
        test_results = []
        for h in session.history:
            if isinstance(h, dict) and h.get("_type") == "tool_turn":
                for sub_turn in h.get("sub_turns", []):
                    for tool_call in sub_turn.get("tool_calls", []):
                        test_results.append({
                            "tool": tool_call.get("tool_name"),
                            "code": tool_call.get("tool_arguments", {}).get("code", ""),
                            "result": tool_call.get("tool_result", {}),
                        })
        
        return {
            "success": True,
            "tool": tool_name,
            "total_tool_calls": len(test_results),
            "tests": test_results,
            "report": final_response
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"测试执行失败: {str(e)}",
            "tests": []
        }


def print_test_summary(results: Dict[str, Any]):
    """打印测试结果摘要"""
    print("\n" + "=" * 60)
    print("📊 测试结果摘要")
    print("=" * 60)
    
    if not results.get("success"):
        print(f"❌ 测试失败: {results.get('error', '未知错误')}")
        return
    
    print(f"🔧 测试工具: {TOOL_DESCRIPTIONS.get(results['tool'], {}).get('name', results['tool'])}")
    print(f"📞 工具调用次数: {results['total_tool_calls']}")
    
    # 统计成功/失败
    success_count = 0
    failure_count = 0
    
    for test in results.get("tests", []):
        result = test.get("result", {})
        if result.get("success"):
            success_count += 1
        else:
            failure_count += 1
    
    print(f"✅ 成功执行: {success_count}")
    print(f"❌ 执行失败: {failure_count}")
    
    print("=" * 60)


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("🧪 DeepSeek 工具测试器")
    print("=" * 60)
    print("此工具使用 DeepSeek 为指定的工具执行器生成测试用例，")
    print("并自动执行每个测试来验证工具的正确性。")
    
    # 选择工具
    tool_name = select_tool()
    if not tool_name:
        print("\n👋 再见！")
        return
    
    tool_info = TOOL_DESCRIPTIONS[tool_name]
    print(f"\n✅ 已选择: {tool_info['name']}")
    
    # 确认执行
    confirm = input("\n是否开始测试? [y/n]: ").strip().lower()
    if confirm not in ('y', 'yes', '是'):
        print("\n👋 已取消测试。")
        return
    
    # 运行测试
    results = run_tool_tests(tool_name)
    
    # 打印摘要
    print_test_summary(results)
    
    # 保存结果
    from datetime import datetime
    from pathlib import Path

    # 创建结果目录
    results_dir = Path(__file__).parent.parent / "history"
    results_dir.mkdir(exist_ok=True)

    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = results_dir / f"test_{tool_name}_{timestamp}.json"

    # 清理不可序列化的对象
    save_data = {
        "success": results.get("success"),
        "tool": results.get("tool"),
        "total_tool_calls": results.get("total_tool_calls"),
        "tests": results.get("tests", []),
        "report": results.get("report"),
        "timestamp": timestamp
    }

    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)

    print(f"\n💾 结果已保存到: {result_file}")


if __name__ == "__main__":
    main()
