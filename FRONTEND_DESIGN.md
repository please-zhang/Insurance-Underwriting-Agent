# Design System — 核保工作流 Agent 前端展示页

## Product Context
- **What this is:** AI 核保工作流展示/演示页面，可视化展示投保申请从进入系统到 AI 决策输出的完整流程
- **Who it's for:** 业务方、技术同行、投资人 — 需要直观理解 AI 核保系统工作原理的人
- **Space/industry:** 保险科技 (InsurTech) / AI Agent 工作流可视化
- **Project type:** 展示/演示页面 (Showcase / Demo Page)
- **Language:** 中英混合 — 中文界面，英文技术术语和代码注释

## Aesthetic Direction
- **Direction:** Industrial/Utilitarian 工业/功能主义
- **Decoration level:** Intentional 有意图的 — 微妙的网格背景纹理呼应 Agent 节点图架构
- **Mood:** 任务控制中心 — 你在看一个智能系统实时运转。专业、沉稳、有技术深度，但不枯燥。
- **Reference sites:** Cytora, Insurity, LangGraph Studio

## Typography
- **Display/Hero:** Satoshi (英文) + Noto Sans SC/思源黑体 (中文) — 几何感、现代、自信
- **Body:** DM Sans + Noto Sans SC — 可读性极佳，专业
- **UI/Labels:** Same as body
- **Data/Tables:** JetBrains Mono — 支持 tabular-nums，用于 JSON 数据展示、风险分数、工具调用日志
- **Code:** JetBrains Mono
- **Loading:**
  - Google Fonts: `https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&family=Noto+Sans+SC:wght@300;400;500;600;700&display=swap`
  - Fontshare: `https://api.fontshare.com/v2/css?f[]=satoshi@400,500,700,900&display=swap`
- **Scale:**
  - Hero: 72px / weight 900 / line-height 1.1 / letter-spacing -0.02em
  - H1: 48px / weight 700
  - H2: 28px / weight 700
  - H3: 20px / weight 700
  - Card Title: 16px / weight 600
  - Body: 16px / weight 400 / line-height 1.7
  - Small: 14px / weight 400
  - Caption: 12px / weight 400
  - Mono Label: 11px / weight 500 / letter-spacing 0.06-0.1em / uppercase

## Color
- **Approach:** Restrained 克制型 — 浅色主题，仅浅色模式
- **Primary Accent:** #0891B2 (Cyan-600) — 代表"处理中"、系统能量流动，用于强调按钮、活跃状态、链接
- **Neutrals:**
  - Background: #F8FAFC (Slate-50)
  - Surface/Card: #FFFFFF
  - Elevated: #F1F5F9 (Slate-100)
  - Border: #E2E8F0 (Slate-200)
  - Border Subtle: #F1F5F9 (Slate-100)
  - Text Primary: #0F172A (Slate-900)
  - Text Secondary: #475569 (Slate-600)
  - Text Muted: #94A3B8 (Slate-400)
- **Semantic:**
  - Success: #059669 (Emerald-600) — 标准承保、核保通过
  - Warning: #D97706 (Amber-600) — 风险提示、人工复核
  - Error: #DC2626 (Red-600) — 拒保、规则不通过
  - Info: #2563EB (Blue-600) — 处理中、信息提示
- **Dim variants (backgrounds):**
  - Accent dim: rgba(8, 145, 178, 0.08)
  - Success dim: rgba(5, 150, 105, 0.08)
  - Warning dim: rgba(217, 119, 6, 0.08)
  - Error dim: rgba(220, 38, 38, 0.08)
  - Info dim: rgba(37, 99, 235, 0.08)

## Spacing
- **Base unit:** 8px
- **Density:** Comfortable 舒适 — 展示页需要呼吸感
- **Scale:** 2xs(2) xs(4) sm(8) md(16) lg(24) xl(32) 2xl(48) 3xl(64)

