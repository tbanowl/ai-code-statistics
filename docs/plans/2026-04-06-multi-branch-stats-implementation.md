# Git Blame 多分支统计实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标：** 支持通过配置表指定要统计的分支，默认统计所有分支

**架构：** 新增分支配置表，改进克隆策略使用 shallow-since，在任务中遍历分支逐个统计并独立保存结果

**技术栈：** Python, SQLAlchemy, Git, SQLite/PostgreSQL

---

## Task 1: 创建数据库迁移脚本

**Files:**
- Create: `sql/migrations/add_branch_config_table_sqlite.sql`
- Create: `sql/migrations/add_branch_config_table_postgresql.sql`

**Step 1: 创建 SQLite 迁移脚本**

```sql
-- sql/migrations/add_branch_config_table_sqlite.sql
CREATE TABLE IF NOT EXISTS stats_repo_branch_config (
    id VARCHAR(20) PRIMARY KEY,
    repo_id VARCHAR(20) NOT NULL,
    branch_pattern TEXT NOT NULL,
    pattern_type VARCHAR(20) NOT NULL DEFAULT 'exact',
    enabled INTEGER DEFAULT 1,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    FOREIGN KEY (repo_id) REFERENCES stats_repositories(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_repo_branch_config_repo ON stats_repo_branch_config(repo_id);
CREATE INDEX IF NOT EXISTS idx_repo_branch_config_enabled ON stats_repo_branch_config(repo_id, enabled);
```

**Step 2: 创建 PostgreSQL 迁移脚本**

```sql
-- sql/migrations/add_branch_config_table_postgresql.sql
CREATE TABLE IF NOT EXISTS stats_repo_branch_config (
    id VARCHAR(20) PRIMARY KEY,
    repo_id VARCHAR(20) NOT NULL,
    branch_pattern TEXT NOT NULL,
    pattern_type VARCHAR(20) NOT NULL DEFAULT 'exact',
    enabled INTEGER DEFAULT 1,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    FOREIGN KEY (repo_id) REFERENCES stats_repositories(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_repo_branch_config_repo ON stats_repo_branch_config(repo_id);
CREATE INDEX IF NOT EXISTS idx_repo_branch_config_enabled ON stats_repo_branch_config(repo_id, enabled);
```

**Step 3: 提交迁移脚本**

```bash
git add sql/migrations/
git commit -m "feat: add branch config table migration scripts"
```

---

## Task 2: 创建数据模型

**Files:**
- Modify: `core/database/models.py`

**Step 1: 添加 StatsRepoBranchConfig 模型**

在 `core/database/models.py` 中添加：

```python
class StatsRepoBranchConfig(Base):
    """仓库分支配置表"""
    __tablename__ = 'stats_repo_branch_config'

    id = Column(String(20), primary_key=True)
    repo_id = Column(String(20), ForeignKey('stats_repositories.id', ondelete='CASCADE'), nullable=False)
    branch_pattern = Column(Text, nullable=False)
    pattern_type = Column(String(20), nullable=False, default='exact')
    enabled = Column(Integer, default=1)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)

    # 关系
    repository = relationship('StatsRepository', back_populates='branch_configs')
```

**Step 2: 在 StatsRepository 模型中添加关系**

在 `StatsRepository` 类中添加：

```python
# 在 StatsRepository 类中添加
branch_configs = relationship('StatsRepoBranchConfig', back_populates='repository', cascade='all, delete-orphan')
```

**Step 3: 提交模型变更**

```bash
git add core/database/models.py
git commit -m "feat: add StatsRepoBranchConfig model"
```

---

## Task 3: 实现 BlameStatsDatabase 分支配置方法

**Files:**
- Modify: `core/database/blame_stats_db.py`

**Step 1: 添加 get_repo_branch_configs 方法**

```python
def get_repo_branch_configs(self, repo_id: str) -> list:
    """
    获取仓库的分支配置
    
    Args:
        repo_id: 仓库 ID
    
    Returns:
        分支配置列表
    """
    from core.database.models import StatsRepoBranchConfig
    
    with self.session_scope() as session:
        configs = (
            session.query(StatsRepoBranchConfig)
            .filter(
                StatsRepoBranchConfig.repo_id == repo_id,
                StatsRepoBranchConfig.enabled == 1
            )
            .all()
        )
        
        return [
            {
                'id': c.id,
                'branch_pattern': c.branch_pattern,
                'pattern_type': c.pattern_type,
                'enabled': c.enabled
            }
            for c in configs
        ]
```

