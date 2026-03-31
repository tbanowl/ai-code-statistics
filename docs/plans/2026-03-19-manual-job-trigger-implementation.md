# 定时任务手动执行功能实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为调度器 API 添加手动触发定时任务的功能，支持异步执行、并发控制和执行历史查询。

**Architecture:** 使用 APScheduler.trigger_job() 触发任务，新增 task_executions 表存储执行记录，通过 BaseTask 钩子更新状态。

**Tech Stack:** Flask, APScheduler, SQLite (可扩展到 PostgreSQL/MySQL), Python 3.8+

---

### Task 1: 更新数据库 Schema 添加 task_executions 表

**Files:**
- Modify: `sql/metrics_schema_sqlite.sql`

**Step 1: 在 metrics_schema_sqlite.sql 末尾添加 task_executions 表定义**

找到文件末尾 `-- ============================================================================` 之前，添加以下内容：

```sql
-- ============================================================================
-- Task Executions 表（任务执行记录）
-- ============================================================================

CREATE TABLE IF NOT EXISTS task_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at DATETIME,
    finished_at DATETIME,
    error_message TEXT,
    execution_time_ms INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- task_executions 字段说明:
-- id - 主键，自增 ID
-- job_id - 任务 ID（对应 APScheduler 的 job_id）
-- status - 执行状态: pending, running, completed, failed
-- started_at - 开始执行时间
-- finished_at - 完成时间
-- error_message - 错误信息（失败时）
-- execution_time_ms - 执行耗时（毫秒）
-- created_at - 创建时间

CREATE INDEX IF NOT EXISTS idx_task_executions_job_id ON task_executions(job_id);
CREATE INDEX IF NOT EXISTS idx_task_executions_created_at ON task_executions(created_at);
```

**Step 2: 验证 SQL 语法**

Run: `sqlite3 data/ai_stats.db < sql/metrics_schema_sqlite.sql` (如果数据库已存在，验证表创建成功)
Expected: 无错误，表创建成功

**Step 3: 提交**

```bash
git add sql/metrics_schema_sqlite.sql
git commit -m "feat: 添加 task_executions 表支持任务执行记录"
```

---

### Task 2: 在 Database 基类添加 task_executions 相关抽象方法

**Files:**
- Modify: `core/database/base.py`

**Step 1: 在 Database 类末尾（最后一个方法后）添加任务执行相关抽象方法**

```python
    # ========== 任务执行记录方法 ==========

    @abstractmethod
    def create_task_execution(self, job_id: str) -> int:
        """创建任务执行记录，返回 execution_id"""
        pass

    @abstractmethod
    def update_task_execution_status(self, execution_id: int,
                                     status: str) -> None:
        """更新任务执行状态"""
        pass

    @abstractmethod
    def complete_task_execution(self, execution_id: int,
                               started_at: datetime,
                               finished_at: datetime,
                               execution_time_ms: int,
                               error_message: str = None) -> None:
        """标记任务执行完成"""
        pass

    @abstractmethod
    def get_running_task_execution(self, job_id: str) -> Optional[Dict]:
        """获取正在运行的任务执行记录（pending 或 running）"""
        pass

    @abstractmethod
    def get_task_execution(self, execution_id: int) -> Optional[Dict]:
        """获取任务执行详情"""
        pass

    @abstractmethod
    def get_task_executions(self, job_id: str, limit: int = 10,
                           status: str = None) -> List[Dict]:
        """获取任务执行历史"""
        pass

    @abstractmethod
    def cleanup_old_task_executions(self, keep_count: int = 100) -> int:
        """清理旧的任务执行记录，返回删除的记录数"""
        pass
```

**Step 2: 提交**

```bash
git add core/database/base.py
git commit -m "feat: 为 Database 基类添加任务执行记录抽象方法"
```

---

### Task 3: 在 SQLiteDatabase 实现 task_executions 方法

**Files:**
- Modify: `core/database/sqlite.py`

**Step 1: 在 SQLiteDatabase 类末尾（最后一个方法后）添加任务执行相关方法**

