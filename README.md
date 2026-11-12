# RefactoringMiner Agent

[中文](#chinese) · [English](#english)

SDK / service **1.5.0** · Result interface **1.0** · RefactoringMiner **3.0.11**

<a id="chinese"></a>

## 中文

RefactoringMiner Agent 用于 **Java 代码审查**。它把重命名、移动、方法提取等重构，与具体的语法修改和文本差异一起列出来，方便 Agent 顺着变化检查代码。

比如，一次补丁把校验逻辑提取成新方法，也顺手改了一个边界条件。审查时既要跟上方法的位置变化，也要看清条件究竟改了什么。本项目调用 RefactoringMiner，将重构、抽象语法树（AST）编辑和代码位置整理成 JSON，供 Agent 检查调用方、对照需求和补充测试。

### 适合放在代码审查这一步

Agent 完成一批实现、重构或缺陷修复后，可以把当前改动交给它分析。审查对象有三种：

| 要审查的内容 | 调用方式 |
|---|---|
| 尚未提交的修改，包括暂存区与工作区 | `review(repo, base=...)` |
| 两个提交之间的最终变化 | `review(repo, base=..., head=...)` |
| 修改前后的源码目录 | `directories(before, after)` |

报告保留具体位置、版本或内容指纹，方便回到源码核查。检测到“方法提取”不意味着整个补丁保持了原有行为；测试是否通过、修改是否符合需求，仍要由 Agent 检查。

这层封装省去了 Agent 自己准备源码快照、调用 Java 库和转换结果格式的工作，可以通过 Python、命令行、MCP 或 HTTP 使用。若还需要追查某段代码的来历，可另外使用 [CodeTracker Agent](https://github.com/William-StarX/Tracker)。

### 审查工作区、提交或目录

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

### 让 Agent 在交付前检查改动

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

Skill 和 MCP 指引约定了以下调用时机，用户不必每轮重新提醒：

1. 用户要求审查 Java 变更时。
2. 完成一批 Java 实现、重构或缺陷修复后。
3. 准备交付时，若最终候选与已有报告的内容不一致，则重新审查。

已经审查过的内容没有变化，就可以沿用报告；交付前又改了代码，则需要重新检查。换一个聊天继续时，保留报告位置、版本和未覆盖的部分，并让宿主继续加载指引。这些规则靠 Agent 执行；如需每次交付都强制检查，还要在宿主的流程中设置检查步骤。详见 [阶段规则](docs/WORKFLOW.md)。

需要 HTTP 时，先将 `JAVA_AGENT_TOKEN` 设置为至少 32 字符的随机令牌，再运行：

```sh
refactoringminer-agent http --root /path/to/repo --port 8765
```

服务监听 `127.0.0.1`；`/health`、`/tools`、`/invoke` 和 `/mcp` 均需 Bearer 认证。只允许配置目录中的目标，建议使用普通独立 clone；远程访问需自行配置可信 TLS 通道，路径指服务端路径。完整协议见 [API](docs/API.md)。

### 读报告时要留意

- 检查 `status`：`ok`、`partial` 或 `error`。`partial` 必须结合报告中的警告、限制和截断信息解释；HTTP 200 或退出码 0 不等于完整分析。
- 默认返回完整组件报告；`format="compact"` 必须同时用 `output` 在被分析项目之外保存完整报告，服务另需授权 `--output-root`，已有文件不会被覆盖。完整返回并不保证引擎覆盖所有输入。
- 工具收集重构和差异证据，不执行目标项目的测试，也不证明补丁无缺陷。Agent 应结合调用方、需求和实际测试结果形成结论。
- 每个 Client / 服务实例一次执行一个分析，忙时返回 `BUSY`。Java 按请求启动，无常驻 JVM、数据库或 GPU；Java 堆默认上限 2048 MiB，可用 `memory_mb` 调整，但这不是整个进程树的内存上限。封装便利性不代表所有输入都更快或更省内存。
- 分析在本地执行，组件不调用模型、不上传源码、不发送遥测。报告可能含源码和路径，宿主 Agent 仍可能把结果发送给其模型提供商。见 [隐私说明](PRIVACY.md)。

### RefactoringMiner 与相关论文

核心分析基于作者的 [tsantalis/RefactoringMiner](https://github.com/tsantalis/RefactoringMiner)，固定使用 Maven `com.github.tsantalis:refactoring-miner:3.0.11`。相关研究包括：

1. **AST 差异分析** — Pouria Alikhanifard, Nikolaos Tsantalis. *A Novel Refactoring and Semantic Aware Abstract Syntax Tree Differencing Tool and a Benchmark for Evaluating the Accuracy of Diff Tools*. **ACM Transactions on Software Engineering and Methodology (TOSEM)**, 34(2), Article 40, **2025 年 2 月正式卷期**. [DOI: 10.1145/3696002](https://doi.org/10.1145/3696002)。这是本组件 AST 差异能力的主要研究依据。
2. **重构识别** — Nikolaos Tsantalis, Ameya Ketkar, Danny Dig. *RefactoringMiner 2.0*. **IEEE Transactions on Software Engineering (TSE)**, 48(3), 930–950, **2022 年 3 月**. [DOI: 10.1109/TSE.2020.3007722](https://doi.org/10.1109/TSE.2020.3007722)。介绍上游重构检测工具的演进。
3. **早期基础工作** — Nikolaos Tsantalis, Matin Mansouri, Laleh M. Eshkevari, Davood Mazinanian, Danny Dig. *Accurate and Efficient Refactoring Detection in Commit History*. **ICSE 2018**, 483–494. [DOI: 10.1145/3180155.3180206](https://doi.org/10.1145/3180155.3180206)。介绍提交历史中的重构检测。

书目信息依据 [作者的引用说明](https://github.com/tsantalis/RefactoringMiner/blob/master/documentation/research.md)。论文的实验结果属于其研究设置，不等同于本封装在任意项目上的质量或性能保证。

### 封装与来源

重构识别和 AST 分析来自 RefactoringMiner。这个仓库另行实现了快照准备、Java 调用和报告输出，以及上面的 SDK、服务和 Skill，便于把分析接入 Agent 的审查流程。它是独立适配项目，与作者官方仓库有别，也不提供原项目的完整镜像。

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

RefactoringMiner Agent is a **Java code review tool for agents**. It reports renames, moves, and method extractions alongside syntax edits and text diffs, so an agent can follow the code through a patch.

A patch might extract validation into a new method and also adjust a boundary condition. Reviewing it means following the relocated code and checking exactly how that condition changed. This project calls RefactoringMiner and returns the refactorings, abstract syntax tree (AST) edits, and source locations as JSON. An agent can use them to inspect callers, check requirements, and add tests.

### Where it fits in a review

Use it after an agent finishes a batch of implementation work, a refactoring, or a bug fix. It accepts three kinds of input:

| Changes to review | Call |
|---|---|
| Uncommitted changes in the index and worktree | `review(repo, base=...)` |
| Final differences between two commits | `review(repo, base=..., head=...)` |
| Before/after source directories | `directories(before, after)` |

Reports retain locations and revisions or content fingerprints so findings can be checked against the source. A detected method extraction does not mean the whole patch preserves behavior. The agent still needs to check the requirements and run the relevant tests.

The wrapper handles source snapshots, Java invocation, and result formatting. Agents can use it through Python, the command line, MCP, or HTTP. For questions about how a piece of code evolved, see the separate [CodeTracker Agent](https://github.com/William-StarX/Tracker).

### Review a worktree, commits, or directories

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

### Make review part of the agent's workflow

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

The Skill and MCP instructions ask the agent to run a review at these points, without waiting for another reminder:

1. When asked to review Java changes.
2. After completing a meaningful batch of Java implementation, refactoring, or bug fixes.
3. Before delivery, if the final candidate differs from the content covered by an existing report.

Reuse a report while the reviewed content remains unchanged. If the code changes again before delivery, review it again. When continuing in another chat, keep the report location, revision, and coverage gaps, and have the host load the instructions. These rules rely on the agent following them; a mandatory review before every delivery needs a check in the host's workflow. See [review timing](docs/WORKFLOW.md).

For HTTP, first set `JAVA_AGENT_TOKEN` to a random token of at least 32 characters, then run:

```sh
refactoringminer-agent http --root /path/to/repo --port 8765
```

The service binds to `127.0.0.1`. `/health`, `/tools`, `/invoke`, and `/mcp` all require Bearer authentication. Targets must stay within configured roots; use a regular independent clone. Remote access requires an operator-configured trusted TLS channel, and paths refer to the server's filesystem. See the [API](docs/API.md).

### Reading the report

- Check `status`: `ok`, `partial`, or `error`. Interpret `partial` with the report's warnings, limitations, and truncation information. HTTP 200 or exit code 0 does not establish complete analysis.
- The complete component report is returned by default. `format="compact"` requires `output` to preserve the complete report outside the analyzed project; services additionally require an authorized `--output-root`. Existing files are not overwritten. A complete response does not guarantee that the engine covered every input.
- The tool collects refactoring and diff evidence. It does not run the target project's tests or prove that a patch is correct. Agents should combine evidence with affected callers, requirements, and actual test results.
- Each Client / service instance runs one analysis at a time and returns `BUSY` to concurrent callers. Java starts per request; there is no persistent JVM, database, or GPU requirement. The default Java heap ceiling is 2048 MiB, configurable with `memory_mb`; this is not a process-tree memory limit. Easier integration does not imply lower time or memory use on every input.
- Analysis runs locally. The component does not call models, upload source, or send telemetry. Reports may contain source and paths, and the host agent may forward results to its model provider. See [privacy](PRIVACY.md).

### RefactoringMiner and the research behind it

Core analysis uses the authors' [tsantalis/RefactoringMiner](https://github.com/tsantalis/RefactoringMiner), pinned to Maven `com.github.tsantalis:refactoring-miner:3.0.11`. Relevant research includes:

1. **AST differencing** — Pouria Alikhanifard, Nikolaos Tsantalis. *A Novel Refactoring and Semantic Aware Abstract Syntax Tree Differencing Tool and a Benchmark for Evaluating the Accuracy of Diff Tools*. **ACM Transactions on Software Engineering and Methodology (TOSEM)**, 34(2), Article 40, **February 2025 issue**. [DOI: 10.1145/3696002](https://doi.org/10.1145/3696002). The principal research reference for this component's AST differencing capability.
2. **Refactoring detection** — Nikolaos Tsantalis, Ameya Ketkar, Danny Dig. *RefactoringMiner 2.0*. **IEEE Transactions on Software Engineering (TSE)**, 48(3), 930–950, **March 2022**. [DOI: 10.1109/TSE.2020.3007722](https://doi.org/10.1109/TSE.2020.3007722). Describes the evolution of the upstream refactoring detector.
3. **Foundational work** — Nikolaos Tsantalis, Matin Mansouri, Laleh M. Eshkevari, Davood Mazinanian, Danny Dig. *Accurate and Efficient Refactoring Detection in Commit History*. **ICSE 2018**, 483–494. [DOI: 10.1145/3180155.3180206](https://doi.org/10.1145/3180155.3180206). Introduces refactoring detection in commit history.

Bibliographic details follow the [authors' citation guide](https://github.com/tsantalis/RefactoringMiner/blob/master/documentation/research.md). Results in these papers apply to their research settings; they do not guarantee this wrapper's quality or performance on arbitrary projects.

### About this wrapper

Refactoring detection and AST analysis come from RefactoringMiner. This repository adds snapshot preparation, Java invocation, report output, and the SDK, services, and Skill described above to fit that analysis into an agent's review workflow. It is maintained as a separate integration, rather than the authors' official repository or a full mirror.

The engine also retains two local optimizations checked by differential tests: `StringDistance.java` and `ReplacementUtil.keepReservedTokens`. The underlying implementation is therefore not entirely unmodified. See [NOTICE](NOTICE.md) for provenance, third-party licensing, and the licensing status of this repository's own code. A third-party MIT license file does not license the entire repository under MIT.

[API and results](docs/API.md) · [Agent integration](docs/AGENTS.md) · [Checkpoints](docs/WORKFLOW.md) · [Interface verification](docs/VERIFICATION.md) · [1.5 checkpoint verification](docs/WORKFLOW_VERIFICATION.md) · [Changelog](CHANGELOG.md)

For development, run from the repository root:

```sh
python -m pip install ".[server,test]"
python -m pytest
python -m build
```
