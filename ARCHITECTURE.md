# 架构设计文档

## 核心架构原则

1. **模型无关（Model-Agnostic）**：业务逻辑与 LLM 提供方完全解耦
2. **Tool-First**：Agent 能力通过 Tool 扩展，不在 prompt 里硬编码逻辑
3. **防御性输出解析**：不假设 LLM 输出格式完全可靠
4. **并行优先**：无依赖的 Tool 并行执行，有依赖的串行

---

## 整体数据流

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户输入层                               │
│  CLI / API  →  投保申请摘要 (JSON / 自然语言)                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      OrchestratorAgent                           │
│                                                                  │
│  1. 解析申请，提取关键字段                                        │
│  2. 规划核查步骤（让 LLM 决定调用哪些 Tool）                     │
│  3. 调度 Tool 执行（并行/串行）                                   │
│  4. 汇总 Tool 结果，生成最终核保意见                             │
│  5. 调用 StructuredParser 确保输出为合法 JSON                    │
└──────────┬───────────────────────────────────────────┬──────────┘
           │                                           │
           │  Tool 调用（并行）                        │  结构化输出
           ▼                                           ▼
┌──────────────────────┐              ┌─────────────────────────────┐
│      Tool 层          │              │      Output 层               │
│                      │              │                             │
│ ┌──────────────────┐ │              │ UnderwritingDecision {      │
│ │ rule_checker     │ │              │   decision: APPROVED        │
│ │ 查询核保规则库    │ │              │            | DECLINED       │
│ └──────────────────┘ │              │            | REQUEST_INFO   │
│ ┌──────────────────┐ │              │   risk_level: LOW|MED|HIGH  │
│ │ doc_retriever    │ │              │   reasons: [...]            │
│ │ RAG检索产品文档  │ │              │   missing_info: [...]       │
│ └──────────────────┘ │              │   next_steps: [...]        │
│ ┌──────────────────┐ │              │   confidence: 0.0-1.0      │
│ │ risk_scorer      │ │              │ }                           │
│ │ 规则引擎风险评分 │ │              └─────────────────────────────┘
│ └──────────────────┘ │
│ ┌──────────────────┐ │
│ │ audit_logger     │ │
│ │ 写入审核日志     │ │
│ └──────────────────┘ │
└──────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LLMProvider 层（关键隔离层）                 │
│                                                                  │
│  LLMProvider (abstract)                                          │
│  ├── ClaudeProvider   → Anthropic API（外网）                   │
│  ├── OpenAIProvider   → OpenAI API（备选）                      │
│  └── GLM4Provider     → 本地部署 HTTP API（内网）               │
│                                                                  │
│  切换方式：仅修改 config/providers.yaml，代码零改动              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 核心组件详解

### 1. OrchestratorAgent (`agent/orchestrator.py`)

**职责：** 整个 Agent 的大脑，负责规划和调度。

**执行流程：**

```
Step 1: 构建系统 Prompt（包含核保规则概要 + 可用 Tool 列表）
    ↓
Step 2: 发送申请到 LLM，LLM 返回 Tool 调用计划
    ↓
Step 3: 解析 Tool 调用请求
    ↓
Step 4: 分组执行（无依赖的并行，有依赖的串行）
    ↓
    ├── 并行组1: [rule_checker, doc_retriever]  ← 无依赖，并行
    └── 串行组2: risk_scorer(依赖rule_checker结果) → audit_logger
    ↓
Step 5: 将所有 Tool 结果返回给 LLM
    ↓
Step 6: LLM 生成最终核保意见
    ↓
Step 7: StructuredParser 解析并验证 JSON 输出
    ↓
Step 8: 返回 UnderwritingDecision 对象
```

**关键方法：**
```python
class OrchestratorAgent:
    async def process(self, application: dict) -> UnderwritingDecision
    async def _execute_tools_parallel(self, tool_calls: list) -> list
    async def _execute_tools_sequential(self, tool_calls: list) -> list
    def _build_system_prompt(self) -> str
```

---

### 2. Tool 层 (`agent/tools/`)

所有 Tool 继承 `BaseTool`，实现统一接口：

```python
class BaseTool:
    name: str           # Tool 名称（与 LLM 对话中的 tool_name 一致）
    description: str    # Tool 描述（LLM 据此决定何时调用）
    input_schema: dict  # JSON Schema（Claude Tool Use 格式）

    async def execute(self, **kwargs) -> dict  # 核心方法
```

**各 Tool 说明：**