```python
    # ========== 任务执行记录方法 ==========

    def create_task_execution(self, job_id: str) -> int:
        """创建任务执行记录，返回 execution_id"""
        now = datetime.now()
        with self._get_connection() as conn:
            cursor = conn.execute(
                'INSERT INTO task_executions (job_id, status, created_at) VALUES (?, ?, ?)',
                (job_id, 'pending', now)
            )
            return cursor.lastrowid

    def update_task_execution_status(self, execution_id: int,
                                     status: str) -> None:
        """更新任务执行状态"""
        now = datetime.now()
        with self._get_connection() as conn:
            conn.execute(
                'UPDATE task_executions SET status = ?, started_at = ? WHERE id = ?',
                (status, now if status == 'running' else None, execution_id)
            )

    def complete_task_execution(self, execution_id: int,
                               started_at: datetime,
                               finished_at: datetime,
                               execution_time_ms: int,
                               error_message: str = None) -> None:
        """标记任务执行完成"""
        status = 'failed' if error_message else 'completed'
        with self._get_connection() as conn:
            conn.execute(
                '''UPDATE task_executions
                   SET status = ?, started_at = ?, finished_at = ?,
                       execution_time_ms = ?, error_message = ?
                   WHERE id = ?''',
                (status, started_at, finished_at, execution_time_ms, error_message, execution_id)
            )

    def get_running_task_execution(self, job_id: str) -> Optional[Dict]:
        """获取正在运行的任务执行记录（pending 或 running）"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                '''SELECT id, job_id, status, started_at, finished_at,
                          error_message, execution_time_ms, created_at
                   FROM task_executions
                   WHERE job_id = ? AND status IN ('pending', 'running')
                   ORDER BY created_at DESC LIMIT 1''',
                (job_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_task_execution(self, execution_id: int) -> Optional[Dict]:
        """获取任务执行详情"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                '''SELECT id, job_id, status, started_at, finished_at,
                          error_message, execution_time_ms, created_at
                   FROM task_executions
                   WHERE id = ?''',
                (execution_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_task_executions(self, job_id: str, limit: int = 10,
                           status: str = None) -> List[Dict]:
        """获取任务执行历史"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            if status:
                cursor = conn.execute(
                    '''SELECT id, job_id, status, started_at, finished_at,
                              error_message, execution_time_ms, created_at
                       FROM task_executions
                       WHERE job_id = ? AND status = ?
                       ORDER BY created_at DESC LIMIT ?''',
                    (job_id, status, min(limit, 100))
                )
            else:
                cursor = conn.execute(
                    '''SELECT id, job_id, status, started_at, finished_at,
                              error_message, execution_time_ms, created_at
                       FROM task_executions
                       WHERE job_id = ?
                       ORDER BY created_at DESC LIMIT ?''',
                    (job_id, min(limit, 100))
                )
            return [dict(row) for row in cursor.fetchall()]

    def cleanup_old_task_executions(self, keep_count: int = 100) -> int:
        """清理旧的任务执行记录，返回删除的记录数"""
        with self._get_connection() as conn:
            # 获取需要保留的最新记录的 ID
            cursor = conn.execute(
                '''SELECT id FROM task_executions
                   ORDER BY created_at DESC LIMIT 1 OFFSET ?''',
                (keep_count,)
            )
            row = cursor.fetchone()
            if not row:
                return 0

            # 获取需要保留的最小 ID
            min_keep_id = row[0]

            # 删除所有早于 min_keep_id 的记录
            cursor = conn.execute(
                '''DELETE FROM task_executions WHERE id < ?''',
                (min_keep_id,)
            )
            return cursor.rowcount
```

**Step 2: 提交**

```bash
git add core/database/sqlite.py
git commit -m "feat: 在 SQLiteDatabase 实现任务执行记录方法"
```

---

### Task 4: 扩展 BaseTask 支持 execution_id 传递

**Files:**
- Modify: `core/scheduler/base.py`

**Step 1: 修改 BaseTask 类，添加 execution_id 支持和钩子方法**

将 `run()` 方法修改为：