**Step 2: 添加 save_repo_branch_config 方法**

```python
def save_repo_branch_config(
    self,
    repo_id: str,
    branch_pattern: str,
    pattern_type: str = 'exact',
    enabled: int = 1
) -> str:
    """
    保存分支配置
    
    Args:
        repo_id: 仓库 ID
        branch_pattern: 分支模式
        pattern_type: 模式类型
        enabled: 是否启用
    
    Returns:
        配置 ID
    """
    from core.database.models import StatsRepoBranchConfig
    
    now = int(time.time() * 1000)
    
    with self.session_scope() as session:
        config = StatsRepoBranchConfig(
            id=gen_xid(),
            repo_id=repo_id,
            branch_pattern=branch_pattern,
            pattern_type=pattern_type,
            enabled=enabled,
            created_at=now,
            updated_at=now
        )
        session.add(config)
        session.flush()
        
        return config.id
```

**Step 3: 添加 delete_repo_branch_configs 方法**

```python
def delete_repo_branch_configs(self, repo_id: str) -> None:
    """
    删除仓库的所有分支配置
    
    Args:
        repo_id: 仓库 ID
    """
    from core.database.models import StatsRepoBranchConfig
    
    with self.session_scope() as session:
        session.query(StatsRepoBranchConfig).filter(
            StatsRepoBranchConfig.repo_id == repo_id
        ).delete()
```

**Step 4: 提交数据库方法**

```bash
git add core/database/blame_stats_db.py
git commit -m "feat: add branch config database methods"
```

---

## Task 4: 改进 GitCloneService 克隆策略

**Files:**
- Modify: `core/services/git_clone_service.py`

**Step 1: 修改 clone_with_ssh_key 方法参数**

将 `depth` 参数改为 `shallow_since`：

```python
def clone_with_ssh_key(
    self,
    repo_url: str,
    private_key: str,
    target_dir: str,
    shallow_since: str = '2026-03-20'
) -> bool:
    """
    使用指定 SSH Key 克隆仓库

    Args:
        repo_url: Git 仓库 URL
        private_key: SSH 私钥内容
        target_dir: 目标目录
        shallow_since: 浅克隆起始日期（默认 2026-03-20）

    Returns:
        是否成功克隆
    """
    temp_key_file = None
    try:
        temp_key_file = self._write_private_key_to_temp(private_key)
        ssh_command = self._create_ssh_command(temp_key_file)
        
        env = os.environ.copy()
        env['GIT_SSH_COMMAND'] = ssh_command
        
        # 使用 shallow-since 替代 depth
        cmd = ['git', 'clone', '--shallow-since', shallow_since, repo_url, target_dir]
        
        self.logger.info(f"开始克隆仓库: {repo_url} (shallow-since: {shallow_since})")
        
        result = subprocess.run(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            self.logger.error(f"克隆失败: {result.stderr}")
            return False
        
        self.logger.info(f"仓库克隆成功: {target_dir}")
        return True
        
    except subprocess.TimeoutExpired:
        self.logger.error("克隆超时")
        return False
    except Exception as e:
        self.logger.error(f"克隆过程中出错: {e}")
        return False
    finally:
        if temp_key_file and os.path.exists(temp_key_file):
            os.unlink(temp_key_file)
```

**Step 2: 提交克隆策略变更**

```bash
git add core/services/git_clone_service.py
git commit -m "feat: change clone strategy from depth to shallow-since"
```

---

## Task 5: 实现 GitCloneService 分支操作方法

**Files:**
- Modify: `core/services/git_clone_service.py`

**Step 1: 添加 list_branches 方法**

```python
def list_branches(self, repo_dir: str) -> list:
    """
    列出仓库所有远程分支
    
    Args:
        repo_dir: 仓库目录
    
    Returns:
        分支名称列表（去除 origin/ 前缀）
    """
    try:
        result = subprocess.run(
            ['git', 'branch', '-r', '--format=%(refname:short)'],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            self.logger.error(f"列出分支失败: {result.stderr}")
            return []
        
        branches = result.stdout.strip().split('\n')
        branches = [b.strip() for b in branches if b.strip()]
        
        # 去除 origin/ 前缀
        branches = [b.replace('origin/', '') for b in branches if b.startswith('origin/')]
        
        # 过滤 HEAD
        branches = [b for b in branches if b != 'HEAD']
        
        return branches
        
    except Exception as e:
        self.logger.error(f"列出分支时出错: {e}")
        return []
```

**Step 2: 添加 checkout_branch 方法**

