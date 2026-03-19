# 设计决策文档

记录关键设计选择和背后的理由，供后续维护和面试讲解使用。

---

## 决策 1：为什么不用 LangChain？

**选择：** 直接使用 Claude SDK 原生 Tool Use + 手写 Orchestrator

**理由：**
- LangChain 抽象层过重，调试困难，面试时被追问底层时容易露底
- Claude SDK 的 Tool Use API 足够清晰，100行代码可以实现完整的 Orchestrator
- 减少依赖 = 减少版本地狱 = 在内网环境更容易部署
- 自己写的代码，每一行都能解释清楚

**代价：** 需要自己处理 Tool 调度逻辑（并行/串行），但这反而是面试亮点。

---

## 决策 2：为什么选 Python 而不是 Java？

**背景：** 项目作者是 9 年 Java 背景，Java 更熟悉。

**选择：** Python

**理由：**
- AI Agent 生态在 Python 侧成熟度领先 Java 约 2 年
- Claude SDK、向量库（ChromaDB）、Pydantic 等工具在 Python 侧最完整
- 面试 AI Agent 岗位时，Python 是默认预期；用 Java 反而需要额外解释
- Python 对 9 年 Java 工程师的学习曲线：2-3天入门，1周写出工程质量代码

**对 Java 背景的说法：**
> "我有9年Java经验，但这个项目选了Python，因为Agent生态在Python侧更成熟。
> 我认为工程师应该选最合适的工具，而不是最熟悉的工具。"

---

## 决策 3：模型无关架构的设计动机

**背景：** 作者在金融内网工作，外网用 Claude，内网只能用 GLM4.7。

**选择：** LLMProvider 抽象接口 + 配置驱动切换

**理由：**
- 这正是所有金融、政府、医疗行业 AI 落地的真实约束
- 提前设计进去，比事后改造成本低 10 倍
- 面试亮点：展示了对企业级 AI 部署约束的真实理解

**实现要点：**
```python
# 错误做法：在业务代码里直接 import anthropic
import anthropic
client = anthropic.Anthropic()  # 硬耦合

# 正确做法：通过接口解耦
from providers import get_provider
provider = get_provider(config["active_provider"])  # 配置驱动
```

---

## 决策 4：为什么用 Pydantic 做输出模型？

**选择：** Pydantic v2 定义 `UnderwritingDecision`

**理由：**
- 自动验证 LLM 输出的字段类型和取值范围
- 序列化/反序列化零代码
- 与 FastAPI 天然兼容（未来如需暴露 HTTP API 可直接用）
- 错误信息清晰，调试友好

---

## 决策 5：向量检索用 ChromaDB（而不是 Faiss 或云服务）

**选择：** ChromaDB 本地模式

**理由：**
- 本地文件存储，无需部署服务，`pip install chromadb` 即可
- 内网环境无法访问云向量数据库（Pinecone、Weaviate 等）
- 数据量小（保险产品说明书 < 10MB），本地 ChromaDB 性能完全够用
- 面试中可以说"我考虑了内网部署约束，选择了可以本地运行的向量库"

---

## 决策 6：test_model_parity 测试的设计思路

**这是本项目最有价值的测试，面试必讲。**

**设计思路：**
```python
# 同一份申请，用两个模型分别跑
# 验证：decision（核心结论）必须一致
# 允许：risk_score 有小幅差异（模型差异造成的）
# 允许：reasons 文字不同（但含义应相近）

def test_model_parity():
    application = load_sample_application()

    claude_result = run_with_claude(application)
    glm4_result = run_with_glm4(application)

    # 核心结论必须一致
    assert claude_result.decision == glm4_result.decision

    # 风险等级必须一致
    assert claude_result.risk_level == glm4_result.risk_level

    # 风险分数差异不超过 20 分
    assert abs(claude_result.risk_score - glm4_result.risk_score) <= 20
```

**面试话术：**
> "在金融 AI 合规中，我们不能接受同一份申请在不同环境下给出不同结论。
> 所以我专门设计了模型一致性测试，用来验证两个模型在关键决策上的一致性。
> 这个测试同时也是我们的回归测试——每次更换模型版本都要跑。"

---

## 数据安全设计说明

本项目**只使用仿真数据**，不包含任何真实投保人信息。

仿真数据生成原则：
- 姓名使用随机生成（faker 库）
- 年龄、健康状况基于公开的保险精算分布随机生成
- 保额、险种基于市场上公开产品设定
- 不使用任何来自公司内部系统的真实数据

这是故意设计的：**项目本身证明了如何在合规约束下做 AI 开发**。