## Layout
- **Approach:** Hybrid 混合式 — 主工作流可视化用叙事/编辑式布局（滚动讲故事），数据展示区域用严格栅格
- **Max content width:** 1120px
- **Grid:** Responsive, auto-fit with minmax
- **Border radius:**
  - sm: 4px — 小元素（badge、代码块）
  - md: 8px — 常规组件（按钮、输入框、卡片内元素）
  - lg: 12px — 大容器（卡片、面板、模态框）
  - full: 9999px — 药丸形状（tag、状态标签）

## Motion
- **Approach:** Intentional 有意图的 — 动画是核心体验，工作流节点依次亮起，数据在节点间流动
- **Easing:**
  - Enter: cubic-bezier(0, 0, 0.2, 1) — ease-out
  - Exit: cubic-bezier(0.4, 0, 1, 1) — ease-in
  - Move: cubic-bezier(0.4, 0, 0.2, 1) — ease-in-out
- **Duration:**
  - Micro: 50-100ms (80ms default) — hover 状态、微交互
  - Short: 150-250ms (200ms default) — 按钮点击、输入框聚焦
  - Medium: 250-400ms (350ms default) — 卡片展开、面板切换
  - Long: 400-700ms (500ms default) — 页面转场、工作流节点动画
- **Key animations:**
  - 工作流节点依次亮起 (sequential node activation)
  - 数据包在节点间流动 (data packet flow between nodes)
  - 风险分数仪表盘渐变 (risk score gauge fill)
  - 最终决策揭晓效果 (decision reveal)
  - 脉冲点动画 (pulse dot for active status)

## CSS Custom Properties Reference

```css
:root {
  /* Fonts */
  --font-display: 'Satoshi', 'Noto Sans SC', sans-serif;
  --font-body: 'DM Sans', 'Noto Sans SC', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;

  /* Spacing */
  --space-2xs: 2px;
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;
  --space-2xl: 48px;
  --space-3xl: 64px;

  /* Radius */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-full: 9999px;

  /* Motion */
  --ease-enter: cubic-bezier(0, 0, 0.2, 1);
  --ease-exit: cubic-bezier(0.4, 0, 1, 1);
  --ease-move: cubic-bezier(0.4, 0, 0.2, 1);
  --dur-micro: 80ms;
  --dur-short: 200ms;
  --dur-medium: 350ms;
  --dur-long: 500ms;

  /* Colors */
  --bg: #F8FAFC;
  --bg-elevated: #FFFFFF;
  --bg-surface: #F1F5F9;
  --border: #E2E8F0;
  --border-subtle: #F1F5F9;
  --text-primary: #0F172A;
  --text-secondary: #475569;
  --text-muted: #94A3B8;
  --accent: #0891B2;
  --accent-dim: rgba(8, 145, 178, 0.08);
  --accent-glow: rgba(8, 145, 178, 0.15);
  --warning: #D97706;
  --warning-dim: rgba(217, 119, 6, 0.08);
  --success: #059669;
  --success-dim: rgba(5, 150, 105, 0.08);
  --error: #DC2626;
  --error-dim: rgba(220, 38, 38, 0.08);
  --info: #2563EB;
  --info-dim: rgba(37, 99, 235, 0.08);
}
```

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-24 | 仅浅色模式 | 用户明确要求去掉深色模式，只保留浅色 |
| 2026-03-24 | Industrial/Utilitarian 美学 | 保险（专业信任）+ AI 技术（现代动态）的交叉点，"任务控制中心"感 |
| 2026-03-24 | Satoshi + Noto Sans SC 字体 | 几何感现代，中英文搭配和谐，避免 Inter/Roboto 等过度使用的字体 |
| 2026-03-24 | #0891B2 Cyan 强调色 | 代表系统能量流动，在浅色背景上对比度好，与金融信任色调一致 |
| 2026-03-24 | 动态节点图为核心体验 | 展示页的灵魂是"看 AI 工作"，动画是核心而非装饰 |
| 2026-03-24 | 中英混合语言 | 中文界面适合目标受众，英文技术术语保持专业性 |
| 2026-03-24 | 初始前端设计系统创建 | Created by /design-consultation based on 保险科技行业调研 + 工作流可视化最佳实践 |
