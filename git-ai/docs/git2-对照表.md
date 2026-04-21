---

I detect **research / planning** intent — 你要的是一份可执行的迁移清单，对照 `repository.rs` 里的 CLI 调用和可替代的 `git2` API。我的做法：直接给你按优先级排好的迁移对照表，并标出收益、难度、风险。
下面这份表聚焦 **`src/git/repository.rs`**。

---

# `repository.rs` 迁移对照表

## P0：优先迁移，收益最高

| 位置/函数 | 当前 Git CLI | 推荐 `git2` API | 难度 | 收益 | 备注 |
|---|---|---|---|---|---|
| `revparse_single()` `2193-2203` | `rev-parse --verify <spec>` | `Repository::revparse_single()` | 低 | 高 | 最直接替换点，很多上层都会复用 |
| `Object::peel_to_commit()` `579-585` | `rev-parse --verify <oid>^{commit}` | `Repository::revparse_single()` + `Object::peel_to_commit()` | 低 | 高 | 典型 peel 操作，git2 很适配 |
| `Commit::tree()` `934-940` | `rev-parse --verify <oid>^{tree}` | `Commit::tree()` / `tree_id()` | 低 | 高 | 不该再起子进程 |
| `Commit::parent()` `947-954` | `rev-parse --verify <oid>^N` | `Commit::parent(n)` | 低 | 高 | 每 commit 常用 |
| `Commit::parents()` `963-976` | `show -s --format=%P` | `Commit::parents()` / `parent_ids()` | 低 | 高 | 当前是“取 parent 列表还起进程” |
| `Commit::summary()` `994-1002` | `show -s --format=%s` | `Commit::summary()` / `message()` | 低 | 高 | 遍历 commit 时热点明显 |
| `Commit::body()` `1008-1016` | `show -s --format=%b` | `Commit::body()` / `message()` | 低 | 高 | 同上 |
| `Commit::author()` `1021-1039` | `show -s --format=%an%n%ae%n%aI` | `Commit::author()` | 低 | 高 | 很标准 |
| `Commit::committer()` `1045-1063` | `show -s --format=%cn%n%ce%n%cI` | `Commit::committer()` | 低 | 高 | 很标准 |
| `Repository::merge_base()` `1938-1944` | `merge-base A B` | `Repository::merge_base()` | 低 | 高 | 图查询，适合迁移 |
| `CommitRange::length()` `759-768` | `rev-list --count A..B` | `Repository::revwalk()` + count | 中 | 高 | 范围大时收益明显 |
| `CommitRange::into_iter()` `809-823` | `rev-list A..B` | `Repository::revwalk()` | 中 | 高 | 这是 commit 范围遍历核心热点 |
| `CommitRange::is_valid()` `708-749` | 多次 `merge-base --is-ancestor` | `Repository::graph_descendant_of()` / `merge_base()` | 中 | 高 | 现在同一逻辑内反复起进程 |
| `parent_on_refname()` `1130-1145` | 循环里 `merge-base --is-ancestor` | `graph_descendant_of()` | 中 | 高 | 典型 inner-loop 热点 |

---

## P1：建议迁移，收益中高