```python
    def run(self, execution_id: Optional[int] = None) -> Dict:
        self.current_execution_id = execution_id
        start_time = datetime.now()

        try:
            context = self.before_execute()
            result = self.execute(context)
            self.after_execute(result, context)

            # 更新执行记录
            if execution_id:
                finished_at = datetime.now()
                execution_time_ms = int((finished_at - start_time).total_seconds() * 1000)
                self.database.complete_task_execution(
                    execution_id,
                    start_time,
                    finished_at,
                    execution_time_ms
                )

            return result
        except Exception as e:
            self.logger.error(f"任务执行失败: {e}", exc_info=True)

            # 更新执行记录为失败状态
            if execution_id:
                finished_at = datetime.now()
                execution_time_ms = int((finished_at - start_time).total_seconds() * 1000)
                self.database.complete_task_execution(
                    execution_id,
                    start_time,
                    finished_at,
                    execution_time_ms,
                    str(e)
                )

            return {"success": False, "error": str(e)}
```

**Step 2: 提交**

```bash
git add core/scheduler/base.py
git commit -m "feat: 扩展 BaseTask 支持 execution_id 传递和状态更新"
```

---

### Task 5: 修改 AICodeScheduler 支持带 execution_id 触发

**Files:**
- Modify: `core/scheduler/scheduler.py`

**Step 1: 在 AICodeScheduler 类中添加 trigger_job_with_execution 方法**

在 `get_all_jobs()` 方法后添加：

```python
    def trigger_job_with_execution(self, job_id: str) -> Optional[int]:
        """手动触发任务并创建执行记录，返回 execution_id"""
        # 检查任务是否存在
        job = self.scheduler.get_job(job_id)
        if not job:
            return None

        # 检查是否有正在运行的任务
        running = self.database.get_running_task_execution(job_id)
        if running:
            self.logger.warning(f"任务 {job_id} 正在执行中，跳过触发")
            return None

        # 创建执行记录
        execution_id = self.database.create_task_execution(job_id)
        self.logger.info(f"创建任务执行记录: {job_id} -> execution_id={execution_id}")

        # 获取任务实例并设置 current_execution_id
        task_instance = self.task_instances.get(job_id)
        if task_instance:
            task_instance.current_execution_id = execution_id

        # 触发任务
        self.scheduler.trigger_job(job_id)
        self.logger.info(f"已触发任务: {job_id}")

        return execution_id
```

**Step 2: 修改调度器初始化，确保 database 可用**

在 `__init__` 方法中添加 database：

```python
from core.database.factory import create_database

class AICodeScheduler:
    def __init__(self, config: Dict):
        self.scheduler = BackgroundScheduler()
        self.config = config
        self.task_instances: Dict[str, BaseTask] = {}
        self.database = create_database(config.get("database", {}))
        self.is_running = False
        self.logger = Logger.get_logger("scheduler")
```

**Step 3: 提交**

```bash
git add core/scheduler/scheduler.py
git commit -m "feat: 添加 trigger_job_with_execution 方法支持手动触发任务"
```

---

### Task 6: 在 scheduler.py API 添加触发任务接口

**Files:**
- Modify: `api/routes/scheduler.py`

**Step 1: 添加 POST /api/v1/scheduler/jobs/<job_id>/trigger 接口**

在 `get_job()` 函数后添加：