| Tool | 输入 | 输出 | 实现方式 |
|------|------|------|---------|
| `rule_checker` | applicant_age, health_conditions[], coverage_amount | rules_matched[], violations[] | 查询 JSON 规则库，精确匹配 |
| `doc_retriever` | query: str, top_k: int | relevant_passages[], sources[] | 向量检索（ChromaDB 本地），文档来自 data/docs/ |
| `risk_scorer` | rule_violations[], health_score | risk_level, risk_score(0-100), factors[] | 加权规则引擎，纯 Python 计算，不依赖 LLM |
| `audit_logger` | application_id, decision, reasons[] | log_id, timestamp | 写入本地 JSONL 文件，data/audit/audit.jsonl |

---

### 3. LLMProvider 层 (`providers/`)

**抽象接口：**

```python
class LLMProvider(ABC):
    @abstractmethod
    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: str = ""
    ) -> LLMResponse

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        system: str = ""
    ) -> str
```

**ClaudeProvider：** 使用 `anthropic` SDK，原生支持 Tool Use，直接映射。

**GLM4Provider：** GLM4.7 通过 OpenAI 兼容的 HTTP API 暴露。Tool Use 能力较弱，采用以下策略：
- 优先尝试 `tools` 参数（如 GLM4 版本支持）
- 如不支持，降级为 prompt 内嵌 Tool 描述 + 结构化输出要求
- 结果交给 `StructuredParser` 统一处理

**配置示例（config/providers.yaml）：**

```yaml
active_provider: claude   # 切换这里：claude | glm4 | openai

claude:
  api_key: ${ANTHROPIC_API_KEY}
  model: claude-opus-4-6
  max_tokens: 4096
  timeout: 30

glm4:
  base_url: http://192.168.x.x:8080/v1   # 内网地址
  api_key: none
  model: glm-4
  max_tokens: 2048
  timeout: 60   # 内网模型推理慢，超时设长

openai:
  api_key: ${OPENAI_API_KEY}
  model: gpt-4o
  max_tokens: 4096
  timeout: 30
```

---

### 4. Output 层 (`agent/output/`)

**数据模型（`models.py`，基于 Pydantic）：**

```python
class UnderwritingDecision(BaseModel):
    decision: Literal["APPROVED", "DECLINED", "REQUEST_MORE_INFO"]
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    risk_score: int           # 0-100
    reasons: list[str]        # 决策理由列表
    missing_info: list[str]   # 缺失信息（REQUEST_MORE_INFO 时使用）
    next_steps: list[str]     # 建议的下一步操作
    confidence: float         # 0.0-1.0，模型对决策的置信度
    tool_calls_made: list[str] # 本次用了哪些 Tool（可追溯）
    processing_time_ms: int   # 处理耗时（性能监控）
```

**解析兜底层（`parser.py`）：**

```
尝试1: 直接 json.loads()
    ↓ 失败
尝试2: 提取 ```json ... ``` 代码块后 json.loads()
    ↓ 失败
尝试3: 正则提取 { ... } 最大块后 json.loads()
    ↓ 失败
尝试4: 发送给 LLM "请将以下文本转为规定的 JSON 格式" + 原始输出
    ↓ 失败（超过最大重试次数）
抛出 ParseError，返回 fallback 兜底决策（REQUEST_MORE_INFO + 错误信息）
```

---

## 并行执行设计

```python
# Tool 依赖关系（在 orchestrator 中定义）
TOOL_DEPENDENCIES = {
    "rule_checker": [],           # 无依赖，可并行
    "doc_retriever": [],          # 无依赖，可并行
    "risk_scorer": ["rule_checker"],  # 依赖 rule_checker 结果
    "audit_logger": ["risk_scorer"],  # 最后执行
}

# 执行顺序（拓扑排序后）：
# Round 1（并行）: rule_checker, doc_retriever
# Round 2（并行）: risk_scorer（依赖 rule_checker 完成）
# Round 3: audit_logger（依赖 risk_scorer 完成）
```

---

## 缓存设计（应对 GLM4.7 慢响应）

- 缓存层：`functools.lru_cache` 或本地文件缓存（data/cache/）
- 缓存 key：`hash(application_json + provider_name)`
- 缓存 TTL：24小时（核保规则每日更新）
- 仅缓存最终决策，不缓存中间 Tool 结果
- 可通过 `--no-cache` 参数强制跳过

---

## 错误处理策略

| 错误类型 | 处理方式 |
|---------|---------|
| LLM API 超时 | 重试3次，指数退避，最终抛出带上下文的异常 |
| Tool 执行失败 | 标记该 Tool 结果为 error，继续执行其他 Tool，在最终输出中注明 |
| JSON 解析失败 | 走解析兜底层（见上），最终返回 REQUEST_MORE_INFO |
| 向量库为空 | doc_retriever 返回空结果，不中断流程 |
| GLM4 不支持 Tool Use | 自动降级为 prompt 内嵌模式 |
