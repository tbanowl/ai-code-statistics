# Codeup Merge Webhook 处理规范

## 背景

本项目需要接入阿里云 Codeup 的 Merge Request Webhook，用于在仓库发生合并相关事件时，触发 AI authorship 的归属处理。

当前 Codeup 官方文档中，合并请求 webhook 同时存在旧版和新版 payload 结构；字段命名、嵌套层级和事件触发语义并不完全一致。与此同时，`git-ai` 的标准并不把 webhook payload 作为归属真值来源，而是要求以 **Git 仓库状态、commit 图谱、Git Notes / authorship log** 为基础处理 merge、squash、rebase、fast-forward 等场景。

因此，Codeup webhook 在本系统中的职责只能是：

1. 提供外部事件触发信号；
2. 将 Codeup payload 归一化为稳定的内部事件；
3. 交由仓库级 merge 语义判定器判断真实合并类型；
4. 再依据 `git-ai standard v3.0.0` 的规则处理 authorship 迁移。

## 目标

- 统一 Codeup 新旧 webhook payload 的接入方式。
- 明确 webhook 只负责触发，不负责决定 authorship 真值。
- 明确不同 merge 类型下的处理规则：standard merge、squash merge、rebase merge、fast-forward merge。
- 明确 AI authorship 的 source of truth 只能来自仓库状态与 authorship notes。
- 明确错误处理、兼容策略与幂等原则。

## 非目标

- 不在 webhook payload 中直接计算最终归属结果。
- 不将 Codeup 的 author / user / assignee 字段当作 AI 归属依据。
- 不把 Codeup webhook 当成唯一的 merge 事实来源。
- 不要求第一版对 Codeup webhook 做鉴权设计。
- 不要求第一版提供前端页面展示任务状态。

## 设计原则

### 1. Webhook 是触发源，不是事实源

Webhook payload 只能说明“Codeup 认为某个 MR 发生了事件”，不能直接说明仓库中已经形成了哪一种 Git 结果。

### 2. 归属判定以仓库状态为准

merge 类型、提交关系、行级归属、冲突解决结果，都必须通过仓库 commit DAG、diff、merge commit parent 关系以及 authorship notes 计算。

### 3. 兼容新旧 payload，但不让 payload 结构污染业务语义

Codeup 的旧版 / 新版 payload 只影响“如何提取字段”，不影响“如何判定 merge 语义”。

### 4. AI authorship 规则与 git-ai standard v3.0.0 对齐

本规范所有 merge 规则，均以 `git-ai standard v3.0.0` 中的 merge / rebase / squash / fast-forward 语义为准。

## 参考来源

- Codeup Webhook 文档：
  - `https://help.aliyun.com/zh/yunxiao/?spm=a2c4g.11186623.help-sub-nav.2.10e65ed4tSYhCh`
- git-ai 仓库：
  - `https://github.com/git-ai-project/git-ai/tree/v1.3.4`
- git-ai 标准：
  - `https://github.com/git-ai-project/git-ai/blob/main/specs/git_ai_standard_v3.0.0.md`

## 输入事件规范

### Webhook 触发范围

本系统只处理 **Codeup Merge Request 相关事件** 中能够映射到 merge 语义的事件。

可接受的事件特征包括：

- 请求头 `Codeup-Event: Merge Request Hook`；
- 顶层 `object_kind: "merge_request"`；
- payload 中存在可识别的 MR / repository / project / merge commit 信息；
- payload 表达的是 merged、merged_success、merge、或可推导为 merge completion 的状态。

### 归一化后的内部事件

所有 Codeup payload 在进入后续处理前，必须先归一化为内部稳定事件。内部事件至少应包含以下语义字段：

| 语义字段 | 含义 |
|---|---|
| `repo_identity` | 仓库唯一标识，优先使用可直接定位仓库的 URL / path 信息 |
| `project_identity` | Codeup project 标识 |
| `merge_request_identity` | MR 的稳定标识，优先使用业务主键，再回退到 iid / id |
| `source_branch` | 源分支名 |
| `target_branch` | 目标分支名 |
| `merge_commit_sha` | merge 结果提交 SHA |
| `source_commit_shas` | 源提交 SHA 列表，如 payload 可提供 |
| `event_kind` | MR 创建 / 更新 / 合并完成 / 关闭 / 重开 / 无法判定 |
| `payload_version_hint` | 用于辅助兼容新旧 payload 的版本提示 |
| `raw_payload_ref` | 原始 payload 的引用或存储位置 |

### 字段兼容原则

#### 仓库标识

优先级应满足：

1. 直接可用的仓库 URL；
2. `project.repository` / `repository` 中的 HTTP / SSH URL；
3. `project.git_http_url` / `project.git_ssh_url`；
4. 其他可推导的仓库定位字段。

#### MR 标识

优先级应满足：

1. Codeup 新版更稳定的业务标识；
2. `object_attributes.biz_id`；
3. `object_attributes.local_id`；
4. `object_attributes.iid`；
5. `object_attributes.id`；
6. 顶层等价字段。

#### 合并结果标识

只有当 payload 中能表达出可识别的 merge 结果时，才允许进入后续处理；否则只作为 MR 事件记录，不应进入 merge authorship 流程。

## Merge 类型判定规则

### 1. Standard Merge

定义：目标分支创建了一个真正的 merge commit，且该 commit 通常具有多个 parent。

判定依据：

