# DevFlow Observability Dashboard — 视觉设计文档

> 本设计文档定义了仪表板的视觉风格、布局结构和交互模式。以 "Pipeline 流动感" 为核心概念，打造具有 DevFlow 品牌辨识度的深色科技风界面。

---

## 1. 设计理念

### 核心隐喻：数据流水线
DevFlow 的本质是 **Pipeline** —— 需求像液体一样在阶段间流动。仪表板的视觉语言应强化这一隐喻：
- **流动感**：使用微妙的渐变、微光和动画暗示数据在管道中流动
- **节点状态**：每个 Pipeline 阶段如同一个处理节点，用发光效果表示活跃状态
- **深度层次**：使用玻璃态（Glassmorphism）和阴影创造空间深度，暗示系统的分层架构

### 情绪板
- **科技感**：深色背景 + 霓虹点缀，类似现代 DevOps 工具（Grafana、Datadog）
- **专业感**：克制的色彩使用，信息密度高但不杂乱
- **活力感**：动态数据刷新时的微动画，让面板"活"起来

---

## 2. 色彩系统

### 主色调（深色模式）
| Token | 值 | 用途 |
|-------|-----|------|
| `--bg-primary` | `#0a0e1a` | 页面主背景（极深蓝黑） |
| `--bg-secondary` | `#111827` | 卡片背景（深灰蓝） |
| `--bg-tertiary` | `#1f2937` | 悬浮、选中状态 |
| `--border-subtle` | `rgba(255,255,255,0.08)` | 微妙边框 |
| `--border-glow` | `rgba(56, 189, 248, 0.3)` | 发光边框（活跃状态） |

### 强调色（霓虹渐变）
| Token | 值 | 用途 |
|-------|-----|------|
| `--accent-cyan` | `#22d3ee` | 主要强调色（阶段流动、KPI） |
| `--accent-purple` | `#a78bfa` | 次要强调色（Token 消耗、图表系列） |
| `--accent-green` | `#34d399` | 成功状态 |
| `--accent-amber` | `#fbbf24` | 警告、等待审批状态 |
| `--accent-red` | `#f87171` | 失败状态 |

### 渐变定义
```css
/* Pipeline 流动渐变 - 用于头部和活跃元素 */
--gradient-flow: linear-gradient(135deg, #22d3ee 0%, #a78bfa 50%, #f472b6 100%);

/* 卡片顶部微光 */
--gradient-shimmer: linear-gradient(90deg, transparent, rgba(34,211,238,0.1), transparent);

/* KPI 卡片背景渐变 */
--gradient-kpi-1: linear-gradient(135deg, rgba(34,211,238,0.15), rgba(34,211,238,0.05));
--gradient-kpi-2: linear-gradient(135deg, rgba(167,139,250,0.15), rgba(167,139,250,0.05));
--gradient-kpi-3: linear-gradient(135deg, rgba(52,211,153,0.15), rgba(52,211,153,0.05));
--gradient-kpi-4: linear-gradient(135deg, rgba(251,191,36,0.15), rgba(251,191,36,0.05));
```

---

## 3. 布局结构