```python
def checkout_branch(self, repo_dir: str, branch: str) -> bool:
    """
    切换到指定分支
    
    Args:
        repo_dir: 仓库目录
        branch: 分支名称
    
    Returns:
        是否成功切换
    """
    try:
        result = subprocess.run(
            ['git', 'checkout', branch],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            self.logger.error(f"切换分支失败: {result.stderr}")
            return False
        
        self.logger.info(f"成功切换到分支: {branch}")
        return True
        
    except Exception as e:
        self.logger.error(f"切换分支时出错: {e}")
        return False
```

**Step 3: 添加 match_branches 方法**

```python
def match_branches(
    self,
    all_branches: list,
    branch_configs: list
) -> list:
    """
    根据配置匹配分支
    
    Args:
        all_branches: 所有分支列表
        branch_configs: 分支配置列表
    
    Returns:
        匹配的分支列表
    """
    import fnmatch
    
    matched = set()
    
    for config in branch_configs:
        pattern = config['branch_pattern']
        pattern_type = config['pattern_type']
        
        if pattern_type == 'special':
            if pattern == 'all':
                # 返回所有分支
                return all_branches
        elif pattern_type == 'exact':
            # 精确匹配
            if pattern in all_branches:
                matched.add(pattern)
        elif pattern_type == 'wildcard':
            # 通配符匹配
            for branch in all_branches:
                if fnmatch.fnmatch(branch, pattern):
                    matched.add(branch)
    
    return list(matched)
```

**Step 4: 提交分支操作方法**

```bash
git add core/services/git_clone_service.py
git commit -m "feat: add branch listing, checkout and matching methods"
```

---

## Task 6: 修改 GitBlameStatsTask 支持多分支统计

**Files:**
- Modify: `core/scheduler/tasks/git_blame_stats_task.py`

**Step 1: 修改 _stat_repository 方法签名和克隆调用**

找到 `_stat_repository` 方法，修改克隆部分：

```python
# 原代码：
if not self.git_clone_service.clone_with_ssh_key(
    repo_path,
    ssh_key_info['private_key'],
    temp_dir
):

# 改为：
if not self.git_clone_service.clone_with_ssh_key(
    repo_path,
    ssh_key_info['private_key'],
    temp_dir,
    shallow_since='2026-03-20'
):
```

**Step 2: 在克隆后添加分支配置获取逻辑**

在克隆成功后，添加：

```python
# 获取分支配置
branch_configs = self.blame_stats_db.get_repo_branch_configs(repo_id)

# 确定要统计的分支列表
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
```

**Step 3: 提交分支配置获取逻辑**

```bash
git add core/scheduler/tasks/git_blame_stats_task.py
git commit -m "feat: add branch config retrieval and matching logic"
```

---

## Task 7: 实现多分支遍历统计逻辑

**Files:**
- Modify: `core/scheduler/tasks/git_blame_stats_task.py`

**Step 1: 替换单次统计为循环统计**

将原来的单次 `analyze_repository` 调用改为循环：

```python
# 获取统计配置
config = load_config()
file_filter = config.get('blame_stats', {}).get('file_filter', {})
repo_url = self.blame_stats_db.get_repository_repo_url(repo_id)

# 遍历每个分支进行统计
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
```

**Step 2: 修改返回值为多分支汇总**

```python
# 返回汇总信息
return {
    'success': failed_count == 0,
    'total_branches': len(target_branches),
    'success_branches': success_count,
    'failed_branches': failed_count,
    'branch_results': branch_results
}
```

**Step 3: 提交多分支统计逻辑**

```bash
git add core/scheduler/tasks/git_blame_stats_task.py
git commit -m "feat: implement multi-branch statistics loop"
```

---

## Task 8: 添加 _save_branch_stats 辅助方法

**Files:**
- Modify: `core/scheduler/tasks/git_blame_stats_task.py`

**Step 1: 提取保存逻辑为独立方法**

在 `GitBlameStatsTask` 类中添加：

