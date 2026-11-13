# RefactoringMiner Agent

SDK / 服务 **1.5.0** · 结果接口 **1.0** · RefactoringMiner **3.0.11**

SDK / service **1.5.0** · Result interface **1.0** · RefactoringMiner **3.0.11**

RefactoringMiner Agent 用于 **Java 代码审查**。它把重命名、移动、方法提取等重构，与具体的语法修改和文本差异一起列出来，方便 Agent 顺着变化检查代码。

RefactoringMiner Agent is a **Java code review tool for agents**. It reports renames, moves, and method extractions alongside syntax edits and text diffs, so an agent can follow the code through a patch.

比如，一次补丁把校验逻辑提取成新方法，也顺手改了一个边界条件。审查时既要跟上方法的位置变化，也要看清条件究竟改了什么。本项目调用 RefactoringMiner，将重构、抽象语法树（AST）编辑和代码位置整理成 JSON，供 Agent 检查调用方、对照需求和补充测试。

A patch might extract validation into a new method and also adjust a boundary condition. Reviewing it means following the relocated code and checking exactly how that condition changed. This project calls RefactoringMiner and returns the refactorings, abstract syntax tree (AST) edits, and source locations as JSON. An agent can use them to inspect callers, check requirements, and add tests.

## 适合放在代码审查这一步<br>Where it fits in a review

Agent 完成一批实现、重构或缺陷修复后，可以把当前改动交给它分析。审查对象有三种：

Use it after an agent finishes a batch of implementation work, a refactoring, or a bug fix. It accepts three kinds of input:

| 要审查的内容<br>Changes to review | 调用方式<br>Call |
|---|---|
| 尚未提交的修改，包括暂存区与工作区<br>Uncommitted changes in the index and worktree | `review(repo, base=...)` |
| 两个提交之间的最终变化<br>Final differences between two commits | `review(repo, base=..., head=...)` |
| 修改前后的源码目录<br>Before/after source directories | `directories(before, after)` |

报告保留具体位置、版本或内容指纹，Agent 可以据此回到源码检查调用方、核对需求，并选择需要补充的测试。

Reports retain locations and revisions or content fingerprints. The agent can use them to inspect callers, check requirements, and choose tests to add.