```python
@scheduler_bp.route('/jobs/<job_id>/trigger', methods=['POST'])
def trigger_job(job_id: str):
    """手动触发任务"""
    try:
        scheduler = get_scheduler()

        # 检查任务是否在注册表中
        from core.scheduler.registry import TaskRegistry
        task_class = TaskRegistry.get(job_id)
        if not task_class:
            return jsonify({'success': False, 'error': '任务不存在'}), 404

        # 触发任务
        execution_id = scheduler.trigger_job_with_execution(job_id)

        if execution_id is None:
            # 检查是否是因为正在执行而失败
            running = scheduler.database.get_running_task_execution(job_id)
            if running:
                return jsonify({
                    'success': False,
                    'error': '任务正在执行中'
                }), 409
            return jsonify({'success': False, 'error': '任务触发失败'}), 500

        return jsonify({
            'success': True,
            'data': {
                'execution_id': execution_id,
                'status': 'pending',
                'job_id': job_id
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

**Step 2: 添加 GET /api/v1/scheduler/jobs/<job_id>/executions 接口**

在 `trigger_job()` 函数后添加：

```python
@scheduler_bp.route('/jobs/<job_id>/executions', methods=['GET'])
def get_job_executions(job_id: str):
    """获取任务执行历史"""
    try:
        scheduler = get_scheduler()

        # 获取查询参数
        limit = min(request.args.get('limit', 10, type=int), 100)
        status = request.args.get('status', None)

        executions = scheduler.database.get_task_executions(job_id, limit, status)

        return jsonify({
            'success': True,
            'data': {
                'executions': executions,
                'job_id': job_id,
                'count': len(executions)
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

**Step 3: 添加 GET /api/v1/scheduler/jobs/<job_id>/executions/<execution_id> 接口**

在 `get_job_executions()` 函数后添加：

```python
@scheduler_bp.route('/jobs/<job_id>/executions/<int:execution_id>', methods=['GET'])
def get_job_execution(job_id: str, execution_id: int):
    """获取任务执行详情"""
    try:
        scheduler = get_scheduler()

        execution = scheduler.database.get_task_execution(execution_id)

        if not execution:
            return jsonify({'success': False, 'error': '执行记录不存在'}), 404

        # 验证 job_id 是否匹配
        if execution['job_id'] != job_id:
            return jsonify({'success': False, 'error': '执行记录不匹配'}), 400

        return jsonify({
            'success': True,
            'data': execution
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

**Step 4: 在文件顶部添加 request 导入**

确保文件开头有：
```python
from flask import Blueprint, jsonify, request
```

**Step 5: 提交**

```bash
git add api/routes/scheduler.py
git commit -m "feat: 添加手动触发任务和执行历史查询 API"
```

---

### Task 7: 创建任务执行清理任务

**Files:**
- Create: `core/scheduler/cleanup_task.py`

**Step 1: 创建清理任务类**

```python
from core.scheduler.base import BaseTask
from core.scheduler.scheduled import scheduled
from core.scheduler.task_meta import TaskMeta


@scheduled(cron="0 3 * * *", job_id="task_cleanup", name="任务执行记录清理")
class TaskCleanupTask(BaseTask, metaclass=TaskMeta):
    def execute(self, context=None):
        """清理旧的任务执行记录"""
        self.logger.info('开始清理任务执行记录')

        # 保留最近 100 条记录
        deleted_count = self.database.cleanup_old_task_executions(keep_count=100)

        self.logger.info(f'清理完成，删除了 {deleted_count} 条记录')

        return {
            'success': True,
            'deleted_count': deleted_count
        }
```

**Step 2:提交**

```bash
git add core/scheduler/cleanup_task.py
git commit -m "feat: 添加任务执行记录清理定时任务"
```

---

### Task 8: 在 app.py 中导入清理任务

**Files:**
- Modify: `app.py`

**Step 1: 在导入任务时添加 CleanupTask**

找到以下导入部分：
```python
from core.scheduler.dimensions_task import DimensionsUpdateTask
from core.scheduler.stats_task import DailyStatsTask
```

修改为：
```python
from core.scheduler.dimensions_task import DimensionsUpdateTask
from core.scheduler.stats_task import DailyStatsTask
from core.scheduler.cleanup_task import TaskCleanupTask
```

**Step 2: 提交**

```bash
git add app.py
git commit -m "feat: 导入任务清理任务使其自动注册"
```

---

### Task 9: 编写 API 测试

**Files:**
- Create: `tests/test_scheduler_api.py`

**Step 1: 编写测试文件**

```python
import pytest
import json
import time
from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestSchedulerAPI:
    """调度器 API 测试"""

    def test_get_jobs(self, client):
        """测试获取所有任务"""
        response = client.get('/api/v1/scheduler/jobs')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'jobs' in data['data']

    def test_trigger_nonexistent_job(self, client):
        """测试触发不存在的任务"""
        response = client.post('/api/v1/scheduler/jobs/nonexistent/trigger')
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] is False

    def test_trigger_job_success(self, client):
        """测试成功触发任务"""
        # 先获取任务列表
        jobs_response = client.get('/api/v1/scheduler/jobs')
        jobs_data = json.loads(jobs_response.data)
        jobs = jobs_data['data']['jobs']

        if not jobs:
            pytest.skip("没有可用的任务")

        job_id = jobs[0]['id']

        # 触发任务
        response = client.post(f'/api/v1/scheduler/jobs/{job_id}/trigger')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'execution_id' in data['data']
        assert data['data']['status'] == 'pending'

    def test_trigger_job_concurrent(self, client):
        """测试并发控制"""
        # 先获取任务列表
        jobs_response = client.get('/api/v1/scheduler/jobs')
        jobs_data = json.loads(jobs_response.data)
        jobs = jobs_data['data']['jobs']

        if not jobs:
            pytest.skip("没有可用的任务")

        job_id = jobs[0]['id']

        # 第一次触发
        response1 = client.post(f'/api/v1/scheduler/jobs/{job_id}/trigger')
        assert response1.status_code == 200

        # 第二次触发（应该返回 409）
        response2 = client.post(f'/api/v1/scheduler/jobs/{job_id}/trigger')
        assert response2.status_code == 409

    def test_get_executions(self, client):
        """测试获取执行历史"""
        # 先获取任务列表
        jobs_response = client.get('/api/v1/scheduler/jobs')
        jobs_data = json.loads(jobs_response.data)
        jobs = jobs_data['data']['jobs']

        if not jobs:
            pytest.skip("没有可用的任务")

        job_id = jobs[0]['id']

        # 获取执行历史
        response = client.get(f'/api/v1/scheduler/jobs/{job_id}/executions')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'executions' in data['data']

    def test_get_execution_detail(self, client):
        """测试获取执行详情"""
        # 先获取任务列表
        jobs_response = client.get('/api/v1/scheduler/jobs')
        jobs_data = json.loads(jobs_response.data)
        jobs = jobs_data['data']['jobs']

        if not jobs:
            pytest.skip("没有可用的任务")

        job_id = jobs[0]['id']

        # 触发任务
        trigger_response = client.post(f'/api/v1/scheduler/jobs/{job_id}/trigger')
        trigger_data = json.loads(trigger_response.data)
        execution_id = trigger_data['data']['execution_id']

        # 获取执行详情
        response = client.get(f'/api/v1/scheduler/jobs/{job_id}/executions/{execution_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['id'] == execution_id

    def test_get_execution_not_found(self, client):
        """测试获取不存在的执行详情"""
        jobs_response = client.get('/api/v1/scheduler/jobs')
        jobs_data = json.loads(jobs_response.data)
        jobs = jobs_data['data']['jobs']

        if not jobs:
            pytest.skip("没有可用的任务")

        job_id = jobs[0]['id']

        response = client.get(f'/api/v1/scheduler/jobs/{job_id}/executions/99999')
        assert response.status_code == 404
```

**Step 2: 提交**

```bash
git add tests/test_scheduler_api.py
git commit -m "test: 添加调度器 API 测试"
```

---

### Task 10: 手动测试 API

**Files:**
- None (使用 curl 或 Postman 测试)

**Step 1: 启动应用**

```bash
python app.py
```

**Step 2: 测试获取任务列表**

Run:
```bash
curl http://localhost:8888/api/v1/scheduler/jobs
```
Expected: 返回任务列表 JSON

**Step 3: 触发一个任务**

Run (替换 `<job_id>` 为实际的任务 ID):
```bash
curl -X POST http://localhost:8888/api/v1/scheduler/jobs/<job_id>/trigger
```
Expected: 返回 `{"success": true, "data": {"execution_id": "123", "status": "pending"}}`

**Step 4: 测试并发控制**

Run (再次触发同一任务):
```bash
curl -X POST http://localhost:8888/api/v1/scheduler/jobs/<job_id>/trigger
```
Expected: 返回 409 状态码

**Step 5: 查询执行历史**

Run:
```bash
curl http://localhost:8888/api/v1/scheduler/jobs/<job_id>/executions
```
Expected: 返回执行记录列表

**Step 6: 查询执行详情**

Run (替换 `<execution_id>` 为实际的 ID):
```bash
curl http://localhost:8888/api/v1/scheduler/jobs/<job_id>/executions/<execution_id>
```
Expected: 返回执行详情

**完成测试后不需要提交代码**

---

## 实现完成检查清单

- [x] 数据库 schema 更新
- [x] Database 基类添加抽象方法
- [x] SQLiteDatabase 实现方法
- [x] BaseTask 扩展支持 execution_id
- [x] AICodeScheduler 添加触发方法
- [x] API 接口添加（trigger, executions, execution detail）
- [x] 清理任务创建
- [x] 清理任务导入
- [x] 测试文件创建
- [x] 手动测试通过
