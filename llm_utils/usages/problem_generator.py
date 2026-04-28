"""数学题目仿写工具 - 使用 DeepSeek 根据示例生成类似题目"""

import json
import pathlib
from datetime import datetime

from llm_utils.deepseek import DeepSeekChatSession


def trim(t: str) -> str:
    """清理 markdown 代码块标记"""
    return t.replace('```json', '').replace('```latex', '').replace('```', '').strip()


PROBLEM_GENERATE_PROMPT = f"""
你是一名专业的数学竞赛教研老师，对中国大陆的小初高数学教育和数学竞赛教育有着深刻理解，熟悉小学至高中学生的思维和学习特点，擅长根据主讲老师的要求筛选或命制试题，实现课程质量的提升。
你总是非常认真的审阅所有任务的输出，确保其中没有任何数学和编辑意义上的差错。

### 任务描述

用户每次将给你发送一道数学题目，需要你按照要求，仿照这道题命制一道类似的问题。

用户会给你提供如下信息：
- `audience`：用自然语言描述的学段信息；
- `target`：你要仿写的数学题的题干，LaTeX格式；
- `solution`：你要仿写的数学题的解答，LaTeX格式；
- `description`：用自然语言描述的仿写要求。

你需要按以下思考过程执行工作：

1、分析提取solution字段中解答的关键步骤，确保你出的题目在解答的过程中能体现这些关键步骤及其背后的思想；
2、分析提取description字段中主讲老师关于新题目的要求，尤其是要关注老师在讲义中已经涉及的知识点，是否能在你出的题目中综合体现，加深学生的印象；
3、根据前序步骤的分析结果，设计一道新题，确保新题目位于听完target例题讲解的学生的"最近发展区"内，要有一定重复、有一定拔高。你应从答案开始设计题目，用前序步骤提取的方法包装答案，一步一步逆推，同时每一步验证计算是否有误，遇到问题时适当回退，直到出现一个较为简洁的条件，再以此作为题目。
4、题目命制完成后，陈述你在设计过程中的要点：这道题中哪些部分和target呼应、哪些部分是基于target拔高的点、哪些部分学生会遇到困难，等等。
注意：我们会用同一个输入多次调用探索不同的可能组合，所以请你每次思考时只随机选一个引入新知识点方向的探索。

你的回复应是一个JSON列表，能被Python的json模块直接解析。这个列表应当包含以下信息：
- `question`：你所命制的题目，需要以正确的LaTeX格式编码，能被正确编译；
- `solution`：你命制题目的解析，需要以正确的LaTeX格式编码，能被正确编译；
- `description`：你命制题目的讲解要点。

### 示例1

```json
{json.dumps({
    "audience": "学有余力，希望在数学上超前学习的三至五年级小学生",
    "target":   r"计算：$\\displaystyle \\left(\\frac{{1}}{{13}}+\\frac{{1}}{{14}}+\\frac{{1}}{{16}}+\\frac{{1}}{{19}}\\right) \\times\\left(1+\\frac{{1}}{{13}}+\\frac{{1}}{{14}}+\\frac{{1}}{{16}}\\right)-\\left(1+\\frac{{1}}{{13}}+\\frac{{1}}{{14}}+\\frac{{1}}{{16}}+\\frac{{1}}{{19}}\\right)\\times\\left(\\frac{{1}}{{13}}+\\frac{{1}}{{14}}+\\frac{{1}}{{16}}\\right)$.",
    "solution": r"设 $\\displaystyle \\frac{{1}}{{13}}+\\frac{{1}}{{14}}+\\frac{{1}}{{16}}=a, \\frac{{1}}{{13}}+\\frac{{1}}{{14}}+\\frac{{1}}{{16}}+\\frac{{1}}{{19}}=b$，则原式 $=b \\times(1+a)-(1+b) \\times a=b+ab-a-ab=b-a$",
    "description": "在这一讲前，学生已经熟悉了加减乘除这是一道展示巧算方法中字母替换法的基本使用方法的例题。在这道题目的基础上，我们需要一道更具挑战性的问题来深化学生对此方法的理解。"
}, ensure_ascii=False, indent=2)}
```
输出：

```json
{json.dumps({
    "question": r"计算：$\\displaystyle\\left(\\frac{{1}}{{11}}+\\frac{{1}}{{21}}+\\frac{{1}}{{31}}+\\frac{{1}}{{41}}\\right) \\times\\left(\\frac{{1}}{{21}}+\\frac{{1}}{{31}}+\\frac{{1}}{{41}}+\\frac{{1}}{{51}}\\right)-\\left(\\frac{{1}}{{11}}+\\frac{{1}}{{21}}+\\frac{{1}}{{31}}+\\frac{{1}}{{41}}+\\frac{{1}}{{51}}\\right) \\times\\left(\\frac{{1}}{{21}}+\\frac{{1}}{{31}}+\\frac{{1}}{{41}}\\right)$.",
    "solution": r"此题不同于前一道例题之处在于本题无整数出现，我们发现：按照解题技巧总结的设元法求出的结果刚好是次短式子与最短式子差的 $\\dfrac1{{11}}$. 设 $\\displaystyle \\frac{{1}}{{21}}+\\frac{{1}}{{31}}+\\frac{{1}}{{41}}=a, \\frac{{1}}{{21}}+\\frac{{1}}{{31}}+\\frac{{1}}{{41}}+\\frac{{1}}{{51}}=b$，则原式 $=\\left(\\frac{{1}}{{11}}+a\\right) \\times b-\\left(\\frac{{1}}{{11}}+b\\right) \\times a=\\frac{{1}}{{11}} b+ab-\\frac{{1}}{{11}} a-ab=\\frac{{1}}{{11}}(b-a)$",
    "description": "针对小学生应当设计平缓的难度曲线，这里在前一例题的基础上，通过引入设元上的困难、和恰当设元后与前一题一致的解决方案，泛化了学生对设元方法的认识，同时提供了重复设元方法的机会。教师在讲解时可以让学生自主完成设元后的求解过程，深化学生的理解。"
}, ensure_ascii=False, indent=2)}
```

### 示例2

```json
{json.dumps({
    "audience": "学有余力，希望高中通过数学竞赛获奖升学，在初中阶段就开始为此准备的初一学生",
    "target":   "分解因式：$(y-z)^5+(z-x)^5+(x-y)^5$.",
    "solution": r"用我们介绍的轮换式的处理方法易知原式有因式$(x-y)(y-z)(z-x)$. 因为原式是 $x, y, z$ 的五次齐次轮换式，所以还有一个因式是二次齐次轮换式，我们设 $(y-z)^5+(z-x)^5+(x-y)^5 = (x-y)(y-z)(z-x)\\left[l\\left(x^2+y^2+z^2\\right)+m(xy+yz+zx)\\right]$. 令 $x=2, y=1, z=0$，得 $5l+2m=15$；令 $x=1, y=0, z=-1$，得 $2l-m=15$；解得 $l=5, m=-5$.",
    "description": "这道题是因式分解讲义中的《轮换式与对称式》的一道题，前序章节（倒序）：待定系数法、余数定理、二元二次式的分解、十字相乘法、...。这道题作为轮换式和待定系数法的综合运用的一道题，接着前序例题进一步展示了齐次的对轮换式与对称式的处理方法。我们需要一道题在此基础上继续提升学生对轮换式与对称式的认识，展示这一方法的强大之处。",
}, ensure_ascii=False, indent=2)}
```

输出：

```json
{json.dumps({
    "question": r"分解因式：$a^5-b^5-(a-b)^5$.",
    "solution": r"原式在 $a,b$ 互换时变号，它不是 $a,b$ 的轮换式. 但是，如果改记 $-b$ 为 $c$，那么原式成为 $a^5+c^5-(a+c)^5$，是 $a,c$ 的轮换式，因而也可以采用前面完全一致的方法去处理. 这里介绍一个更简单的方法，提醒大家做题时可以充分利用化归思想，把问题转换为已经解决的问题. 如果我们在上一道例题中令$y-z=a, z-x=c=-b$，那么 $x-y=b-a$，$a^5-b^5-(a-b)^5 = (y-z)^5+(z-x)^5+(x-y)^5 = 5(x-y)(y-z)(z-x)\\left(x^2+y^2+z^2-xy-yz-zx\\right) = 5ab(a-b)\\left(a^2+b^2-ab\\right)$",
    "description": "这道题通过设置需要代换才能变为轮换式的非轮换式来增加难度，进一步拓展学生对于轮换式处理方法的认知。同时，这道题设计了一个能转化为所提供例题的式子，进一步简化了课堂讲述所需的时间和学生的理解成本，也用此介绍了重要的化归思想。",
}, ensure_ascii=False, indent=2)}
```
"""


