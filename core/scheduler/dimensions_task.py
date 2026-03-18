import json
from typing import Dict, Optional
from datetime import datetime
from core.models.metrics import MetricsRepo, MetricsContributor, MetricsRepoContributor
from core.scheduler.base import BaseTask
from core.scheduler.scheduled import scheduled
from core.scheduler.task_meta import TaskMeta


@scheduled(
    cron="0 3 * * *", job_id="dimensions_update", name="维度表统计更新", enabled=True
)
class DimensionsUpdateTask(BaseTask, metaclass=TaskMeta):
    def execute(self, context: Optional[Dict] = None) -> Dict:
        try:
            self.logger.info("开始执行维度统计更新任务")
            start_time = datetime.now()

            # 获取所有待处理的 Committed 事件
            committed_events = self._get_committed_events()

            if not committed_events:
                self.logger.info("没有需要处理的 Committed 事件")
                return {
                    "success": True,
                    "message": "没有需要处理的数据",
                    "processed": 0,
                }

            # 按仓库和作者聚合数据
            repo_stats = self._aggregate_by_repo(committed_events)
            author_stats = self._aggregate_by_author(committed_events)
            repo_author_relations = self._extract_repo_author_relations(
                committed_events
            )

            # 保存仓库统计
            saved_repos = 0
            for repo_data in repo_stats.values():
                repo = MetricsRepo(**repo_data)
                self._upsert_repo(repo)
                saved_repos += 1

            # 保存作者统计
            saved_contributors = 0
            for author_data in author_stats.values():
                contributor = MetricsContributor(**author_data)
                self._upsert_contributor(contributor)
                saved_contributors += 1

            # 保存关联关系
            saved_relations = 0
            for relation_key, relation_data in repo_author_relations.items():
                relation = MetricsRepoContributor(**relation_data)
                self._upsert_repo_contributor(relation)
                saved_relations += 1

            duration = (datetime.now() - start_time).total_seconds()

            self.logger.info(
                f"维度统计更新完成: 仓库={saved_repos}, "
                f"作者={saved_contributors}, 关联={saved_relations}, "
                f"耗时={duration:.2f}s"
            )

            return {
                "success": True,
                "message": "维度统计更新成功",
                "processed": {
                    "repos": saved_repos,
                    "contributors": saved_contributors,
                    "relations": saved_relations,
                },
                "duration": duration,
            }

        except Exception as e:
            self.logger.error(f"维度统计更新失败: {e}")
            return {"success": False, "error": str(e)}

    def _get_committed_events(self) -> list:
        """获取所有 Committed 事件"""
        # 从 metrics_events_committed 表读取数据
        # 这里简化处理，实际应该从数据库查询
        with self.database._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM metrics_events_committed")
            columns = [desc[0] for desc in cursor.description]
            events = []
            for row in cursor.fetchall():
                events.append(dict(zip(columns, row)))
            return events

    def _aggregate_by_repo(self, events: list) -> Dict:
        """按仓库聚合数据"""
        repo_stats = {}

        for event in events:
            repo_url = event.get("repo_url", "")
            repo_name = self._extract_repo_name(repo_url)
            repo_id = self._extract_repo_id(repo_url)

            if not repo_id:
                continue

            if repo_id not in repo_stats:
                repo_stats[repo_id] = {
                    "repo_id": repo_id,
                    "repo_name": repo_name or repo_id,
                    "repo_url": repo_url,
                    "provider_type": "github",  # 可从 url 解析
                    "branch": event.get("branch", "main"),
                    "total_lines": 0,
                    "ai_lines": 0,
                    "human_lines": 0,
                    "ai_percentage": 0.0,
                    "total_commits": 0,
                    "ai_commits": 0,
                    "tool_model_breakdown": {},
                    "first_commit_ts": None,
                    "last_commit_ts": None,
                    "created_at": int(datetime.now().timestamp()),
                    "updated_at": int(datetime.now().timestamp()),
                }

            stat = repo_stats[repo_id]
            timestamp = event.get("timestamp", 0)

            # 更新首次和最近提交时间
            if stat["first_commit_ts"] is None or timestamp < stat["first_commit_ts"]:
                stat["first_commit_ts"] = timestamp
            if stat["last_commit_ts"] is None or timestamp > stat["last_commit_ts"]:
                stat["last_commit_ts"] = timestamp

            # 统计提交数
            stat["total_commits"] += 1

            # 解析 AI 相关数据
            ai_additions = self._parse_json_field(event.get("ai_additions"))
            if ai_additions:
                # 判断是否包含 AI 生成的代码
                if any(v > 0 for v in ai_additions.values()):
                    stat["ai_commits"] += 1

            human_additions = event.get("human_additions", 0) or 0
            total_ai = sum(ai_additions.values()) if ai_additions else 0

            stat["human_lines"] += human_additions
            stat["ai_lines"] += total_ai
            stat["total_lines"] += human_additions + total_ai

            # 工具模型分布
            self._update_tool_model_breakdown(
                stat["tool_model_breakdown"],
                event.get("tool"),
                event.get("model"),
                total_ai,
            )

        # 计算占比
        for stat in repo_stats.values():
            if stat["total_lines"] > 0:
                stat["ai_percentage"] = round(
                    stat["ai_lines"] / stat["total_lines"] * 100, 2
                )
            stat["tool_model_breakdown"] = json.dumps(stat["tool_model_breakdown"])
            stat["updated_at"] = int(datetime.now().timestamp())

        return repo_stats

    def _aggregate_by_author(self, events: list) -> Dict:
        """按作者聚合数据"""
        author_stats = {}

        for event in events:
            author = event.get("author")
            author_email = event.get("author_email")  # 可能有这个字段
            if not author:
                continue

            if author not in author_stats:
                author_stats[author] = {
                    "author": author,
                    "author_email": None,
                    "total_lines": 0,
                    "ai_lines": 0,
                    "human_lines": 0,
                    "ai_percentage": 0.0,
                    "total_commits": 0,
                    "ai_commits": 0,
                    "tool_model_breakdown": {},
                    "first_commit_ts": None,
                    "last_commit_ts": None,
                    "repos_count": 0,
                    "created_at": int(datetime.now().timestamp()),
                    "updated_at": int(datetime.now().timestamp()),
                }

            stat = author_stats[author]
            timestamp = event.get("timestamp", 0)

            # 更新时间
            if stat["first_commit_ts"] is None or timestamp < stat["first_commit_ts"]:
                stat["first_commit_ts"] = timestamp
            if stat["last_commit_ts"] is None or timestamp > stat["last_commit_ts"]:
                stat["last_commit_ts"] = timestamp

            # 统计提交
            stat["total_commits"] += 1

            # AI 判断
            ai_additions = self._parse_json_field(event.get("ai_additions"))
            if ai_additions and any(v > 0 for v in ai_additions.values()):
                stat["ai_commits"] += 1

            human_additions = event.get("human_additions", 0) or 0
            total_ai = sum(ai_additions.values()) if ai_additions else 0

            stat["human_lines"] += human_additions
            stat["ai_lines"] += total_ai
            stat["total_lines"] += human_additions + total_ai

            # 工具模型分布
            self._update_tool_model_breakdown(
                stat["tool_model_breakdown"],
                event.get("tool"),
                event.get("model"),
                total_ai,
            )

        # 计算聚合值
        for stat in author_stats.values():
            if stat["total_lines"] > 0:
                stat["ai_percentage"] = round(
                    stat["ai_lines"] / stat["total_lines"] * 100, 2
                )
            stat["tool_model_breakdown"] = json.dumps(stat["tool_model_breakdown"])
            stat["repos_count"] = self._count_repos_for_author(events, stat["author"])
            stat["updated_at"] = int(datetime.now().timestamp())

        return author_stats

    def _extract_repo_author_relations(self, events: list) -> Dict:
        """提取仓库作者关联关系"""
        relations = {}

        for event in events:
            repo_url = event.get("repo_url", "")
            author = event.get("author")

            if not repo_url or not author:
                continue

            repo_id = self._extract_repo_id(repo_url)
            if not repo_id:
                continue

            key = f"{repo_id}:{author}"

            timestamp = event.get("timestamp", 0)

            if key not in relations:
                relations[key] = {
                    "repo_id": repo_id,
                    "author": author,
                    "first_seen_ts": timestamp,
                    "last_seen_ts": timestamp,
                    "created_at": int(datetime.now().timestamp()),
                    "updated_at": int(datetime.now().timestamp()),
                }
            else:
                # 更新时间范围
                if timestamp < relations[key]["first_seen_ts"]:
                    relations[key]["first_seen_ts"] = timestamp
                if timestamp > relations[key]["last_seen_ts"]:
                    relations[key]["last_seen_ts"] = timestamp

        for rel in relations.values():
            rel["updated_at"] = int(datetime.now().timestamp())

        return relations

    def _upsert_repo(self, repo: MetricsRepo) -> None:
        """更新或插入仓库记录"""
        existing = self.database.get_metrics_repo(repo.repo_id)
        if existing:
            # 更新 - 这里简化，实际应该通过 SQL UPDATE
            self.database.save_metrics_repo(repo)
        else:
            # 插入
            self.database.save_metrics_repo(repo)

    def _upsert_contributor(self, contributor: MetricsContributor) -> None:
        """更新或插入作者记录"""
        existing = self.database.get_metrics_contributor(contributor.author)
        if existing:
            # 更新
            self.database.save_metrics_contributor(contributor)
        else:
            # 插入
            self.database.save_metrics_contributor(contributor)

    def _upsert_repo_contributor(self, rel: MetricsRepoContributor) -> None:
        """更新或插入关联记录"""
        # 简化处理，直接保存
        self.database.save_metrics_repo_contributor(rel)

    def _extract_repo_name(self, repo_url: str) -> Optional[str]:
        """从 URL 提取仓库名"""
        if not repo_url:
            return None
        parts = repo_url.rstrip("/").split("/")
        return parts[-1] if parts else None

    def _extract_repo_id(self, repo_url: str) -> Optional[str]:
        """从 URL 提取仓库 ID"""
        if not repo_url:
            return None

        # 简化处理，假设 URL 格式为 https://github.com/owner/repo
        # 实际应该更健壮地解析
        parts = repo_url.replace("https://", "").replace("http://", "").split("/")
        if len(parts) >= 3:  # domain/owner/repo
            return f"{parts[-2]}/{parts[-1]}"
        return None

    def _parse_json_field(self, value: Optional[str]) -> Optional[Dict]:
        """解析 JSON 字段"""
        if not value:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None

    def _update_tool_model_breakdown(
        self, breakdown: Dict, tool: Optional[str], model: Optional[str], count: int
    ) -> None:
        """更新工具模型分布"""
        if not count:
            return

        if tool and model:
            key = f"{tool}/{model}"
            breakdown[key] = breakdown.get(key, 0) + count
        elif model:
            breakdown[model] = breakdown.get(model, 0) + count
        elif tool:
            breakdown[tool] = breakdown.get(tool, 0) + count

    def _count_repos_for_author(self, events: list, author: str) -> int:
        """统计作者参与的仓库数"""
        repos = set()
        for event in events:
            if event.get("author") == author:
                repo_id = self._extract_repo_id(event.get("repo_url", ""))
                if repo_id:
                    repos.add(repo_id)
        return len(repos)