- 仓库中可确认存在 merge commit；
- merge commit 具有多个 parent；
- 其内容来自目标分支与源分支的历史汇合，而不是单独重写成一个线性提交。

处理原则：

- 源分支上已有的 commits 保持原 authorship logs；
- merge commit 本身只记录冲突解决所引入的新归属；
- 如果没有冲突，merge commit 可以没有实质归属记录；
- 如果冲突由 AI 协助解决，则冲突对应的新增归属必须作为新 session 记录；
- 如果冲突由人类解决，则冲突对应新增内容应归属人类 resolver。

### 2. Squash Merge

定义：多个源分支 commits 的变更被压缩成一个新的提交，历史不以原样 parent 链保留。

判定依据：

- 目标分支新增单一提交；
- 该提交内容对应源分支多个 commit 的聚合；
- 原始 commit 链在目标分支上不再以多 parent 形式保留。

处理原则：

- 源分支 commits 的 prompt records 必须保留；
- 源分支的 authorship 信息必须迁移到 squash 后的结果；
- 行级归属必须按 squash 后最终文件内容重新映射；
- 不允许简单把源分支 notes 原封不动当作最终结果；
- 如果多个 session 作用于同一行，最终归属遵循“最后一次有效 session 优先”的原则。

### 3. Rebase Merge

定义：源分支的 commits 被重新放置到新的 base 上，形成新的线性 commit 序列。

判定依据：

- 目标分支上出现新的线性 commits；
- 这些 commits 的内容和原来源 commits 相近，但 SHA 发生变化；
- 语义上属于历史重写而非单纯合并。

处理原则：

- 原 authorship logs 需要按新 commit 图谱迁移；
- `base_commit_sha` 需要指向新语义下的基准 commit；
- 行级归属必须按新 commit 的实际内容重新计算；
- 如果 rebase 后出现冲突解决，其新增内容按新 session 记录。

### 4. Fast-forward Merge

定义：目标分支只是直接前进到源分支已有的提交，没有生成额外 merge commit。

判定依据：

- 目标分支 HEAD 直接移动到源分支末端；
- 没有新的 merge commit；
- 原始提交历史保持线性可见。

处理原则：

- 不应创建新的伪 merge authorship 记录；
- 已存在的 authorship notes 保持原样；
- 只需确保仓库中相关 notes 可被正确读取和同步；
- 不应把 fast-forward 误判为 standard merge。

## Authorship 迁移规则

### Source of Truth

Authorship 的唯一真值来源为：

1. Git 仓库的 commit 图谱；
2. 最终文件内容与 diff；
3. authorship notes / Git Notes 所记录的归属信息。

Codeup payload 中的作者、提交者、用户、审批人字段，均不是 AI 归属真值。

### merge commit 的归属范围

对于 standard merge：

- 仅允许为冲突解决新增内容生成归属；
- 源分支已有归属保持不变；
- 目标分支已有归属不得被无条件覆盖。

### squash / rebase 的归属迁移

对于 squash / rebase：

- 原来源 commits 的 prompt records 必须保留；
- 新 commit 的 authorship log 必须反映最终内容；
- 行号、文件路径和归属范围必须按最终 commit 内容重新计算；
- 当多个来源对同一最终行产生归属时，必须采用稳定的优先级规则，而不是随机合并。

### 冲突解决归属

冲突解决分两类：

1. **AI 协助解决**：冲突解决形成新的 AI 归属 session；
2. **人工解决**：冲突解决归属人类 resolver。

## 错误与兼容策略

### 兼容策略

- 必须兼容旧版与新版 Codeup payload；
- 必须允许字段缺失时通过其他可用字段回退；
- 必须允许部分信息不可得时进入“无法判定”状态，而不是强行猜测；
- 必须允许某些 MR 事件只记录，不进入 merge authorship 处理。

### 错误处理原则

- 缺少关键仓库标识：拒绝进入 merge authorship 流程；
- 缺少可识别的 merge 结果：按非 merge completion 处理；
- 无法判定 merge 类型：进入保守路径，只做事件落库或等待后续仓库状态确认；
- 仓库拉取、提交解析、diff 计算失败：应可重试，不应污染归属结果；
- note 解析失败：仅在影响最终归属生成时视为失败，否则按未知归属处理。

### 幂等原则

- 同一 merge request 的重复 webhook 不应导致重复归属写入；
- 相同仓库、相同 MR、相同 merge 结果应视为同一处理单元；
- 仅当 merge 结果变化、补充 source commits、或仓库状态发生实质变化时，才允许更新处理结果。

## 验收标准

一份符合本规范的实现，应至少满足以下条件：

1. 能正确识别 Codeup 新旧 payload 中的 MR 与仓库信息；
2. 能将 webhook 事件稳定归一化为内部事件；
3. 能区分 standard merge、squash merge、rebase merge、fast-forward merge；
4. 能在不同 merge 类型下遵守 git-ai standard v3.0.0 的 authorship 规则；
5. 能保证 authorship 处理只依赖仓库状态与 notes，而不是 Codeup payload 本身；
6. 能对重复 webhook 保持幂等；
7. 能在字段缺失或事件不完整时安全降级，不产生错误归属。

## 结论

Codeup merge webhook 的正确职责，是把外部 MR 事件转化为“可判定的仓库级 merge 语义输入”；真正的 AI authorship 处理必须以 git-ai standard v3.0.0 的 merge 规则为准，最终落点应由仓库状态、commit 图谱和 authorship notes 决定。
