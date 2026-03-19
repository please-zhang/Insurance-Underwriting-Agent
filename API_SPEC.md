# API 规范与数据结构

## 输入规范

### 投保申请对象（ApplicationInput）

```json
{
  "application_id": "APP-2026-001",
  "applicant": {
    "age": 45,
    "gender": "male",
    "occupation": "office_worker",
    "smoking": false,
    "bmi": 24.5
  },
  "health_conditions": [
    {
      "condition": "hypertension",
      "diagnosed_year": 2020,
      "controlled": true,
      "medication": "amlodipine"
    }
  ],
  "coverage": {
    "product_code": "LIFE-TERM-20",
    "coverage_amount": 500000,
    "coverage_period_years": 20,
    "premium_frequency": "annual"
  },
  "beneficiaries": [
    {
      "relationship": "spouse",
      "percentage": 100
    }
  ]
}
```

**字段说明：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| application_id | string | 是 | 申请唯一标识 |
| applicant.age | int | 是 | 年龄，范围 18-75 |
| applicant.gender | enum | 是 | male / female |
| applicant.occupation | string | 是 | 职业代码，参见 data/rules/occupations.json |
| applicant.smoking | bool | 是 | 是否吸烟 |
| applicant.bmi | float | 否 | 体重指数，范围 10.0-60.0 |
| health_conditions | array | 否 | 既往症列表，可为空数组 |
| coverage.product_code | string | 是 | 产品代码，参见 data/rules/products.json |
| coverage.coverage_amount | int | 是 | 保额（元），最小 10000 |
| coverage.coverage_period_years | int | 是 | 保险期限（年），1-30 |

---

## 输出规范

### 核保决议对象（UnderwritingDecision）

```json
{
  "decision": "APPROVED",
  "risk_level": "MEDIUM",
  "risk_score": 62,
  "reasons": [
    "申请人年龄45岁，属于标准承保范围",
    "高血压已受控，影响评级上调至中风险",
    "不吸烟，正向因素"
  ],
  "missing_info": [],
  "next_steps": [
    "建议加费10%承保",
    "需提供最近12个月血压监测记录"
  ],
  "confidence": 0.87,
  "tool_calls_made": ["rule_checker", "doc_retriever", "risk_scorer", "audit_logger"],
  "processing_time_ms": 3842
}
```

**decision 取值：**

| 值 | 含义 | 触发条件 |
|----|------|---------|
| APPROVED | 标准承保 | 风险评分 < 60，无严重违规 |
| APPROVED_WITH_LOADING | 加费承保 | 风险评分 60-79，有可控风险因素 |
| DECLINED | 拒保 | 风险评分 ≥ 80，或触发一票否决规则 |
| REQUEST_MORE_INFO | 待补充信息 | 必要字段缺失，或需要医疗检查结果 |

---

## Tool 接口规范

### Tool 1：rule_checker

**描述：** 检查申请是否符合核保规则，返回匹配的规则和违规项。

**输入 Schema：**
```json
{
  "name": "rule_checker",
  "description": "检查投保申请是否符合核保规则库中的规定，返回适用规则和违规情况",
  "input_schema": {
    "type": "object",
    "properties": {
      "age": {"type": "integer", "description": "申请人年龄"},
      "health_conditions": {
        "type": "array",
        "items": {"type": "string"},
        "description": "既往症名称列表，如 ['hypertension', 'diabetes']"
      },
      "coverage_amount": {"type": "integer", "description": "申请保额（元）"},
      "product_code": {"type": "string", "description": "产品代码"}
    },
    "required": ["age", "coverage_amount", "product_code"]
  }
}
```

**输出：**
```json
{
  "rules_matched": [
    {"rule_id": "R001", "description": "年龄在18-65范围内，标准承保", "impact": "positive"},
    {"rule_id": "R042", "description": "高血压受控，可承保但需加费", "impact": "negative"}
  ],
  "violations": [],
  "hard_stops": []
}
```

`hard_stops` 非空则直接 DECLINED，不继续评分。

---

### Tool 2：doc_retriever

**描述：** 从保险产品文档中检索相关条款。

**输入 Schema：**
```json
{
  "name": "doc_retriever",
  "description": "从保险产品说明书和条款文档中检索与申请相关的内容",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": {"type": "string", "description": "检索查询，如'高血压承保条件'"},
      "product_code": {"type": "string", "description": "产品代码，限定检索范围"},
      "top_k": {"type": "integer", "description": "返回结果数量，默认3", "default": 3}
    },
    "required": ["query"]
  }
}
```

**输出：**
```json
{
  "passages": [
    {
      "content": "第十二条 被保险人患有以下疾病者，需提供...",
      "source": "产品说明书第3章",
      "relevance_score": 0.89
    }
  ]
}
```

---

### Tool 3：risk_scorer

**描述：** 基于规则检查结果计算综合风险分数。

**输入 Schema：**
```json
{
  "name": "risk_scorer",
  "description": "根据规则匹配结果和申请信息计算综合风险评分（0-100分，分越高风险越大）",
  "input_schema": {
    "type": "object",
    "properties": {
      "rule_checker_result": {
        "type": "object",
        "description": "rule_checker 工具的完整输出结果"
      },
      "age": {"type": "integer"},
      "smoking": {"type": "boolean"},
      "bmi": {"type": "number"}
    },
    "required": ["rule_checker_result", "age"]
  }
}
```

**输出：**
```json
{
  "risk_score": 62,
  "risk_level": "MEDIUM",
  "score_breakdown": {
    "age_factor": 5,
    "health_factor": 30,
    "lifestyle_factor": 0,
    "product_factor": 10,
    "base_score": 17
  }
}
```

---

### Tool 4：audit_logger

**描述：** 记录核保审查日志，供合规和追溯使用。

**输入 Schema：**
```json
{
  "name": "audit_logger",
  "description": "将核保处理过程记录到审核日志，用于合规追溯",
  "input_schema": {
    "type": "object",
    "properties": {
      "application_id": {"type": "string"},
      "preliminary_decision": {
        "type": "string",
        "enum": ["APPROVED", "APPROVED_WITH_LOADING", "DECLINED", "REQUEST_MORE_INFO"]
      },
      "risk_score": {"type": "integer"},
      "tools_used": {"type": "array", "items": {"type": "string"}},
      "summary": {"type": "string", "description": "一句话描述核保判断依据"}
    },
    "required": ["application_id", "preliminary_decision", "risk_score"]
  }
}
```

**输出：**
```json
{
  "log_id": "LOG-20260319-001",
  "timestamp": "2026-03-19T10:30:00Z",
  "status": "recorded"
}
```

---

## 错误码规范

| 错误码 | 说明 | 建议处理 |
|--------|------|---------|
| E001 | LLM API 调用失败（超时/限流） | 重试，最多3次 |
| E002 | JSON 解析失败，兜底重试耗尽 | 返回 REQUEST_MORE_INFO |
| E003 | 必填字段缺失 | 返回 REQUEST_MORE_INFO + missing_info 列表 |
| E004 | 产品代码不存在 | 抛出 ValueError |
| E005 | 向量库未初始化 | doc_retriever 返回空，不中断流程 |
| E006 | 规则库文件损坏 | 抛出 RuntimeError，停止处理 |