| 位置/函数 | 当前 Git CLI | 推荐 `git2` API | 难度 | 收益 | 备注 |
|---|---|---|---|---|---|
| `Reference::shorthand()` `1300-1306` | `rev-parse --abbrev-ref <ref>` | `Reference::shorthand()` | 低 | 中 | 标准 ref API |
| `Reference::target()` `1309-1314` | `rev-parse <ref>` | `Reference::target()` | 低 | 中 | 简单替换 |
| `Reference::peel_to_blob()` `1321-1330` | `rev-parse --verify <ref>^{blob}` | `find_reference`/`revparse_single` + peel | 低 | 中 | 与 P0 同类 |
| `Reference::peel_to_commit()` `1335-1345` | `rev-parse --verify <ref>^{commit}` | 同上 | 低 | 中 | 与 P0 同类 |
| `head()` `1570-1589` | `symbolic-ref HEAD` | `Repository::head()` | 低 | 中 | detached HEAD 逻辑需保留 |
| `find_reference()` `1925-1935` | `show-ref --verify -s` | `Repository::find_reference()` | 低 | 中 | 干净直接 |
| `references()` `2287-2305` | `for-each-ref --format=%(refname)` | `Repository::references()` | 低 | 中 | 列 ref 很适合库调用 |
| `new_infer_refname()` `650-667` | `for-each-ref --points-at` | `Repository::references()` + target 过滤 | 中 | 中 | 需要自己做 `points-at` 过滤 |
| `remote_head()` `1913-1920` | `symbolic-ref refs/remotes/.../HEAD --short` | `find_reference()` + symbolic target | 中 | 中 | 语义稍微多一点 |
| `upstream_remote()` `2235-2247` | `branch --show-current` + config | `head()` + `branch_upstream_remote()` 或 config 读 | 中 | 中 | 可迁，但收益一般 |

---

## P1：对象/树/blob 读取，适合迁移

| 位置/函数 | 当前 Git CLI | 推荐 `git2` API | 难度 | 收益 | 备注 |
|---|---|---|---|---|---|
| `object_type()` `1558-1564` | `cat-file -t <oid>` | `find_object()` + `ObjectType` | 低 | 中 | 纯对象库查询 |
| `Blob::content()` `1275-1281` | `cat-file blob <oid>` | `Repository::find_blob()` + `Blob::content()` | 低 | 中 | 很适合 |
| `find_commit()` `2309-2321` | `cat-file -t` 后校验 | `Repository::find_commit()` | 低 | 中 | 更自然 |
| `find_blob()` `2325-2333` | `cat-file -t` 后校验 | `Repository::find_blob()` | 低 | 中 | 更自然 |
| `find_tree()` `2337-2345` | `cat-file -t` 后校验 | `Repository::find_tree()` | 低 | 中 | 更自然 |
| `get_file_content()` `2351-2360` | `show <commit>:<path>` | `find_commit` + `tree` + `get_path` + blob read | 中 | 中 | 需要改成对象遍历 |
| `Tree::get_path()` `1199-1259` | `ls-tree -z -r <tree> -- <path>` | `Tree::get_path()` | 中 | 中 | git2 有 API，但路径/错误语义要重新对齐 |

---

## P1/P2：索引和 staged 读取，性能潜力大，但不一定只靠 `git2`

| 位置/函数 | 当前 Git CLI | 推荐方案 | 难度 | 收益 | 备注 |
|---|---|---|---|---|---|
| `get_all_staged_files_content()` `2366-2408` | 并发 `git show :<path>` | `Repository::index()` + blob OID -> blob content | 中 | 很高 | 这里在慢 VM 里很可能是大热点 |
| `get_all_staged_file_blob_oids()` `2411-2428` | 已经是 `gix_index` | 保持现状 | 低 | 已优化 | 这块已经走对方向了，不必改成 git2 |

> 这一块我会特别提醒：**如果目标只是性能，不一定要统一成 git2**。  
> staged/index 读取这类场景，`gix`/直接 index 读取常常比 `git2` 更划算。

---

## P2：可迁移，但收益一般 / 语义稍重

| 位置/函数 | 当前 Git CLI | 推荐 `git2` API | 难度 | 收益 | 备注 |
|---|---|---|---|---|---|
| `remotes()` `1692-1699` | `remote` | `Repository::remotes()` | 低 | 低中 | 不常调用就没太大收益 |
| `remotes_with_urls()` `1702-1725` | `remote -v` | `Repository::remotes()` + `find_remote()` | 中 | 低中 | 要自己组装 fetch/push URL 逻辑 |
| `resolve_author_spec()` `2249-2282` | `rev-list --all --author=...` + `show` | `revwalk()` + 手动过滤 author | 中高 | 中 | CLI 一句顶很多逻辑，迁移不如前面值 |
| `is_bare_repository()` `1613-1620` | `rev-parse --is-bare-repository` | `Repository::is_bare()` | 低 | 低 | 可顺手迁移 |
| `find_repository()` `2709-2864` | `rev-parse --git-dir --git-common-dir --show-toplevel` | `Repository::discover()` / `open_ext()` | 中 | 中 | 这是初始化路径，次数少但可清理掉若干 subprocess |