def generate_problem(input_info: dict, n_samples: int = 1) -> list:
    """
    根据示例题目生成仿写题目
    
    Args:
        input_info: 包含 audience, target, solution, description 字段的字典
        n_samples: 生成的题目数量
    
    Returns:
        list: 生成的题目列表
    """
    session = DeepSeekChatSession(PROBLEM_GENERATE_PROMPT, model="deepseek-reasoner")
    
    results = []
    for _ in range(n_samples):
        response = session.works(json.dumps(input_info, ensure_ascii=False))
        content = trim(response.choices[0].message.content)
        try:
            result = json.loads(content)
            results.append(result)
        except json.JSONDecodeError:
            results.append({"raw": content})
    
    # 保存结果
    log_path = pathlib.Path(__file__).parent / "log"
    log_path.mkdir(exist_ok=True)
    with open(log_path / f"problem-gen-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json", 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    
    return results


if __name__ == "__main__":
    # 示例输入
    example_input = {
        'audience': "为高中数学竞赛获奖作准备的初中学生",
        'target': r"解方程 $\frac{1}{x(x+2)}+\frac{1}{(x+1)(x+3)}+\cdots+\frac{1}{(x+8)(x+10)}=0$",
        'solution': r"方程两边同时乘以 2 得：$$\frac{2}{x(x+2)}+\frac{2}{(x+1)(x+3)}+\cdots+\frac{2}{(x+8)(x+10)}=0$$ 裂项得 $$\left(\frac{1}{x}-\frac{1}{x+2}\right)+\left(\frac{1}{x+1}-\frac{1}{x+3}\right)+\cdots+\left(\frac{1}{x+8}-\frac{1}{x+10}\right)=0$$ 整理得 $\frac{9}{x(x+9)}=\frac{-9}{(x+1)(x+10)}$，解得 $x=-5 \pm 2 \sqrt{5}$.",
        'description': '这是《分式方程》一节中所选取的例题，前序各章节：《因式分解进阶》（乘法公式、添项拆项、双十字相乘法、换元法、主元法）、《因式定理与待定系数法》、《轮换式与对称式》、《高次方程》。教师反馈："这道题是一道极好的题,如果能找一道类似的就更妙了,其实甚至可以把三次方程求根公式拿出来让学生爽一爽。"注意：你出的题应该明显比给你的例题困难，要涉及高次方程求根，能在讲授时能深化学生对前一道例题的理解，不能被学生一眼直接仿照之前的方法解决。'
    }
    
    print("题目仿写工具")
    print("=" * 50)
    
    use_example = input("使用示例输入？(y/n): ").lower() == 'y'
    
    if use_example:
        input_info = example_input
    else:
        input_info = {
            'audience': input("学段描述 (audience): "),
            'target': input("题目 (target): "),
            'solution': input("解答 (solution): "),
            'description': input("仿写要求 (description): "),
        }
    
    n = int(input("生成数量 (默认 1): ") or "1")
    
    print("\n正在生成题目...")
    results = generate_problem(input_info, n)
    
    print("\n生成结果:")
    for i, r in enumerate(results, 1):
        print(f"\n--- 题目 {i} ---")
        if "question" in r:
            print(f"题目: {r['question']}")
            print(f"解答: {r['solution']}")
            print(f"讲解要点: {r['description']}")
        else:
            print(f"原始输出: {r.get('raw', r)}")

