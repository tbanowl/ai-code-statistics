# Gitea Provider 设计文档

## 概述

为 `core/git_providers` 模块添加 Gitea 平台支持，使系统能够从 Gitea 实例获取代码统计数据。

## 背景

当前系统已支持 GitLab，需要扩展支持 Gitea 平台。Gitea API 与 GitLab API 有相似之处，但在认证方式、端点路径和响应格式上存在差异。

## 架构设计

### 新增组件

1. **`core/git_providers/gitea.py`** - GiteaProvider 类实现
2. **`core/git_providers/factory.py`** - 更新工厂方法支持 Gitea 类型

### GiteaProvider 类结构

```python
class GiteaProvider(GitProvider):
    """Gitea API 实现"""

    def __init__(self, config: Dict):
        self.api_base = f"{self.base_url.rstrip('/')}/api/v1"
        self.timeout = config.get('api_timeout', 30)
```

### API 端点映射

| 方法 | GitLab 端点 | Gitea 端点 | 说明 |
|------|-------------|-----------|------|
| get_project_info | GET `/projects/{id}` | GET `/repos/{owner}/{repo}` | Gitea 使用 owner/repo 格式 |
| get_projects | GET `/projects` | GET `/repos/search` | 搜索/列出仓库 |
| get_commits | GET `/projects/{id}/repository/commits` | GET `/repos/{owner}/{repo}/commits` | 获取提交列表 |
| get_ai_notes | GET `/projects/{id}/repository/notes/ai/{sha}` | GET `/repos/{owner}/{repo}/git/notes/{ref}/{sha}` | Gitea Notes 支持有限 |
| validate_connection | GET `/user` | GET `/user` | 验证认证 |

## 关键实现细节

### 认证方式

- **GitLab**: `headers = {"PRIVATE-TOKEN": self.token}`
- **Gitea**: `headers = {"Authorization": f"token {self.token}"}`

### 项目标识符

- **GitLab**: 数字 ID (如 `123`)
- **Gitea**: `owner/repo` 格式 (如 `gitea/admin`)

### Notes API 处理

Gitea 对 Git Notes 的支持比 GitLab 有限：
- 需要处理可能的 404 响应
- 解析格式可能与 GitLab 不同
- 返回 `None` 当不可用时

### 分页处理

- **GitLab**: 响应头 `X-Total`
- **Gitea**: 响应头 `X-Total-Count`

## 配置示例

```yaml
git:
  type: gitea
  gitea:
    base_url: https://gitea.example.com
    token: your_gitea_token
    api_timeout: 30
```

## 兼容性

- Python 3.8+
- Gitea API v1.20+
- requests 库

## 后续步骤

1. 创建 `gitea.py` 实现文件
2. 更新 `factory.py` 添加 Gitea 支持
3. 更新 `__init__.py` 导出 GiteaProvider
4. 编写单元测试
5. 更新配置文档