### 整体架构
```
┌─────────────────────────────────────────────────────────────┐
│  Header (品牌标识 + 全局状态指示器)                            │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ KPI 1   │ │ KPI 2   │ │ KPI 3   │ │ KPI 4   │           │
│  │ 总运行   │ │ 成功率   │ │ 活跃运行 │ │ 待审批   │           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────────┐  ┌──────────────────────────┐     │
│  │   阶段耗时分布图      │  │   24小时运行趋势图        │     │
│  │   (BarChart)         │  │   (AreaChart)            │     │
│  └──────────────────────┘  └──────────────────────────┘     │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Token 消耗趋势 (LineChart)                │  │
│  └───────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────┐  │
│  │              最近 Pipeline 运行列表 (Table)             │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 响应式断点
| 断点 | 布局变化 |
|------|----------|
| `>= 1280px` | 4 列 KPI，2 列图表并排，完整表格 |
| `>= 1024px` | 4 列 KPI，2 列图表并排，紧凑表格 |
| `>= 768px` | 2 列 KPI，图表堆叠，紧凑表格 |
| `< 768px` | 1 列 KPI，图表堆叠，卡片式运行列表 |

---

## 4. 组件设计

### 4.1 Header 区域
- **高度**: `64px`
- **背景**: `--bg-secondary` + 底部 `1px` 边框 `--border-subtle`
- **左侧**: DevFlow 品牌标识（文字 Logo + 流动渐变下划线动画）
- **右侧**: 
  - 实时状态指示器（脉冲绿点 + "系统正常运行" 文字）
  - 最后刷新时间戳
  - 刷新按钮（旋转图标动画）

### 4.2 KPI 卡片
- **尺寸**: 等宽 4 列，高度 `120px`
- **背景**: 各卡片使用不同的 `--gradient-kpi-*` 渐变
- **边框**: `1px solid --border-subtle`，圆角 `12px`
- **悬浮效果**: 边框变为 `--border-glow`，卡片微微上移 `-2px`，阴影增强
- **内容布局**:
  - 顶部：图标（Lucide icon）+ 标签文字
  - 中部：大字号数值（`32px`，白色，font-weight 700）
  - 底部：变化趋势（绿色上升箭头 + 百分比，或红色下降）
- **特色**: 卡片顶部有一条 `2px` 的流动渐变线条，使用 CSS animation 实现从左到右的 shimmer 效果

### 4.3 图表卡片
- **背景**: `--bg-secondary`
- **边框**: `1px solid --border-subtle`，圆角 `16px`
- **标题区**: 左侧标题文字 + 右侧图例/控制按钮
- **图表区**: 内边距 `16px`，使用 Recharts 自定义主题色
- **Recharts 主题配置**:
  ```typescript
  const chartTheme = {
    background: 'transparent',
    textColor: '#9ca3af',
    axisColor: 'rgba(255,255,255,0.1)',
    gridColor: 'rgba(255,255,255,0.05)',
    colors: ['#22d3ee', '#a78bfa', '#34d399', '#fbbf24', '#f472b6'],
  };
  ```

### 4.4 Pipeline 阶段可视化（运行详情弹窗）
- **设计**: 水平流程图，每个阶段是一个节点
- **节点样式**:
  - `pending`: 灰色空心圆
  - `running`: 青色发光圆 + 旋转加载环
  - `success`: 绿色实心圆 + 白色对勾
  - `failed`: 红色实心圆 + 白色叉号
  - `blocked`: 黄色实心圆 + 白色感叹号
- **连接线**:
  - 已完成阶段之间：实线，使用渐变 `--gradient-flow`
  - 当前进行中的连接：虚线，青色脉冲动画
  - 未开始的连接：虚线，灰色

### 4.5 运行列表表格
- **表头**: `--bg-tertiary` 背景，文字灰色，字体较小
- **行样式**: 
  - 默认：`--bg-secondary` 背景
  - 悬浮：`--bg-tertiary` 背景 + 左侧 `3px` 青色边框
  - 斑马纹：偶数行略微变暗
- **状态标签**: 使用 Badge 组件，圆角全角，带微妙背景色
  - `running`: 青色背景 + 青色文字 + 脉冲动画点
  - `success`: 绿色背景 + 绿色文字
  - `failed`: 红色背景 + 红色文字
  - `paused`: 黄色背景 + 黄色文字
- **操作列**: "查看详情" 按钮，悬浮时显示流动渐变背景

### 4.6 运行详情弹窗 (Dialog)
- **尺寸**: `max-width: 900px`，高度自适应，最大 `85vh`
- **背景**: `--bg-secondary` + `backdrop-filter: blur(12px)`
- **边框**: `1px solid --border-glow`
- **内容分区**:
  1. **头部**: 运行 ID + 关闭按钮
  2. **Pipeline 流程图**: 水平阶段可视化
  3. **指标网格**: 2x2 网格展示耗时、Token、阶段数、检查点状态
  4. **时间线**: 垂直时间线，左侧时间戳，右侧事件卡片
  5. **原始日志**: Collapsible 折叠面板，JSON 语法高亮

---

## 5. 动画与交互

### 5.1 入场动画
- KPI 卡片：依次从下方滑入 + 淡入，间隔 `100ms`
- 图表：从透明淡入，持续 `500ms`
- 表格行：依次淡入，间隔 `30ms`

### 5.2 数据刷新动画
- KPI 数值变化：数字滚动动画（从旧值滚动到新值）
- 图表数据更新：平滑过渡动画
- 刷新按钮：旋转动画（刷新期间）

### 5.3 悬浮交互
- KPI 卡片：上移 `2px` + 发光边框
- 表格行：左侧出现青色指示条
- 按钮：背景渐变流动

### 5.4 特殊效果
- **Pipeline 流动线条**: 使用 CSS `@keyframes` 实现渐变位置的循环移动
- **活跃状态脉冲**: `running` 状态使用 `box-shadow` 脉冲动画
- **Shimmer 效果**: 卡片顶部的微光线条从左到右扫过

---

## 6. 字体与排版

| 元素 | 字体 | 大小 | 字重 | 颜色 |
|------|------|------|------|------|
| 页面标题 | system-ui | `24px` | 700 | 白色 |
| 卡片标题 | system-ui | `14px` | 500 | `#9ca3af` |
| KPI 数值 | system-ui | `32px` | 700 | 白色 |
| KPI 标签 | system-ui | `12px` | 400 | `#6b7280` |
| 表格文字 | system-ui | `13px` | 400 | `#d1d5db` |
| 状态标签 | system-ui | `11px` | 600 | 按状态色 |
| 时间戳 | monospace | `12px` | 400 | `#6b7280` |