```python
def _save_branch_stats(
    self,
    repo_id: str,
    stat_date: int,
    result
) -> None:
    """
    保存分支统计结果
    
    Args:
        repo_id: 仓库 ID
        stat_date: 统计日期
        result: 分析结果
    """
    # 保存仓库级统计结果
    self.blame_stats_db.save_repo_blame_stats(
        repo_id=repo_id,
        stat_date=stat_date,
        commit_sha=result.commit_sha,
        branch=result.branch,
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
    
    # 保存仓库贡献者统计结果
    contributor_ids = {}
    for contrib_key, stats in result.contributor_stats.items():
        contrib_id = self.blame_stats_db.get_or_create_contributor(
            'Unknown',
            None
        )
        contributor_ids[contrib_key] = contrib_id
        
        contrib_name = f'Contributor_{contrib_key[:8]}'
        contrib_email = ""
        
        self.blame_stats_db.save_repo_contributor_stats(
            repo_id=repo_id,
            stat_date=stat_date,
            contributor_id=contrib_id,
            contributor_name=contrib_name,
            contributor_email=contrib_email,
            ai_lines=stats['ai_lines'],
            non_ai_lines=stats['non_ai_lines'],
            total_lines=stats['total_lines']
        )
    
    # 保存文件贡献者统计
    file_records = self.blame_stats_db.get_file_blame_stats(repo_id, stat_date)
    file_id_map = {r['file_path']: r['id'] for r in file_records}
    
    file_contributor_stats = []
    for file_result in result.files_results:
        file_id = file_id_map.get(file_result.file_path)
        if not file_id:
            continue
        
        for contrib_key, stats in file_result.contributor_stats.items():
            contrib_id = contributor_ids.get(contrib_key)
            
            file_contributor_stats.append({
                'file_id': file_id,
                'stat_date': stat_date,
                'repo_id': repo_id,
                'file_path': file_result.file_path,
                'contributor_id': contrib_id,
                'contributor_name': f'Contributor_{contrib_key[:8]}',
                'contributor_email': None,
                'ai_lines': stats['ai_lines'],
                'non_ai_lines': stats['non_ai_lines'],
                'total_lines': stats['total_lines']
            })
    
    if file_contributor_stats:
        self.blame_stats_db.save_batch_file_contributor_stats(
            file_contributor_stats
        )
```

**Step 2: 提交辅助方法**

```bash
git add core/scheduler/tasks/git_blame_stats_task.py
git commit -m "feat: extract branch stats saving logic to helper method"
```

---

## Task 9: 更新任务汇总日志

**Files:**
- Modify: `core/scheduler/tasks/git_blame_stats_task.py`

**Step 1: 修改 execute 方法中的日志输出**

找到任务完成后的日志输出，修改为包含分支信息：

```python
if result:
    success_repos += 1
    self.logger.info(
        f"仓库 {repo_name} 统计完成: "
        f"成功分支 {result.get('success_branches', 0)}/{result.get('total_branches', 0)}"
    )
else:
    failed_repos += 1
```

**Step 2: 提交日志更新**

```bash
git add core/scheduler/tasks/git_blame_stats_task.py
git commit -m "feat: update task summary logs with branch info"
```

---

## Task 10: 运行数据库迁移

**Step 1: 执行 SQLite 迁移**

```bash
sqlite3 data/ai_stats.db < sql/migrations/add_branch_config_table_sqlite.sql
```

预期输出：无错误

**Step 2: 验证表创建**

```bash
sqlite3 data/ai_stats.db "SELECT name FROM sqlite_master WHERE type='table' AND name='stats_repo_branch_config';"
```

预期输出：`stats_repo_branch_config`

**Step 3: 提交迁移记录**

```bash
git add -A
git commit -m "chore: run database migration for branch config table"
```

---

## Task 11: 测试多分支统计功能

**Step 1: 手动插入测试配置**

```bash
sqlite3 data/ai_stats.db "INSERT INTO stats_repo_branch_config (id, repo_id, branch_pattern, pattern_type, enabled, created_at, updated_at) VALUES ('test001', 'your_repo_id', 'main', 'exact', 1, $(date +%s)000, $(date +%s)000);"
```

**Step 2: 运行定时任务测试**

```bash
python -c "
from core.scheduler.tasks.git_blame_stats_task import GitBlameStatsTask
from core.config import load_config
config = load_config()
task = GitBlameStatsTask(config)
result = task.execute()
print(result)
"
```

预期：任务成功执行，日志显示分支统计信息

**Step 3: 验证数据库结果**

```bash
sqlite3 data/ai_stats.db "SELECT repo_id, branch, total_lines, ai_lines FROM stats_blame_repo ORDER BY created_at DESC LIMIT 5;"
```

预期：看到不同分支的统计记录

---

## 完成

所有任务完成后，多分支统计功能已实现。关键变更：
- 新增分支配置表和模型
- 克隆策略从 depth 改为 shallow-since
- 支持精确、通配符、特殊标记三种分支匹配
- 每个分支独立统计和保存结果
- 默认统计所有分支
