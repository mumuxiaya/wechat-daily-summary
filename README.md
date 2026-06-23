# wechat-daily-summary

微信群聊/私聊每日摘要生成器 — 通过 [wechat-cli](https://github.com/huohuoer/wechat-cli) 读取微信聊天记录，自动生成结构化日报。

---

## 📋 目录

- [平台支持](#-平台支持)
- [快速开始](#-快速开始)
  - [方式一：WorkBuddy Skill 安装（推荐）](#方式一workbuddy-skill-安装推荐)
  - [方式二：手动安装](#方式二手动安装)
- [配置引导：你会被问到哪 4 个问题？](#-配置引导你会被问到哪-4-个问题)
- [命令参考](#-命令参考)
- [两种摘要模式：规则 vs AI](#-两种摘要模式规则-vs-ai)
- [目录结构](#-目录结构)
- [工作原理](#-工作原理)
- [常见问题](#-常见问题)

---

## 🌍 平台支持

| 层级 | 支持范围 | 说明 |
|------|---------|------|
| **核心脚本** `run_daily_v3.py` | ✅ Windows / macOS / Linux | 纯 Python，任何能执行 Shell+Python 的环境均可运行 |
| **微信数据源** wechat-cli | Windows only | 依赖微信 PC 版 Windows COM 接口；macOS 微信无此接口 |
| **AI 引导体验** SKILL.md | WorkBuddy | 对话式安装/配置/执行，非 WorkBuddy 用户需手动运行命令 |
| **AI 摘要模式** Ollama | ✅ Windows / macOS / Linux | 可选功能，需额外安装 [Ollama](https://ollama.com) |

> 💡 **简单来说**：你在哪个系统都行，只是微信必须跑在 Windows 上。如果你 Mac 办公但 Windows 挂微信，可以在 Windows 上跑脚本。

---

## 🚀 快速开始

### 前置条件

| 依赖 | 说明 |
|------|------|
| **微信 PC 版** | 运行中且已登录（Windows only） |
| **Python 3.8+** | 运行脚本 |
| **Git** | 安装 wechat-cli 时 clone 仓库用 |
| **PyYAML** | Python 依赖（AI 自动安装，无需手动处理） |

---

### 方式一：WorkBuddy 安装（推荐）

**一句话安装**——在 WorkBuddy 对话中粘贴：

```
帮我配置并安装 https://github.com/mumuxiaya/wechat-daily-summary
```

AI 会自动读取项目中的 SKILL.md，完成全部工作：
- ✅ 克隆仓库并放到合适的位置
- ✅ 检测环境 → 自动安装 wechat-cli + PyYAML
- ✅ 对话式配置（问 4 个问题，详见下文）
- ✅ 生成第一份摘要

**设置定时自动化（可选）**

在 WorkBuddy 中创建自动化任务，每天自动生成微信日报。

---

### 方式二：手动安装

适用于其他 AI Agent、命令行用户、或想自行集成的场景。

```bash
# 1. 克隆本仓库
git clone https://github.com/你的用户名/wechat-daily-summary.git
cd wechat-daily-summary

# 2. 安装 wechat-cli（一键脚本）
python setup_wechat_cli.py

# 3. 初始化 wechat-cli（需微信 PC 版已登录）
wechat-cli init

# 4. 配置向导（交互式回答 4 个问题）
python run_daily_v3.py --setup

# 5. 生成今天的摘要
python run_daily_v3.py

# 6. 补跑历史某天
python run_daily_v3.py --date 2026-06-15

# 7. 聚合分析最近一周
python run_daily_v3.py --date-range 2026-06-15 2026-06-21
```

---

## ❓ 配置引导：你会被问到哪 4 个问题？

无论是 WorkBuddy AI 引导还是手动 `--setup`，配置过程都只需回答以下 4 个问题：

### 问题 1：核心联系人 👤

```
首先，我需要知道你想监控哪些人的消息。

请输入核心联系人的名字，每行一个（可以写备注名或微信昵称），
输入"完成"或空行结束。
例如：
  张三
  李四（产品组）
```

**作用**：这些人决定了自动发现哪些群聊、监控哪些私聊。

---

### 问题 2：群聊监控模式 📢

```
请选择群聊监控模式：
1. 自动发现（推荐）— 扫描所有群聊，自动识别包含核心联系人的群
2. 监控所有群聊 — 你加入的全部群（消息量可能很大）
3. 指定群名 — 手动指定要监控的群
```

| 选项 | 说明 | 推荐场景 |
|------|------|---------|
| **1. 自动发现** | 脚本扫描你所有群，找出包含核心联系人的群 | ⭐ 推荐，精准高效 |
| **2. 所有群聊** | 监控所有群，包括购物群、闲聊群 | 想全面了解微信动态时 |
| **3. 指定群名** | 只监控你指定的群 | 群特别多、只想看几个关键群时 |

---

### 问题 3：私聊监控模式 💬

```
请选择私聊监控模式：
1. 只监控核心联系人的私聊（推荐）
2. 监控所有私聊（消息量可能很大）
3. 指定联系人 — 手动指定
```

| 选项 | 说明 |
|------|------|
| **1. 核心联系人** | 只监控问题 1 中指定的人的私聊 |
| **2. 所有私聊** | 全部一对一聊天（谨慎使用） |
| **3. 指定联系人** | 手动指定想监控私聊的人 |

---

### 问题 4：摘要模式 🤖

```
请选择摘要生成模式：
1. 规则模式（推荐）— 按关键词和时间结构汇总，速度快
2. AI 模式 — 使用 AI 模型生成自然语言摘要，需要安装 Ollama
```

| 模式 | 特点 | 需额外安装 |
|------|------|-----------|
| **规则模式** | 秒级出结果，按活跃度/时段结构汇总 | ❌ 无 |
| **AI 模式** | 自然语言叙述，智能提炼重点 | Ollama + 模型 |

> 两种模式的详细区别见 [下方说明](#-两种摘要模式规则-vs-ai)。

---

**回答完这 4 个问题后**，配置文件会自动生成到 `config.yaml`，之后运行脚本不再需要回答任何问题。

想修改配置？直接编辑 `config.yaml` 或再次运行 `python run_daily_v3.py --setup`。

---

## 📟 命令参考

### 日常使用

| 命令 | 用途 |
|------|------|
| `python run_daily_v3.py` | 生成今天的摘要 |
| `python run_daily_v3.py --date 2026-06-15` | 生成指定日期的摘要（精确当天 00:00-23:59） |
| `python run_daily_v3.py --date-range 2026-06-15 2026-06-21` | 聚合分析多天（推荐 ≤7 天） |
| `python run_daily_v3.py --mode all` | 临时使用「所有群聊」模式 |
| `python run_daily_v3.py --mode discover` | 临时使用「自动发现」模式 |

### 管理命令

| 命令 | 用途 |
|------|------|
| `python run_daily_v3.py --setup` | 重新配置（再次回答 4 个问题） |
| `python run_daily_v3.py --list-groups` | 列出所有微信群 |
| `python run_daily_v3.py --list-contacts` | 列出所有微信联系人 |
| `python setup_wechat_cli.py` | 安装/更新 wechat-cli |

### 配置参考

所有可配置项见 `config.yaml.example`（带详细中文注释）。

---

## 🤖 两种摘要模式：规则 vs AI

### 规则模式（默认）

脚本直接分析消息，按结构化规则生成摘要：

```
## 工作群A 今日摘要
活跃成员: 张三(45条), 李四(32条), 王五(18条)
关键话题: 项目排期讨论、UI设计评审
```

- ✅ 速度快（秒级），零额外依赖
- ✅ 稳定可靠，不受 AI 幻觉影响
- ❌ 格式固定，缺乏叙述感

### AI 模式（Ollama）

将消息发送给本地 Ollama 模型，生成自然语言摘要：

```
工作群A今天主要讨论了项目排期。张三提出了新的时间节点，
李四对 UI 设计给出了修改意见，团队决定将 deadline 延后两天。
大家下午还围绕测试用例做了详细对齐。
```

- ✅ 阅读体验好，智能提炼重点
- ❌ 需要安装 [Ollama](https://ollama.com) 并拉取模型（如 `qwen2:7b`）
- ❌ 依赖本地 GPU/CPU 算力，速度较慢

> 💡 **建议**：日常用规则模式，周末想看叙事性回顾时切换到 AI 模式。

---

## 📁 目录结构

```
wechat-daily-summary/
├── SKILL.md                  ← WorkBuddy Skill 定义
├── README.md                 ← 本文件
├── run_daily_v3.py           ← 核心脚本（单日 + 聚合 + 配置向导）
├── setup_wechat_cli.py       ← wechat-cli 一键安装脚本
├── config.yaml.example       ← 配置模板（含详细中文注释）
├── .gitignore                ← 排除个人数据/旧脚本
│
├── config.yaml               ← 你的配置（gitignore，不提交）
└── summaries/                ← 生成的摘要
    ├── 2026-06-23_scan_result.json
    ├── 2026-06-23_工作群A.md
    ├── 2026-06-15_to_2026-06-21_周期报告.md   ← 聚合报告
    └── ...
```

---

## ⚙️ 工作原理

```
微信 PC 版 (已登录，Windows)
    ↓ Windows COM 接口
wechat-cli (命令行工具)
    ↓ 子进程调用
run_daily_v3.py (Python)
    ├── 1. 扫描群聊 → 根据模式过滤
    ├── 2. 拉取消息 → 按时间精确过滤 (00:00-23:59)
    ├── 3. 生成摘要 →
    │       规则模式: 按活跃度/关键词/时段汇总
    │       AI 模式: 调用 Ollama 生成自然语言摘要
    └── 4. 输出 Markdown → summaries/ 目录
```

**隐私说明**：全部处理在本地完成，聊天记录不会上传到任何云端服务。摘要文件储存在本地 `summaries/` 目录中。

---

## ❓ 常见问题

<details>
<summary><b>Q: 支持 macOS / Linux 吗？</b></summary>

核心脚本 `run_daily_v3.py` 支持 macOS / Linux，但 **wechat-cli 依赖 Windows COM 接口**，因此微信必须运行在 Windows 上。

如果你的微信在 Windows 上，你可以：
- 直接在 Windows 上运行脚本
- 或通过远程执行（如 SSH）在 Windows 机器上运行

macOS/Linux 可尝试 Wine 运行微信 PC 版，但未经测试。
</details>

<details>
<summary><b>Q: 能在其他 AI Agent（非 WorkBuddy）中使用吗？</b></summary>

**可以。** 核心脚本 `run_daily_v3.py` 是标准 Python，任何能执行 Shell/Python 的 AI Agent 都可以调用。只需：

```bash
python run_daily_v3.py --date 2026-06-15
```

SKILL.md 中的对话式引导体验是 WorkBuddy 专属的；其他 Agent 需手动运行上述命令，或由其 AI 自行编排调用流程。
</details>

<details>
<summary><b>Q: 消息会泄露吗？</b></summary>

**不会。** 所有处理完全本地运行：
- 聊天记录通过 wechat-cli 从本地微信 PC 版读取
- 摘要由本地 Python 脚本生成（或本地 Ollama 模型）
- 摘要文件存储在本地 `summaries/` 目录
- 没有任何数据上传到云端
</details>

<details>
<summary><b>Q: 如何确保只抓取指定日期的消息？</b></summary>

脚本使用 wechat-cli 的 `--end-time` 参数精确锁定日期范围：
- `--date 2026-06-15` → 抓取 6/15 00:00 到 6/15 23:59 的消息
- `--date-range 2026-06-15 2026-06-21` → 抓取 6/15 00:00 到 6/21 23:59

不会混入前一天或后一天的消息。
</details>

<details>
<summary><b>Q: 聚合模式（--date-range）和单日模式有什么区别？</b></summary>

| | 单日模式 `--date` | 聚合模式 `--date-range` |
|------|------|------|
| 输出 | 按天 × 按群，多个 .md 文件 | 一份统一周期报告 |
| 内容 | 当天消息汇总 | 跨日趋势、热点变化、活跃排行 |
| 适用 | 日常日报 | 休假回来、周末补漏、了解近期动态 |
| 推荐天数 | 1 天 | 2-7 天 |
</details>

<details>
<summary><b>Q: 自动发现模式怎么判断哪些群是「工作群」？</b></summary>

自动发现不判断群的性质。它的逻辑是：

> 你指定了核心联系人（如张三、李四）→ 扫描所有群 → 找出**同时包含你和张三或李四**的群 → 只监控这些群。

此外，群名包含「好物」「购物」「游戏」「外卖」等关键词的群会被自动排除（可在 `config.yaml` 中自定义排除词）。
</details>

<details>
<summary><b>Q: wechat-cli 安装失败怎么办？</b></summary>

常见原因和解决方法：

1. **网络问题**（克隆 GitHub 失败）→ 检查是否能访问 github.com
2. **Python 版本过低** → 需要 Python 3.8+
3. **微信未登录** → 先启动微信 PC 版并扫码登录，再运行 `wechat-cli init`
4. **权限问题** → Windows 上尝试以管理员身份运行终端

如果仍然失败，请到 [wechat-cli Issues](https://github.com/huohuoer/wechat-cli/issues) 搜索或反馈。
</details>

---

## 📄 许可证

MIT License
