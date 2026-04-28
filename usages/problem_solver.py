from llm_utils.deepseek import DeepSeekChatSession
from llm_utils.tools import get_all_tools


MATH_SOLVER_SYSTEM_PROMPT = """你是一位专业的数学解题助手。请遵循以下要求：

## 语言要求
- 使用中文进行思考和回答
- 所有解释和推理过程都用中文表达

## 工具使用要求
- 你可以使用以下计算工具来验证计算结果：
  - execute_python: 执行 Python 代码（处于 Restrict Python 环境, 只有基本功能）
  - execute_sagemath: 执行 SageMath 代码（适合代数、数论相关问题）
  - execute_mathematica: 执行 Mathematica 代码（适合符号计算、微积分、方程求解等）
  - execute_matlab: 执行 Matlab 代码（适合矩阵运算、数值分析、工程计算等）

- **重要**：每个计算步骤都必须调用工具进行验证，不要仅凭推理给出计算结果
- 选择最合适的工具计算, 可以尝试多个不同工具
- 工具会返回 stdout 中的内容

## 解题格式
1. 首先分析题目，理解问题
2. 制定解题策略
3. 逐步执行计算，每个计算步骤都调用工具验证
4. 总结答案

## 工具调用示例
当你需要计算 1+2*3 时，应该调用工具：
```python
print(1 + 2 * 3)
```

当你需要解方程 x^2 - 5x + 6 = 0 时，可以调用：
```python
import sympy as sp
x = sp.Symbol('x')
solutions = sp.solve(x**2 - 5*x + 6, x)
print(f"方程的解: {solutions}")
```

请严格遵循以上要求，确保每个计算都经过工具验证。
"""


if __name__ == '__main__':
    # 创建带工具的 DeepSeekChatSession 实例
    # 使用 get_all_tools() 获取所有可用工具（Python、SageMath、Mathematica、Matlab）
    tools = get_all_tools()
    session = DeepSeekChatSession(
        system_prompt=MATH_SOLVER_SYSTEM_PROMPT,
        model="deepseek-chat",  # 使用 deepseek-chat 以获得更好的工具调用支持
        tools=tools
    )
    
    # 提示用户输入问题
    problem = input("请输入问题: ")
    
    # 调用 ask_with_tools 并输出回答
    response = session.ask_with_tools(problem)
    print("\n" + "=" * 50)
    print("回答：")
    print(session.recent_response)
    print("=" * 50 + "\n")
    
    # 追问循环
    while True:
        follow_up = input("追问 (q退出): ")
        if follow_up.lower() == 'q':
            print("再见！")
            break
        
        # 继续在同一个会话中追问
        response = session.ask_with_tools(follow_up)
        print("\n" + "=" * 50)
        print("回答：")
        print(session.recent_response)
        print("=" * 50 + "\n")

