# Windows spawn hang fix 变更文档

背景
- 解决 Windows 10 虚拟机上通过 git-ai 执行 git 命令（如 rev-parse）时的间歇性挂起问题。

根本原因
- 主要原因：Pipe 句柄继承竞争条件。Windows 下 Rust 的 Command::spawn() 在 CreateProcessW 时将 bInheritHandles 设置为 TRUE。当并发达到上限（约 30 个并发 git 进程）时，子进程会继承同辈进程的全部可继承管道句柄，导致 finalize_pipe_reader() 等待 EOF，但某些同辈进程仍保持管道写端打开，进而产生死锁。
- 辅助原因：缺乏超时保护，exec_git* 系列调用 timeout 为 None，挂起无法自我恢复。
- 其他影响因素：GIT_TERMINAL_PROMPT 未在内部 git 调用中禁用、stdin 使用 stdin 管道导致额外可继承句柄等。

变更内容
### src/git/repository.rs
- 新增常量 DEFAULT_EXEC_GIT_TIMEOUT: Duration = Duration::from_secs(60)
- 将以下调用中的 timeout: None 替换为 timeout: Some(DEFAULT_EXEC_GIT_TIMEOUT)：
  - exec_git_allow_nonzero_with_profile
  - exec_git_with_profile
  - exec_git_stdin_with_profile
  - exec_git_stdin_with_env_with_profile
- 在 build_git_command() 中新增环境变量：cmd.env("GIT_TERMINAL_PROMPT", "0")
- 将没有输入数据时的 stdin 从 Stdio::piped() 改为 Stdio::null()
- 将 MAX_CONCURRENT: 30 调整为按平台弹性调整：Windows 下为 4，其它平台仍为 30

### src/commands/checkpoint.rs
- 将 MAX_CONCURRENT: 30 调整为 Windows 下 4，其它平台 30

### src/authorship/virtual_attribution.rs
- 将两个 MAX_CONCURRENT: 30 的出现，均改为 Windows 下 4，其它平台 30

为什么这些修复有效
- 超时保护：将长期挂起转换为可恢复的 GitCliError，输出明确的错误信息而非静默阻塞。
- 降低并发数：Windows 下管道句柄继承竞争降低，4 进程并发显著降低死锁概率。
- 禁用交互式凭据提示：GIT_TERMINAL_PROMPT=0 避免凭据提示阻塞非交互场景。
- 调整 stdin 处理：null stdin 避免不必要的可继承管道句柄。

长期建议
- 根本解决方案应使用 CreateProcessW 的 PROCESS_HANDLE_LIST 属性，显式枚举需要继承的三个 stdio 句柄，并将 bInheritHandles 设置为 FALSE 以禁用其他句柄的继承。该方向在 rust-lang/rust#146407 跟踪中存在，待稳定后再替换 Windows 的 spawn 实现路径（在 build_git_command() 中的实现）。