这层封装省去了 Agent 自己准备源码快照、调用 Java 库和转换结果格式的工作，可以通过 Python、命令行、MCP 或 HTTP 使用。若还需要追查某段代码的来历，可另外使用 [CodeTracker Agent](https://github.com/William-StarX/Tracker)。

The wrapper handles source snapshots, Java invocation, and result formatting. Agents can use it through Python, the command line, MCP, or HTTP. For questions about how a piece of code evolved, see the separate [CodeTracker Agent](https://github.com/William-StarX/Tracker).

## 审查工作区、提交或目录<br>Review a worktree, commits, or directories

运行环境为 **Python 3.11+、Java 17+**；源码安装和仓库比较使用 Git，目录比较直接读取源码目录。首次准备引擎需要 **JDK 和网络**。基础 SDK 使用 Python 标准库。

Use **Python 3.11+ and Java 17+**. Source installation and repository comparisons use Git; directory comparisons read source folders directly. Initial engine preparation requires a **JDK and network access**. The base SDK uses the Python standard library.

```sh
python -m pip install "git+https://github.com/William-StarX/RefactoringMiner.git"
refactoringminer-agent doctor
refactoringminer-agent prepare
```

`prepare` 下载固定版本依赖并准备分析引擎，后续调用可复用缓存。用 `JAVA_HOME` 指定 Java、`JAVA_ANALYSIS_CACHE` 指定缓存，并将下面的路径和提交替换为实际目标。

`prepare` downloads pinned dependencies and prepares the analysis engine for reuse. Set `JAVA_HOME` to select Java and `JAVA_ANALYSIS_CACHE` to choose a cache directory, then replace example paths and revisions with your targets.

```python
from refactoringminer_agent import Client

client = Client()

# 审查当前工作区；包含暂存、未暂存修改及分析范围内的新 Java 文件。
# Review staged/unstaged changes and in-scope new Java files in the worktree.
report = client.review("/path/to/repo", base="HEAD", include_untracked=True)
print(report["status"])
# 组件报告，包含证据、警告、限制和来源
# Component report: evidence, warnings, limits, and provenance
print(report["result"])

# 也可选择两个提交，或没有 Git 的源码目录。
# Alternatively, compare commits or source directories without Git.
# report = client.review("/path/to/repo", base="HEAD~1", head="HEAD")
# report = client.directories("/path/to/before", "/path/to/after")
```

`base` 用于指定比较基准；搭配 `head` 可以审查两个已提交版本之间的变化。

Set `base` to the task's comparison baseline. Supply `head` as well to review the changes between two committed revisions.

Agent 也可以通过命令行传入 JSON 请求：

Agents can also submit a JSON request through the command line:

```sh
refactoringminer-agent describe
refactoringminer-agent call --request request.json
```

`request.json`

```json
{"operation":"review","repo":"/path/to/repo","base":"HEAD","include_untracked":true}
```

`call` 也接受标准输入。`describe` 返回工具参数、响应 Schema 和调用阶段指引。

`call` also accepts standard input. `describe` returns tool parameters, response schemas, and checkpoint guidance.

## 让 Agent 在交付前检查改动<br>Make review part of the agent's workflow

提供四种调用入口：Python `Client` / `HTTPClient`、JSON CLI、MCP stdio / Streamable HTTP，以及认证 HTTP API。HTTP/MCP 服务需安装可选依赖：

Four entry points are available: Python `Client` / `HTTPClient`, JSON CLI, MCP stdio / Streamable HTTP, and an authenticated HTTP API. Install optional dependencies for HTTP/MCP services:

```sh
python -m pip install "refactoringminer-agent[server] @ git+https://github.com/William-StarX/RefactoringMiner.git"
refactoringminer-agent config codex --root /path/to/repo
```

将 `config` 生成的片段合并到宿主配置即可接入；另支持 `claude-code`、`claude-desktop`、`cursor`、`vscode`、`copilot`。MCP stdio 启动命令为 `refactoringminer-agent mcp --root /path/to/repo`，具体配置见 [Agent 接入](docs/AGENTS.md)。

Merge the fragment printed by `config` into the host's configuration. It also supports `claude-code`, `claude-desktop`, `cursor`, `vscode`, and `copilot`. The MCP stdio launch command is `refactoringminer-agent mcp --root /path/to/repo`; see [agent integration](docs/AGENTS.md) for setup details.

支持 Skill 的宿主还可导出调用流程，例如在项目根目录执行：

For a host that supports Skills, export the workflow, for example from a project root:

```sh
refactoringminer-agent install-skill --destination .agents/skills
```

上面使用 Codex 的项目技能目录；其他宿主选择对应的发现目录。可加 `--java-home`、`--cache-dir` 绑定 Java 和缓存位置。

The example uses Codex's project skill directory; choose the discovery directory for your host. Add `--java-home` and `--cache-dir` to bind the Java installation and cache location.

Skill 和 MCP 指引让 Agent 在以下阶段主动发起审查：

The Skill and MCP instructions ask the agent to initiate reviews at these points:

1. 用户要求审查 Java 变更时。

   When asked to review Java changes.

2. 完成一批 Java 实现、重构或缺陷修复后。

   After completing a meaningful batch of Java implementation, refactoring, or bug fixes.

3. 准备交付时，若最终候选与已有报告的内容不一致，则重新审查。

   Before delivery, if the final candidate differs from the content covered by an existing report.

与当前内容匹配的报告可以继续使用；后续修改完成后，再审查最终版本。跨聊天接着工作时，在任务记录中保留报告位置、版本和覆盖范围，并继续加载 Skill 或 MCP 指引。详见 [阶段规则](docs/WORKFLOW.md)。

Reuse reports that match the current content, then review the final version after further edits. To continue in another chat, keep the report location, revision, and coverage in the task notes and load the Skill or MCP instructions again. See [review timing](docs/WORKFLOW.md).

需要 HTTP 时，先将 `JAVA_AGENT_TOKEN` 设置为至少 32 字符的随机令牌，再运行：

For HTTP, first set `JAVA_AGENT_TOKEN` to a random token of at least 32 characters, then run:

```sh
refactoringminer-agent http --root /path/to/repo --port 8765
```

服务监听 `127.0.0.1`，通过 Bearer 认证访问 `/health`、`/tools`、`/invoke` 和 `/mcp`。用 `--root` 指定普通独立 clone 的分析目录；跨机器调用可通过可信 TLS 通道连接，参数路径使用服务端路径。完整协议见 [API](docs/API.md)。

The service binds to `127.0.0.1` and exposes `/health`, `/tools`, `/invoke`, and `/mcp` with Bearer authentication. Set `--root` to a regular independent clone. For access from another machine, connect through a trusted TLS channel and use server-side paths. See the [API](docs/API.md).

## 获取报告和调整开销<br>Get reports and manage resource use

调用返回 `status` 和 `result`：前者为 `ok`、`partial` 或 `error`，后者保存组件报告。默认完整返回；需要简短响应时，可设置 `format="compact"`，并通过 `output` 将完整报告保存到分析项目之外的新文件。服务模式同时配置 `--output-root`。

Calls return `status` and `result`: the status is `ok`, `partial`, or `error`, and the result holds the component report. Full reports are returned by default. For a shorter response, set `format="compact"` and use `output` to save the full report to a new file outside the analyzed project. In service mode, also configure `--output-root`.

Java 按请求启动，每个 Client / 服务实例同时执行一项分析，忙时返回 `BUSY`。默认 Java 堆上限为 2048 MiB，可通过 `memory_mb` 调整。参数和结果字段见 [API](docs/API.md)。

Java starts per request. Each Client / service instance handles one analysis at a time and returns `BUSY` while occupied. The default Java heap ceiling is 2048 MiB, adjustable with `memory_mb`. See the [API](docs/API.md) for parameters and result fields.

## RefactoringMiner 与相关论文<br>RefactoringMiner and the research behind it

核心分析基于作者的 [tsantalis/RefactoringMiner](https://github.com/tsantalis/RefactoringMiner)，固定使用 Maven `com.github.tsantalis:refactoring-miner:3.0.11`。相关研究包括：

Core analysis uses the authors' [tsantalis/RefactoringMiner](https://github.com/tsantalis/RefactoringMiner), pinned to Maven `com.github.tsantalis:refactoring-miner:3.0.11`. Relevant research includes:

1. **AST 差异分析** — Pouria Alikhanifard, Nikolaos Tsantalis. *A Novel Refactoring and Semantic Aware Abstract Syntax Tree Differencing Tool and a Benchmark for Evaluating the Accuracy of Diff Tools*. **ACM Transactions on Software Engineering and Methodology (TOSEM)**, 34(2), Article 40, **2025 年 2 月正式卷期**. [DOI: 10.1145/3696002](https://doi.org/10.1145/3696002)。这是本组件 AST 差异能力的主要研究依据。

   **AST differencing** — Pouria Alikhanifard, Nikolaos Tsantalis. *A Novel Refactoring and Semantic Aware Abstract Syntax Tree Differencing Tool and a Benchmark for Evaluating the Accuracy of Diff Tools*. **ACM Transactions on Software Engineering and Methodology (TOSEM)**, 34(2), Article 40, **February 2025 issue**. [DOI: 10.1145/3696002](https://doi.org/10.1145/3696002). The principal research reference for this component's AST differencing capability.

2. **重构识别** — Nikolaos Tsantalis, Ameya Ketkar, Danny Dig. *RefactoringMiner 2.0*. **IEEE Transactions on Software Engineering (TSE)**, 48(3), 930–950, **2022 年 3 月**. [DOI: 10.1109/TSE.2020.3007722](https://doi.org/10.1109/TSE.2020.3007722)。介绍上游重构检测工具的演进。

   **Refactoring detection** — Nikolaos Tsantalis, Ameya Ketkar, Danny Dig. *RefactoringMiner 2.0*. **IEEE Transactions on Software Engineering (TSE)**, 48(3), 930–950, **March 2022**. [DOI: 10.1109/TSE.2020.3007722](https://doi.org/10.1109/TSE.2020.3007722). Describes the evolution of the upstream refactoring detector.

3. **早期基础工作** — Nikolaos Tsantalis, Matin Mansouri, Laleh M. Eshkevari, Davood Mazinanian, Danny Dig. *Accurate and Efficient Refactoring Detection in Commit History*. **ICSE 2018**, 483–494. [DOI: 10.1145/3180155.3180206](https://doi.org/10.1145/3180155.3180206)。介绍提交历史中的重构检测。

   **Foundational work** — Nikolaos Tsantalis, Matin Mansouri, Laleh M. Eshkevari, Davood Mazinanian, Danny Dig. *Accurate and Efficient Refactoring Detection in Commit History*. **ICSE 2018**, 483–494. [DOI: 10.1145/3180155.3180206](https://doi.org/10.1145/3180155.3180206). Introduces refactoring detection in commit history.

更多研究资料见 [作者的引用说明](https://github.com/tsantalis/RefactoringMiner/blob/master/documentation/research.md)。

Further research material is available in the [authors' citation guide](https://github.com/tsantalis/RefactoringMiner/blob/master/documentation/research.md).

## 封装与来源<br>About this wrapper

重构识别和 AST 分析来自 RefactoringMiner。本项目负责快照准备、Java 调用和报告输出，并提供 SDK、服务和 Skill，将分析接入 Agent 的审查流程。

Refactoring detection and AST analysis come from RefactoringMiner. This project handles snapshots, Java invocation, and report output, with an SDK, services, and Skill to bring that analysis into an agent's review workflow.

分析引擎包含 `StringDistance.java` 和 `ReplacementUtil.keepReservedTokens` 两处经差分测试的局部优化，用于减少字符串计算和临时对象分配。

The engine includes two local optimizations checked by differential tests: `StringDistance.java` and `ReplacementUtil.keepReservedTokens`. They reduce string computation and temporary object allocation.

## 注意事项<br>Attention

- 审查结论应结合需求、调用方和实际测试；`partial` 结果需查看报告中的覆盖范围、警告与截断信息。

  Assess review findings alongside requirements, callers, and actual tests. For `partial` results, read the report's coverage, warnings, and truncation details.

- Skill/MCP 的阶段指引由 Agent 执行；需要强制检查时，将工具调用接入宿主流程。

  Agents follow the Skill/MCP checkpoint instructions; wire calls into the host workflow when execution must be enforced.

- 报告和本机配置可能包含源码或路径，分享前按需检查，详见 [隐私说明](PRIVACY.md)。

  Reports and local configuration may contain source or paths. Check them before sharing; see [privacy](PRIVACY.md).

- 代码来源、局部修改和许可信息见 [NOTICE](NOTICE.md)。

  See [NOTICE](NOTICE.md) for code provenance, local modifications, and licensing information.

[API 与结果](docs/API.md) · [Agent 接入](docs/AGENTS.md) · [阶段规则](docs/WORKFLOW.md) · [接口验证](docs/VERIFICATION.md) · [1.5 阶段调用验证](docs/WORKFLOW_VERIFICATION.md) · [变更记录](CHANGELOG.md)

[API and results](docs/API.md) · [Agent integration](docs/AGENTS.md) · [Checkpoints](docs/WORKFLOW.md) · [Interface verification](docs/VERIFICATION.md) · [1.5 checkpoint verification](docs/WORKFLOW_VERIFICATION.md) · [Changelog](CHANGELOG.md)

从源码开发时，在仓库根目录执行：

For development, run from the repository root:

```sh
python -m pip install ".[server,test]"
python -m pytest
python -m build
```