---

## P3：能迁，但我不建议作为第一批

| 位置/函数 | 当前 Git CLI | 推荐 `git2` API | 难度 | 收益 | 为什么不优先 |
|---|---|---|---|---|---|
| `blob()` `1877-1883` | `hash-object -w --stdin` | `Repository::blob()` | 中 | 中 | 可做，但不是主要热点 |
| `reference()` `1888-1910` | `update-ref --stdin --create-reflog` | `Repository::reference()` | 中高 | 中 | reflog/force/create 语义要仔细对齐 |
| `commit()` `2077-2189` | `commit-tree` + `update-ref` | `Repository::commit()` + refs 更新 | 高 | 中 | 这里不是单纯 API 替换，牵涉 CAS 语义 |
| `fetch_branch()` `2699-2705` | `fetch remote branch` | `Remote::fetch()` | 高 | 低/不确定 | 网络/transport 场景不一定比 CLI 更好 |

---

## 暂时建议保留 CLI 的

| 位置/函数 | 当前 Git CLI | 为什么先别动 |
|---|---|---|
| `list_commit_files()` `2433-2490` | `diff-tree --name-only -r -z` | 当前强依赖 CLI diff 输出语义和 pathspec 处理 |
| `diff_added_lines()` `2499-2545` | `diff -U0 --find-renames=1%` | 你不仅要 diff，还要解析 patch/hunk 语义 |
| `diff_added_lines_with_deleted_count()` `2551-2568` | 同上 | 迁移会变成重写算法 |
| `diff_changed_files()` `2572-2596` | `diff --name-only -z` | 输出格式和 rename/pathspec 语义已成依赖 |
| `diff_workdir_added_lines()` `2604-2645` | `diff -U0` | 同上 |
| `diff_workdir_added_lines_with_insertions()` `2654-2696` | `diff -U0 --no-renames` | 同上 |
| `merge_trees_favor_ours()` `1949-1964` | `merge-tree --write-tree -X ours` | `git2` 有 merge API，但这里不是一键等价 |

---

# 推荐落地顺序

## 第一阶段：最值得做
按这个顺序改，通常收益最大：

1. `revparse_single` / peel / ref resolve  
2. `Commit::{summary, body, author, committer, tree, parent, parents}`  
3. `merge_base` / `CommitRange::{length, into_iter, is_valid}` / `parent_on_refname`  
4. `object_type` / `find_commit` / `find_blob` / `find_tree` / `Blob::content`

## 第二阶段：如果还要继续
5. `head` / `find_reference` / `references` / `new_infer_refname`  
6. `get_file_content` / `Tree::get_path`  
7. `get_all_staged_files_content`（但优先考虑沿用/扩展 `gix` 思路）

## 最后才碰
8. `commit-tree` / `update-ref` / `reference` / `commit`  
9. `diff*` / `merge-tree` / `fetch`

---

# 额外提醒

## 1. 不要把“能用 git2”误解成“就该迁”
你这文件里最有价值的目标不是“全面去 CLI”，而是：

- 去掉 **高频、轻量、只读** 的 git 子进程
- 保留 **复杂语义 / 输出格式依赖 / 网络操作** 的 CLI

## 2. `git2` 不是唯一答案
你这仓库已经在 index 层用了 `gix_index`。  
如果你的核心痛点是：
- staged files
- index scan
- status/index 相关

那继续往 `gix` 方向走，可能比统一迁成 `git2` 更快。

---

如果你愿意，我下一条可以继续给你一份：

## **“第一阶段具体改造清单”**
格式会是：

- 函数名
- 替换成的 `git2` 调用
- 需要保留的当前语义
- 迁移时最容易踩的坑

只覆盖 **P0 + P1 第一阶段**，方便你直接开工。