---

## 7. 空状态设计

当没有运行数据时：
- **图标**: 一个静态的 Pipeline 流程图轮廓（灰色虚线）
- **文字**: "暂无 Pipeline 运行数据"
- **副文字**: "启动一个 DevFlow Pipeline 后，数据将在此显示"
- **CTA**: 引导用户查看 API 文档或启动 Pipeline 的提示

---

## 8. 与 shadcn/ui 的整合

### 需要安装的 shadcn/ui 组件
```bash
npx shadcn add card
npx shadcn add badge
npx shadcn add button
npx shadcn add dialog
npx shadcn add table
npx shadcn add scroll-area
npx shadcn add collapsible
npx shadcn add skeleton
npx shadcn add separator
```

### 主题覆盖
在 `dashboard/src/index.css` 中覆盖 shadcn/ui 默认变量：
```css
@layer base {
  :root {
    --background: 222 47% 5%; /* #0a0e1a */
    --foreground: 210 40% 98%;
    --card: 222 47% 7%; /* #111827 */
    --card-foreground: 210 40% 98%;
    --popover: 222 47% 7%;
    --popover-foreground: 210 40% 98%;
    --primary: 189 94% 53%; /* #22d3ee */
    --primary-foreground: 222 47% 5%;
    --secondary: 217 33% 17%; /* #1f2937 */
    --secondary-foreground: 210 40% 98%;
    --muted: 217 33% 17%;
    --muted-foreground: 215 20% 65%;
    --accent: 217 33% 17%;
    --accent-foreground: 210 40% 98%;
    --destructive: 0 84% 60%;
    --destructive-foreground: 210 40% 98%;
    --border: 215 28% 17%;
    --input: 215 28% 17%;
    --ring: 189 94% 53%;
    --radius: 0.75rem;
  }
}
```

---

## 9. 文件结构

```
dashboard/
├── src/
│   ├── index.css              # 全局样式 + Tailwind + shadcn 主题覆盖
│   ├── App.tsx                # 主布局组件
│   ├── main.tsx               # 入口
│   ├── hooks/
│   │   └── useMetrics.ts      # 数据获取 hooks + 轮询
│   ├── components/
│   │   ├── Header.tsx         # 顶部导航栏
│   │   ├── KpiCards.tsx       # KPI 卡片网格
│   │   ├── StageStatsChart.tsx    # 阶段耗时柱状图
│   │   ├── RunsTrendChart.tsx     # 24小时趋势面积图
│   │   ├── TokenUsageChart.tsx    # Token 消耗折线图
│   │   ├── RecentRunsTable.tsx    # 最近运行列表
│   │   ├── RunDetailDialog.tsx    # 运行详情弹窗
│   │   ├── PipelineFlow.tsx       # Pipeline 流程可视化
│   │   ├── Timeline.tsx           # 时间线组件
│   │   └── EmptyState.tsx         # 空状态
│   └── lib/
│       └── utils.ts           # cn() 工具函数
├── public/
├── index.html
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
├── components.json
└── package.json
```
