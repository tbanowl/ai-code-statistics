# 安装

下载解压最新版本的 git-ai.7z 后，进入解压后的 git-ai 目录 , 使用管理员打开 powershell ，执行 install.ps1 脚本，注意 install.ps1 和 git-ai-windows-x64.exe 文件必须在同一目录内，并且不要修改 git-ai-windows-x64.exe 的文件名， 脚本执行后需要关闭终端重新打开，才会加载环境变量。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command ./install.ps1
```

如果提示 powershell 提示禁止运行脚本，请先执行以下命令。

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```

安装成功如下：

![install-success](./assets/docs/install-success.png)

安装过程中如果有以下红色内容输出，就代表系统环境变量没有配置成功，请使用管理员权限执行 install.ps1 脚本，或者按照非管理员方式配置环境变量。

![install-error](./assets/docs/install-error.png)

## 非管理员权限配置系统环境变量

如果是非管理员用户，在执行安装脚本后，需要手动配置一下，使用长鑫安装助手软件管理中的修改系统环境变量，将安装后的 git-ai的路径配置到系统环境变量 PATH 的最前面。git-ai 的安装路径在当前用户目录下的 .git-ai 目录。
`git-ai` 路径示例：C:\Users\vendor.mrdit.dk03\.git-ai\bin
系统环境变量配置后，可以重新打开 cmd 或 powershell，打印输出 PATH 环境变量，查看 git-ai 的路径是否在 git 路径的前面。

```cmd
echo %PATH%
```

```powershell
$env:PATH
```

输出示例，git-ai 的路径在 git 的前面：

```
...C:\Users\vendor.mrdit.dk03\.git-ai\bin;...C:\Program Files\Git\cmd;...
```


![install-env-1](./assets/docs/install-env-1.png)

![install-env-2](./assets/docs/install-env-2.png)

![install-env-3](./assets/docs/install-env-3.png)

## 验证

### 验证 git-ai 是否安装成功
执行 git-ai --version验证 git-ai 是否安装成功，如果正常输出版本号则安装成功。

命令：

```bash
git-ai --version
```

输出示例：

```
1.1.22
```

### 验证数据上传配置

执行 git-ai login 命令验证是否已登录。只有在登录后数据才会上传到服务器。

```
git-ai login
```

输出：

```
Already logged in. Use 'git-ai logout' to log out first.
```

### 验证 git 路径

执行 where.exe git 验证 git 是否在 git-ai 路径下，如果第一行输出的是 git-ai 路径下的 git 就代表没问题。

命令：

```
where.exe git
```

输出示例，第一行是 git-ai 路径下的代理 git 文件：

```
C:\Users\vendor.mrdit.dk03\.git-ai\bin\git.exe
C:\Program Files\Git\cmd\git.exe
```
### Bash 配置

查看当前用户目录下 `.basrc` 文件中是否到配置 `git-ai` 的环境变量，因为 claude code 在 Windows 系统中使用的终端程序是 `git-bash`，会加载 `bash` 相关的配置，需要保证 `git-ai` 的安装路径在 `PATH` 的最前面，保证执行的是 `git-ai` 的 `git` 程序

```
cat ~\.bashrc
```

命令执行后查看输出中是否有以下内容

```
export PATH="$HOME/.git-ai/bin:$PATH"
```

### 验证 Cluade Code  是否正确调用 Git-AI

在 git 项目中使用 Cluade Code 生成代码后，在对应的项目路径下使用 cmd 或 powershell 执行 git-ai status 命令验证调用。

```
git-ai status
```

```
输出：
you  ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ ai
   4%                                   96%
   100% AI code accepted | waited 33s for ai

29 secs ago     +103      0  Claude claude-4.5-opus-high-thinking
46 secs ago       +2     -1  Claude claude-4.5-opus-high-thinking
57 secs ago      +12     -2  Claude claude-4.5-opus-high-thinking
1 mins ago        +1     -2  Aidan Cunniffe
2 mins ago       +53      0  Claude claude-4.5-opus-high-thinking
2 mins ago         0     -3  Claude claude-4.5-opus-high-thinking
2 mins ago        +4     -6  Claude claude-4.5-opus-high-thinking
3 mins ago        +2     -1  Claude claude-4.5-opus-high-thinking
5 mins ago        +6    -16  Claude claude-opus-4-5-20251101
5 mins ago         0     -2  Aidan Cunniffe
```

如果正确，应该能看到几个当前未提交的代码变更检查点，检查点不是最终的统计结果。如果没有，说明 Claude code 的 Hooks 没有正确安装。执行 git-ai install-hooks 重新安装 Hooks。

```cmd
git-ai install-hooks
```

在 Claude Code 配置文件中确认是否安装 git-ai 的 hooks，如果没有可以执行 git-ai install-hooks 重新安装 Hooks。

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "hooks": [
          {
            "command": "git-ai checkpoint claude --hook-input stdin",
            "type": "command"
          }
        ],
        "matcher": "Write|Edit|MultiEdit"
      }
    ],
    "PreToolUse": [
      {
        "hooks": [
          {
            "command": "git-ai checkpoint claude --hook-input stdin",
            "type": "command"
          }
        ],
        "matcher": "Write|Edit|MultiEdit"
      }
    ]
  }
}
```

## 注意事项

1. 执行 install.ps1 脚本时，git-ai-windows-x64.exe 和 install.ps1 文件必须在同一个目录内，并且不要修改 git-ai-windows-x64.exe文件名
2. install.ps1 脚本执行成功后，终端或 IDE 需要关闭重新打开才会重新加载环境变量
3. 非管理员用户需要借助长鑫助手配置环境变量
4. 一定要执行 where.exe git 命令并确认控制台输出的第一行路径的 git 是 git-ai 目录下的
5. 如果 IDE 中配置了 git 路径，请修改为 git-ai 下的 git

