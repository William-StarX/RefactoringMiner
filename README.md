# RefactoringMiner Agent

[中文](#chinese) · [English](#english)

SDK / service **1.5.0** · Result interface **1.0** · RefactoringMiner **3.0.11**

<a id="chinese"></a>

## 中文

### 作用是什么

**为编程 Agent 提供可定位、可复查的 Java 变更证据，帮助它审查实现、核对重构和复审缺陷修复。**

Agent 改完代码后，需要知道“哪些代码只是重命名或移动，哪些表达式、条件和调用也发生了变化”。本组件调用 RefactoringMiner，结合重构识别、抽象语法树（AST）编辑和普通文本差异，把这些证据整理成统一 JSON，交给 Agent 阅读源码、检查调用方和选择测试。

例如：一次修改把校验逻辑提取成新方法，同时改变了边界条件。Agent 可以结合方法提取和条件编辑的证据，定位相关代码，再检查边界行为和回归测试。**审查结论仍由 Agent 根据需求、源码和测试形成；检测到重构不代表行为一定保持不变。**

### 能帮助 Agent 干什么

| 工作场景 | 组件提供什么 | Agent 如何使用 |
|---|---|---|
| 完成一批 Java 实现或修复 | 工作区相对基准的重构、AST 编辑、文本差异和代码位置 | 检查候选补丁，寻找需要验证的条件、调用和测试 |
| 审查提交或版本变化 | 两个提交之间的最终差异及精确版本信息 | 理解变更范围，跟随重命名、移动和提取后的代码 |
| 接收修改前后的源码包 | 两个源码目录之间的变更证据 | 在没有 Git 历史时审查交付物 |
| 向下一位 Agent 交接 | 完整报告、目标版本或内容指纹、警告和覆盖限制 | 复查已有结论，判断报告是否仍对应当前候选 |

适用于能调用本地进程、Python SDK、HTTP 或 MCP 工具的 Agent。项目提供统一接口和关键阶段调用指引，减少每个 Agent 单独编写 Java 调用、参数校验和结果适配的工作。

需要先理解旧项目或追查代码历史时，可搭配独立的 [CodeTracker Agent](https://github.com/William-StarX/Tracker)：先梳理和调查，再修改与测试，最后用本组件审查候选变更。两个组件可以分别使用。

### 快速开始

需要 **Python 3.11+、Java 17+**；下方的源码安装命令及仓库比较需要 Git，目录比较本身不需要 Git。首次准备引擎需要 **JDK 和网络**。基础 SDK 没有第三方 Python 依赖。

```sh
python -m pip install "git+https://github.com/William-StarX/RefactoringMiner.git"
refactoringminer-agent doctor
refactoringminer-agent prepare
```

`prepare` 下载固定版本依赖并准备本组件引擎，不构建被分析项目；后续可复用缓存。可用 `JAVA_HOME` 指定 Java、`JAVA_ANALYSIS_CACHE` 指定缓存。以下示例中的路径和提交需替换为实际目标。

```python
from refactoringminer_agent import Client

client = Client()

# 审查当前工作区；包含暂存、未暂存修改及分析范围内的新 Java 文件。
report = client.review("/path/to/repo", base="HEAD", include_untracked=True)
print(report["status"])
print(report["result"])  # 组件报告，包含证据、警告、限制和来源

# 也可选择两个提交，或没有 Git 的源码目录。
# report = client.review("/path/to/repo", base="HEAD~1", head="HEAD")
# report = client.directories("/path/to/before", "/path/to/after")
```

`base` 应使用任务实际要求的比较基准。传入 `head` 时比较已提交版本，不包含工作区修改。

不使用 Python SDK 的 Agent 可以传入一个 JSON 请求：

```sh
refactoringminer-agent describe
refactoringminer-agent call --request request.json
```

`request.json`：

```json
{"operation":"review","repo":"/path/to/repo","base":"HEAD","include_untracked":true}
```

`call` 也接受标准输入。`describe` 返回工具参数、响应 Schema 和调用阶段指引。

### 接入 Agent，并在关键阶段主动调用

提供四种调用入口：Python `Client` / `HTTPClient`、JSON CLI、MCP stdio / Streamable HTTP，以及认证 HTTP API。HTTP/MCP 服务需安装可选依赖：

```sh
python -m pip install "refactoringminer-agent[server] @ git+https://github.com/William-StarX/RefactoringMiner.git"
refactoringminer-agent config codex --root /path/to/repo
```

`config` 只生成配置片段，需合并到宿主配置；另支持 `claude-code`、`claude-desktop`、`cursor`、`vscode`、`copilot`。MCP stdio 启动命令为 `refactoringminer-agent mcp --root /path/to/repo`。配置与协议启动已验证，各宿主的完整任务流程仍需按实际环境验证，详见 [Agent 接入](docs/AGENTS.md)。

支持 Skill 的宿主还可导出调用流程，例如在项目根目录执行：

```sh
refactoringminer-agent install-skill --destination .agents/skills
```

该目录是 Codex 项目示例，其他宿主应使用其发现目录。安装器不覆盖已有 Skill，可加 `--java-home`、`--cache-dir`；生成的 `runtime.local.json` 仅保留在本机。

已加载 Skill 或 MCP 指引的 Agent，应在以下阶段主动调用，无需用户每轮再次点名：

1. 用户要求审查 Java 变更时。
2. 完成一批 Java 实现、重构或缺陷修复后。
3. 准备交付时，若最终候选与已有报告的内容不一致，则重新审查。

相同目标和内容的证据可复用，无需每条消息或每次保存文件都重跑。跨聊天继续项目时，宿主应继续加载指引，并保存报告引用、版本和覆盖限制。**这些指引由 Agent 执行；强制保证某个流程节点已经运行，需要宿主调度器接入。** SDK 自身不监听项目流程，也不恢复聊天记录。详见 [阶段规则](docs/WORKFLOW.md)。

需要 HTTP 时，先将 `JAVA_AGENT_TOKEN` 设置为至少 32 字符的随机令牌，再运行：

```sh
refactoringminer-agent http --root /path/to/repo --port 8765
```

服务监听 `127.0.0.1`；`/health`、`/tools`、`/invoke` 和 `/mcp` 均需 Bearer 认证。只允许配置目录中的目标，建议使用普通独立 clone；远程访问需自行配置可信 TLS 通道，路径指服务端路径。完整协议见 [API](docs/API.md)。

### 如何理解结果与开销

- 检查 `status`：`ok`、`partial` 或 `error`。`partial` 必须结合报告中的警告、限制和截断信息解释；HTTP 200 或退出码 0 不等于完整分析。
- 默认返回完整组件报告；`format="compact"` 必须同时用 `output` 在被分析项目之外保存完整报告，服务另需授权 `--output-root`，已有文件不会被覆盖。完整返回并不保证引擎覆盖所有输入。
- 工具收集重构和差异证据，不执行目标项目的测试，也不证明补丁无缺陷。Agent 应结合调用方、需求和实际测试结果形成结论。
- 每个 Client / 服务实例一次执行一个分析，忙时返回 `BUSY`。Java 按请求启动，无常驻 JVM、数据库或 GPU；Java 堆默认上限 2048 MiB，可用 `memory_mb` 调整，但这不是整个进程树的内存上限。封装便利性不代表所有输入都更快或更省内存。
- 分析在本地执行，组件不调用模型、不上传源码、不发送遥测。报告可能含源码和路径，宿主 Agent 仍可能把结果发送给其模型提供商。见 [隐私说明](PRIVACY.md)。

### 论文与上游项目

核心分析基于作者的 [tsantalis/RefactoringMiner](https://github.com/tsantalis/RefactoringMiner)，固定使用 Maven `com.github.tsantalis:refactoring-miner:3.0.11`。相关研究包括：

1. **AST 差异分析** — Pouria Alikhanifard, Nikolaos Tsantalis. *A Novel Refactoring and Semantic Aware Abstract Syntax Tree Differencing Tool and a Benchmark for Evaluating the Accuracy of Diff Tools*. **ACM Transactions on Software Engineering and Methodology (TOSEM)**, 34(2), Article 40, **2025 年 2 月正式卷期**. [DOI: 10.1145/3696002](https://doi.org/10.1145/3696002)。这是本组件 AST 差异能力的主要研究依据。
2. **重构识别** — Nikolaos Tsantalis, Ameya Ketkar, Danny Dig. *RefactoringMiner 2.0*. **IEEE Transactions on Software Engineering (TSE)**, 48(3), 930–950, **2022 年 3 月**. [DOI: 10.1109/TSE.2020.3007722](https://doi.org/10.1109/TSE.2020.3007722)。介绍上游重构检测工具的演进。
3. **早期基础工作** — Nikolaos Tsantalis, Matin Mansouri, Laleh M. Eshkevari, Davood Mazinanian, Danny Dig. *Accurate and Efficient Refactoring Detection in Commit History*. **ICSE 2018**, 483–494. [DOI: 10.1145/3180155.3180206](https://doi.org/10.1145/3180155.3180206)。介绍提交历史中的重构检测。

书目信息依据 [作者的引用说明](https://github.com/tsantalis/RefactoringMiner/blob/master/documentation/research.md)。论文的实验结果属于其研究设置，不等同于本封装在任意项目上的质量或性能保证。

### 本项目新增了什么

本仓库是**基于作者库的独立 Agent 适配项目**，不是作者官方仓库或完整镜像。本项目提供输入快照准备、Java 调用桥接、统一 JSON、资源限制、SDK、CLI、HTTP/MCP、宿主配置与 Skill 阶段指引；最终审查判断由调用它的 Agent 完成。

分析引擎还保留了两处经差分测试的局部优化：`StringDistance.java` 和 `ReplacementUtil.keepReservedTokens`，因此不能宣称所有底层代码均未经修改。第三方来源、许可范围及仓库自有代码的许可状态见 [NOTICE](NOTICE.md)；第三方 MIT 文件不代表全仓库统一采用 MIT 许可。

[API 与结果](docs/API.md) · [Agent 接入](docs/AGENTS.md) · [阶段规则](docs/WORKFLOW.md) · [接口验证](docs/VERIFICATION.md) · [1.5 阶段调用验证](docs/WORKFLOW_VERIFICATION.md) · [变更记录](CHANGELOG.md)

从源码开发时，在仓库根目录执行：

```sh
python -m pip install ".[server,test]"
python -m pytest
python -m build
```

---

<a id="english"></a>

## English

### What it does

**Gives coding agents traceable Java change evidence for implementation reviews, refactoring checks, and reviews of bug fixes.**

After editing code, an agent needs to understand which elements were renamed or moved and which expressions, conditions, or calls also changed. This component invokes RefactoringMiner and combines detected refactorings, abstract syntax tree (AST) edits, and text diffs into a consistent JSON report. The agent can then inspect the source, check affected callers, and select relevant tests.

For example, a patch may extract validation into a new method while also changing a boundary condition. Evidence about the extraction and condition edits helps the agent locate the relevant code and check boundary behavior and regression tests. **The agent still derives findings from requirements, source, and tests; detecting a refactoring does not prove behavior preservation.**

### How it helps an agent

| Task | Evidence provided | How the agent uses it |
|---|---|---|
| Review a batch of Java edits or a bug fix | Worktree changes against a baseline, refactorings, AST edits, text diffs, and locations | Inspect the candidate patch and identify conditions, calls, and tests to verify |
| Review commits or version changes | Final differences between two commits with exact revision information | Understand scope and follow code through renames, moves, and extractions |
| Review before/after source packages | Change evidence between two source directories | Review a deliverable without Git history |
| Hand work to another agent | Complete reports, revisions or content fingerprints, warnings, and coverage limits | Revisit findings and check whether evidence still matches the current candidate |

Agents can use a local process, Python SDK, HTTP, or MCP. The consistent interface and checkpoint guidance reduce the Java invocation, validation, and response adaptation work each agent integration would otherwise need.

For unfamiliar projects or historical investigation, optionally pair it with the independent [CodeTracker Agent](https://github.com/William-StarX/Tracker): survey and investigate, implement and test, then review candidate changes here. Either component can be used on its own.

### Quick start

Requires **Python 3.11+ and Java 17+**. The source installation below and repository comparisons require Git; directory analysis itself does not. Initial engine preparation requires a **JDK and network access**. The base SDK has no third-party Python dependencies.

```sh
python -m pip install "git+https://github.com/William-StarX/RefactoringMiner.git"
refactoringminer-agent doctor
refactoringminer-agent prepare
```

`prepare` downloads pinned dependencies and prepares this component's engine; it does not build the target project. Later runs can reuse the cache. Set `JAVA_HOME` to select Java and `JAVA_ANALYSIS_CACHE` to select a cache directory. Replace example paths and revisions with your actual targets.

```python
from refactoringminer_agent import Client

client = Client()

# Review staged/unstaged changes and in-scope new Java files in the worktree.
report = client.review("/path/to/repo", base="HEAD", include_untracked=True)
print(report["status"])
print(report["result"])  # Component report: evidence, warnings, limits, and provenance

# Alternatively, compare commits or source directories without Git.
# report = client.review("/path/to/repo", base="HEAD~1", head="HEAD")
# report = client.directories("/path/to/before", "/path/to/after")
```

Use the task's actual comparison baseline for `base`. When `head` is supplied, the comparison uses committed revisions and excludes worktree changes.

An agent without a Python integration can submit one JSON request:

```sh
refactoringminer-agent describe
refactoringminer-agent call --request request.json
```

`request.json`:

```json
{"operation":"review","repo":"/path/to/repo","base":"HEAD","include_untracked":true}
```

`call` also accepts standard input. `describe` returns tool parameters, response schemas, and checkpoint guidance.

### Connect an agent and use it at project checkpoints

Four entry points are available: Python `Client` / `HTTPClient`, JSON CLI, MCP stdio / Streamable HTTP, and an authenticated HTTP API. Install optional dependencies for HTTP/MCP services:

```sh
python -m pip install "refactoringminer-agent[server] @ git+https://github.com/William-StarX/RefactoringMiner.git"
refactoringminer-agent config codex --root /path/to/repo
```

`config` prints a fragment to merge into the host's configuration. It also supports `claude-code`, `claude-desktop`, `cursor`, `vscode`, and `copilot`. The MCP stdio launch command is `refactoringminer-agent mcp --root /path/to/repo`. Configuration parsing and protocol startup have been verified; complete workflows in each host still require validation in your environment. See [agent integration](docs/AGENTS.md).

For a host that supports Skills, export the workflow, for example from a project root:

```sh
refactoringminer-agent install-skill --destination .agents/skills
```

This destination is a Codex project example; use your host's discovery directory. The installer refuses to overwrite an existing Skill and accepts `--java-home` and `--cache-dir`. Keep the generated `runtime.local.json` on the local machine.

An agent with the Skill or MCP guidance loaded should proactively invoke the component at these checkpoints without requiring the user to name it again:

1. When asked to review Java changes.
2. After completing a meaningful batch of Java implementation, refactoring, or bug fixes.
3. Before delivery, if the final candidate differs from the content covered by an existing report.

Evidence may be reused for identical targets and content; no rerun is needed after every message or file save. Across chats, the host should keep loading the guidance and retain report references, revisions, and coverage limits. **The agent follows these instructions; guaranteed execution at a workflow node requires host scheduler integration.** The SDK neither monitors project progress nor restores chat history. See [checkpoint behavior](docs/WORKFLOW.md).

For HTTP, first set `JAVA_AGENT_TOKEN` to a random token of at least 32 characters, then run:

```sh
refactoringminer-agent http --root /path/to/repo --port 8765
```

The service binds to `127.0.0.1`. `/health`, `/tools`, `/invoke`, and `/mcp` all require Bearer authentication. Targets must stay within configured roots; use a regular independent clone. Remote access requires an operator-configured trusted TLS channel, and paths refer to the server's filesystem. See the [API](docs/API.md).

### Interpreting results and resource use

- Check `status`: `ok`, `partial`, or `error`. Interpret `partial` with the report's warnings, limitations, and truncation information. HTTP 200 or exit code 0 does not establish complete analysis.
- The complete component report is returned by default. `format="compact"` requires `output` to preserve the complete report outside the analyzed project; services additionally require an authorized `--output-root`. Existing files are not overwritten. A complete response does not guarantee that the engine covered every input.
- The tool collects refactoring and diff evidence. It does not run the target project's tests or prove that a patch is correct. Agents should combine evidence with affected callers, requirements, and actual test results.
- Each Client / service instance runs one analysis at a time and returns `BUSY` to concurrent callers. Java starts per request; there is no persistent JVM, database, or GPU requirement. The default Java heap ceiling is 2048 MiB, configurable with `memory_mb`; this is not a process-tree memory limit. Easier integration does not imply lower time or memory use on every input.
- Analysis runs locally. The component does not call models, upload source, or send telemetry. Reports may contain source and paths, and the host agent may forward results to its model provider. See [privacy](PRIVACY.md).

### Papers and upstream project

Core analysis uses the authors' [tsantalis/RefactoringMiner](https://github.com/tsantalis/RefactoringMiner), pinned to Maven `com.github.tsantalis:refactoring-miner:3.0.11`. Relevant research includes:

1. **AST differencing** — Pouria Alikhanifard, Nikolaos Tsantalis. *A Novel Refactoring and Semantic Aware Abstract Syntax Tree Differencing Tool and a Benchmark for Evaluating the Accuracy of Diff Tools*. **ACM Transactions on Software Engineering and Methodology (TOSEM)**, 34(2), Article 40, **February 2025 issue**. [DOI: 10.1145/3696002](https://doi.org/10.1145/3696002). The principal research reference for this component's AST differencing capability.
2. **Refactoring detection** — Nikolaos Tsantalis, Ameya Ketkar, Danny Dig. *RefactoringMiner 2.0*. **IEEE Transactions on Software Engineering (TSE)**, 48(3), 930–950, **March 2022**. [DOI: 10.1109/TSE.2020.3007722](https://doi.org/10.1109/TSE.2020.3007722). Describes the evolution of the upstream refactoring detector.
3. **Foundational work** — Nikolaos Tsantalis, Matin Mansouri, Laleh M. Eshkevari, Davood Mazinanian, Danny Dig. *Accurate and Efficient Refactoring Detection in Commit History*. **ICSE 2018**, 483–494. [DOI: 10.1145/3180155.3180206](https://doi.org/10.1145/3180155.3180206). Introduces refactoring detection in commit history.

Bibliographic details follow the [authors' citation guide](https://github.com/tsantalis/RefactoringMiner/blob/master/documentation/research.md). Results in these papers apply to their research settings; they do not guarantee this wrapper's quality or performance on arbitrary projects.

### What this project adds

This repository is an **independent agent integration built on the authors' library**, not the official upstream repository or a complete mirror. It provides input snapshots, a Java bridge, consistent JSON, resource controls, SDK, CLI, HTTP/MCP, host configuration, and Skill checkpoint guidance. The calling agent makes the final review judgments.

The engine also retains two local optimizations checked by differential tests: `StringDistance.java` and `ReplacementUtil.keepReservedTokens`. The underlying implementation is therefore not entirely unmodified. See [NOTICE](NOTICE.md) for provenance, third-party licensing, and the licensing status of this repository's own code. A third-party MIT license file does not license the entire repository under MIT.

[API and results](docs/API.md) · [Agent integration](docs/AGENTS.md) · [Checkpoints](docs/WORKFLOW.md) · [Interface verification](docs/VERIFICATION.md) · [1.5 checkpoint verification](docs/WORKFLOW_VERIFICATION.md) · [Changelog](CHANGELOG.md)

For development, run from the repository root:

```sh
python -m pip install ".[server,test]"
python -m pytest
python -m build
```
