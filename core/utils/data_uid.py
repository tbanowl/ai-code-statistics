import hashlib
from core.database.models import MetricsEventsAgentUsage, MetricsEventsCheckpoint, MetricsEventsCommitted, MetricsEventsInstallHooks


def gen_commited_uid(data: MetricsEventsCommitted) -> str:
    data_str = ""
    data_str = check_append(data.commit_sha, data_str)
    data_str = check_append(data.base_commit_sha, data_str)
    return data_str

def gen_checkpoint_uid(data: MetricsEventsCheckpoint):
    """
    生成 checkpoint 数据的唯一ID
    """
    data_str = ""
    data_str = check_append(data.timestamp, data_str)
    data_str = check_append(data.checkpoint_ts, data_str)
    data_str = check_append(data.kind, data_str)
    data_str = check_append(data.file_path, data_str)
    data_str = check_append(data.lines_added, data_str)
    data_str = check_append(data.lines_deleted, data_str)
    data_str = check_append(data.lines_added_sloc, data_str)
    data_str = check_append(data.lines_deleted_sloc, data_str)
    data_str = check_append(data.repo_url, data_str)
    data_str = check_append(data.author, data_str)
    data_str = check_append(data.commit_sha, data_str)
    data_str = check_append(data.base_commit_sha, data_str)
    data_str = check_append(data.branch, data_str)
    data_str = check_append(data.tool, data_str)
    data_str = check_append(data.model, data_str)
    data_str = check_append(data.prompt_id, data_str)
    return hash_data(data_str)

def gen_install_hooks_uid(data: MetricsEventsInstallHooks) -> str:
    """
    生成 install hooks 事件的唯一id
    """
    data_str = ""
    data_str = check_append(data.timestamp, data_str)
    data_str = check_append(data.tool_id, data_str)
    data_str = check_append(data.status, data_str)
    data_str = check_append(data.message, data_str)
    return hash_data(data_str)

def gen_agent_usage_uid(data: MetricsEventsAgentUsage) -> str:
    data_str = ""
    
    data_str = check_append(data.timestamp, data_str)
    data_str = check_append(data.repo_url, data_str)
    data_str = check_append(data.author, data_str)
    data_str = check_append(data.commit_sha, data_str)
    data_str = check_append(data.base_commit_sha, data_str)
    data_str = check_append(data.branch, data_str)
    data_str = check_append(data.tool, data_str)
    data_str = check_append(data.model, data_str)
    data_str = check_append(data.prompt_id, data_str)
    return hash_data(data_str)

def check_append(value, data_str: str) -> str:
    """
    检查并拼接字符 - 将值转换为字符串并拼接
    """
    if value is None:
        return data_str
    str_value = str(value).strip()
    if not str_value:
        return data_str
    if not data_str:
        return str_value
    return data_str + ',' + str_value

def hash_data(data: str, algorithm: str = 'sha1') -> str:
    hash_func = getattr(hashlib, algorithm)()
    hash_func.update(data.encode('utf-8'))
    return hash_func.hexdigest()