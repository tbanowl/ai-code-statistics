# Git Blame 多分支统计配置设计

## 设计日期
2026-04-06

## 背景
当前 Git Blame 统计任务只统计主分支的代码量，需要支持通过配置表指定要统计的分支。如果配置表中没有指定分支，默认统计所有分支。

## 需求概述
1. 支持按仓库配置要统计的分支
2. 支持三种分支指定方式：
   - 精确匹配（如：main, develop）
   - 模式匹配（如：feature/*, release/*）
   - 特殊标记（如：all 表示所有分支）
3. 每个分支的统计结果独立存储
4. 分支不存在时跳过并记录警告
5. 无配置时默认统计所有分支

## 架构设计

### 1. 数据库设计

#### 新增配置表：stats_repo_branch_config

```sql
CREATE TABLE IF NOT EXISTS stats_repo_branch_config (
    -- 主键
    id VARCHAR(20) PRIMARY KEY,
    -- 仓库 ID
    repo_id VARCHAR(20) NOT NULL,
    -- 分支模式（具体分支名或通配符）
    branch_pattern TEXT NOT NULL,
    -- 模式类型：exact(精确), wildcard(通配符), special(特殊标记如all)
    pattern_type VARCHAR(20) NOT NULL DEFAULT 'exact',
    -- 是否启用
    enabled INTEGER DEFAULT 1,
    -- 创建时间戳（毫秒）
    created_at BIGINT NOT NULL,
    -- 更新时间戳（毫秒）
    updated_at BIGINT NOT NULL,
    
    FOREIGN KEY (repo_id) REFERENCES stats_repositories(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_repo_branch_config_repo ON stats_repo_branch_config(repo_id);
CREATE INDEX IF NOT EXISTS idx_repo_branch_config_enabled ON stats_repo_branch_config(repo_id, enabled);
```

#### 配置示例

| repo_id | branch_pattern | pattern_type | enabled |
|---------|---------------|--------------|---------|
| repo_1  | main          | exact        | 1       |
| repo_1  | develop       | exact        | 1       |
| repo_2  | feature/*     | wildcard     | 1       |
| repo_3  | all           | special      | 1       |

#### 现有表调整

`stats_blame_repo` 表已有 `branch` 字段，无需修改表结构。每个分支的统计结果通过 `repo_id + stat_date + branch` 唯一标识。

### 2. 克隆策略调整

#### 当前实现
```python
git clone --depth 1 <repo_url> <target_dir>
```

#### 改进后
```python
git clone --shallow-since 2026-03-20 <repo_url> <target_dir>
```

**优势：**
- 获取指定日期后所有分支的提交历史
- 支持多分支切换统计
- 相比完整克隆节省空间和时间

**固定日期：** 2026-03-20（后续可配置化）

### 3. 服务层设计

#### GitCloneService 新增方法

```python
def clone_with_ssh_key(
    self,
    repo_url: str,
    private_key: str,
    target_dir: str,
    shallow_since: str = '2026-03-20'
) -> bool:
    """使用 shallow-since 克隆仓库"""
    cmd = ['git', 'clone', '--shallow-since', shallow_since, repo_url, target_dir]
    # ... 执行克隆

def list_branches(self, repo_dir: str) -> list:
    """列出仓库所有远程分支"""
    # git branch -r --format='%(refname:short)'
    # 返回 ['origin/main', 'origin/develop', ...]
    # 去除 'origin/' 前缀

def checkout_branch(self, repo_dir: str, branch: str) -> bool:
    """切换到指定分支"""
    # git checkout <branch>
    # 返回是否成功

def match_branches(
    self,
    all_branches: list,
    branch_configs: list
) -> list:
    """根据配置匹配分支"""
    # 遍历 branch_configs，根据 pattern_type 匹配分支
    # exact: 精确匹配
    # wildcard: 使用 fnmatch 模式匹配
    # special: 'all' 返回所有分支
```

#### BlameStatsDatabase 新增方法

```python
def get_repo_branch_configs(self, repo_id: str) -> list:
    """获取仓库的分支配置"""
    # 查询 stats_repo_branch_config 表
    # WHERE repo_id = ? AND enabled = 1
    # 返回 [{'branch_pattern': 'main', 'pattern_type': 'exact'}, ...]

def save_repo_branch_config(
    self,
    repo_id: str,
    branch_pattern: str,
    pattern_type: str = 'exact',
    enabled: int = 1
) -> str:
    """保存分支配置"""
    # 插入到 stats_repo_branch_config 表
    # 返回配置 ID

def delete_repo_branch_configs(self, repo_id: str) -> None:
    """删除仓库的所有分支配置"""
    # DELETE FROM stats_repo_branch_config WHERE repo_id = ?

def delete_daily_repo_stats(
    self,
    repo_id: str,
    stat_date: int,
    branch: str = None
) -> None:
    """删除仓库级别的当天统计结果"""
    # 如果指定 branch，只删除该分支的数据
    # 如果不指定，删除所有分支的数据
```

### 4. 任务执行流程

#### GitBlameStatsTask._stat_repository 改进

```python
def _stat_repository(
    self,
    repo_id: str,
    repo_path: str,
    stat_date: int,
    ssh_key_info: Dict
) -> Dict | None:
    """统计单个仓库的多个分支"""
    
    temp_dir = None
    try:
        # 1. 创建临时目录并克隆仓库
        temp_dir = tempfile.mkdtemp(prefix='git_blame_')
        
        if not self.git_clone_service.clone_with_ssh_key(
            repo_path,
            ssh_key_info['private_key'],
            temp_dir,
            shallow_since='2026-03-20'
        ):
            self.logger.error("仓库克隆失败")
            return None
        
        # 2. 获取分支配置
        branch_configs = self.blame_stats_db.get_repo_branch_configs(repo_id)
        
        # 3. 确定要统计的分支列表
        all_branches = self.git_clone_service.list_branches(temp_dir)
        
        if not branch_configs:
            # 默认：统计所有分支
            target_branches = all_branches
            self.logger.info(f"未配置分支，将统计所有 {len(all_branches)} 个分支")
        else:
            # 根据配置匹配分支
            target_branches = self.git_clone_service.match_branches(
                all_branches,
                branch_configs
            )
            self.logger.info(f"根据配置匹配到 {len(target_branches)} 个分支")
        
        if not target_branches:
            self.logger.warning("没有匹配到任何分支")
            return None
        
        # 4. 获取统计配置
        config = load_config()
        file_filter = config.get('blame_stats', {}).get('file_filter', {})
        repo_url = self.blame_stats_db.get_repository_repo_url(repo_id)
        
        # 5. 遍历每个分支进行统计
        branch_results = {}
        success_count = 0
        failed_count = 0
        
        for branch in target_branches:
            self.logger.info(f"开始统计分支: {branch}")
            
            # 切换分支
            if not self.git_clone_service.checkout_branch(temp_dir, branch):
                self.logger.warning(f"分支 {branch} 切换失败，跳过")
                failed_count += 1
                continue
            
            # 统计该分支
            result = self.blame_stats_service.analyze_repository(
                repo_url,
                temp_dir,
                stat_date,
                file_filter
            )
            
            if not result:
                self.logger.error(f"分支 {branch} 分析失败")
                failed_count += 1
                continue
            
            # 保存该分支的统计结果
            self._save_branch_stats(repo_id, stat_date, result)
            
            branch_results[branch] = {
                'total_lines': result.total_lines,
                'ai_lines': result.ai_lines,
                'non_ai_lines': result.non_ai_lines,
                'ai_ratio': round(
                    (result.ai_lines / result.total_lines * 100) if result.total_lines > 0 else 0.0,
                    2
                )
            }
            success_count += 1
            
            self.logger.info(
                f"分支 {branch} 统计完成: "
                f"总行数={result.total_lines}, "
                f"AI 行数={result.ai_lines}, "
                f"AI 占比={branch_results[branch]['ai_ratio']}%"
            )
        
        # 6. 返回汇总信息
        return {
            'success': failed_count == 0,
            'total_branches': len(target_branches),
            'success_branches': success_count,
            'failed_branches': failed_count,
            'branch_results': branch_results
        }
        
    except Exception as e:
        self.logger.error(f"统计仓库时出错: {e}", exc_info=True)
        return None
    
    finally:
        # 清理临时目录
        if temp_dir and os.path.exists(temp_dir):
            self.git_clone_service.cleanup_temp_dir(temp_dir)

def _save_branch_stats(
    self,
    repo_id: str,
    stat_date: int,
    result: RepoBlameResult
) -> None:
    """保存分支统计结果（复用现有逻辑）"""
    # 保存仓库级统计结果
    self.blame_stats_db.save_repo_blame_stats(
        repo_id=repo_id,
        stat_date=stat_date,
        commit_sha=result.commit_sha,
        branch=result.branch,  # 关键：branch 字段
        total_lines=result.total_lines,
        ai_lines=result.ai_lines,
        non_ai_lines=result.non_ai_lines,
        total_files=result.total_files
    )
    
    # 保存文件级统计结果
    for file_result in result.files_results:
        self.blame_stats_db.save_file_blame_stats(
            repo_id=repo_id,
            stat_date=stat_date,
            file_path=file_result.file_path,
            commit_sha=file_result.commit_sha,
            total_lines=file_result.total_lines,
            ai_lines=file_result.ai_lines,
            non_ai_lines=file_result.non_ai_lines
        )
    
    # 保存贡献者统计（省略，与现有逻辑相同）
    # ...
```

### 5. API 接口（可选）

为方便管理分支配置，可新增以下 API：

```python
# POST /api/repos/{repo_id}/branch-config
# 请求体：
{
    "branch_pattern": "main",
    "pattern_type": "exact",
    "enabled": 1
}

# GET /api/repos/{repo_id}/branch-config
# 返回：
{
    "configs": [
        {
            "id": "xxx",
            "branch_pattern": "main",
            "pattern_type": "exact",
            "enabled": 1
        }
    ]
}

# DELETE /api/repos/{repo_id}/branch-config/{config_id}
# 删除指定配置

# DELETE /api/repos/{repo_id}/branch-config
# 删除仓库的所有分支配置
```

## 数据流

```
1. 定时任务触发
   ↓
2. 获取待统计仓库列表
   ↓
3. 对每个仓库：
   a. 克隆仓库（shallow-since）
   b. 查询分支配置
   c. 匹配目标分支列表
   d. 遍历每个分支：
      - 切换分支
      - 执行 blame 分析
      - 保存统计结果（独立记录）
   e. 清理临时目录
   ↓
4. 返回任务执行结果
```

## 错误处理

1. **分支不存在**：跳过该分支，记录警告日志，继续统计其他分支
2. **分支切换失败**：跳过该分支，记录警告日志
3. **分支分析失败**：跳过该分支，记录错误日志
4. **克隆失败**：整个仓库标记为失败
5. **无匹配分支**：记录警告，返回 None

## 兼容性

1. **现有数据**：`stats_blame_repo` 表已有 `branch` 字段，现有数据保持不变
2. **现有任务**：未配置分支的仓库自动统计所有分支（行为变更，需注意）
3. **API 兼容**：查询接口需支持按 branch 过滤

## 性能考虑

1. **克隆时间**：使用 `--shallow-since` 比完整克隆快，但比 `--depth=1` 慢
2. **切换分支**：本地切换速度快，对性能影响小
3. **统计时间**：与分支数量成正比，建议限制单个仓库的分支数（如 < 20）
4. **磁盘空间**：临时目录占用增加，需及时清理

## 后续优化

1. **配置化日期**：将 `shallow-since` 日期从硬编码改为配置项
2. **并行统计**：多个分支可并行统计（需要多个临时目录）
3. **增量统计**：已统计过的分支可跳过（需要记录上次统计的 commit）
4. **分支数量限制**：在配置层面限制单个仓库的分支数量
5. **统计结果聚合**：提供跨分支的汇总统计视图

## 实施计划

1. 创建数据库迁移脚本（SQLite + PostgreSQL）
2. 实现 GitCloneService 新方法
3. 实现 BlameStatsDatabase 新方法
4. 修改 GitBlameStatsTask 执行逻辑
5. 编写单元测试
6. 更新 API 文档
7. 部署和验证

## 风险评估

**低风险：**
- 数据库表结构变更（新增表，不影响现有表）
- 服务层新增方法（不影响现有功能）

**中风险：**
- 克隆策略变更（从 depth 改为 shallow-since）
- 默认行为变更（从单分支改为所有分支）

**建议：**
- 先在测试环境验证
- 提供配置开关控制新旧行为
- 监控任务执行时间和资源占用
