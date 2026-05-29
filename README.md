# AI PR Reviewer — 多Agent协作代码评审系统

一个由大语言模型驱动的、具备“协作-仲裁”机制的智能代码评审工具。
它模拟真实团队的评审过程，让**安全、性能、逻辑、风格**四位专家并行分析代码变更，
在出现分歧时引入**仲裁 Agent** 统一意见，最终通过 CI/CD 无缝融入开发流程。

---

## 🌟 核心亮点

- **🧠 多Agent协作与仲裁** — 四位专家并行分析，严重分歧自动触发仲裁，降低误报
- **📊 四维结构化报告** — 安全/性能/逻辑/风格独立评审，输出结构化风险列表与改进建议
- **🎯 智能上下文引擎** — 基于 tree-sitter 精准提取变更函数及调用关系，降低 Token 成本
- **✅ 修复验证闭环** — 对比同一 PR 多次提交，标记已修复、新引入、遗留问题
- **⚙️ CI/CD 无缝集成** — 提供 GitHub Action，PR 更新时自动触发，报告回写 PR 评论
- **🌐 多平台支持** — 支持 GitHub / GitLab 双平台 API 适配

---

## 🏗 系统架构

```mermaid
flowchart TD
    Dev[开发者] -->|提交 PR| GitHub[GitHub]
    GitHub -->|Webhook| Action[GitHub Action]
    Action -->|POST /review| API[FastAPI 服务]
    API -->|异步任务| Orchestrator[编排器]
    
    Orchestrator -->|并行调用| SecAgent[安全Agent]
    Orchestrator -->|并行调用| PerfAgent[性能Agent]
    Orchestrator -->|并行调用| LogicAgent[逻辑Agent]
    Orchestrator -->|并行调用| StyleAgent[风格Agent]
    
    SecAgent & PerfAgent & LogicAgent & StyleAgent -->|返回结果| Merger[冲突检测 & 聚合]
    
    Merger -->|有冲突| Arbiter[仲裁Agent]
    Merger -->|无冲突| Final[最终报告]
    Arbiter --> Final
    
    Final -->|存储| SQLite[(SQLite)]
    Final -->|回写评论| GitHub