# 设计决策文档

记录关键设计选择和背后的理由，供后续维护和面试讲解使用。

## 决策 1：test_model_parity 测试的设计思路



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
---

## 数据安全设计说明

本项目**只使用仿真数据**，不包含任何真实投保人信息。

仿真数据生成原则：
- 姓名使用随机生成（faker 库）
- 年龄、健康状况基于公开的保险精算分布随机生成
- 保额、险种基于市场上公开产品设定
- 不使用任何来自公司内部系统的真实数据

