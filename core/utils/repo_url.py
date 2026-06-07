"""仓库地址归一化与还原工具函数。"""

from __future__ import annotations

UNKNOWN_REPO = "未知仓库"


def normalize_repo_url(raw: str | None) -> str:
    """将任意 Git URL 归一化为 host/path 格式。

    规则（按顺序）：
    1. None / 空白 → "未知仓库"
    2. 去除协议前缀：https://, http://, ssh://, git://, file://
    3. 去除 git@ 前缀，将第一个 : 替换为 /（处理 git@host:path 格式）
    4. 去除末尾 .git（仅当以 .git 结尾时）
    5. 去除首尾斜杠
    """
    value = (raw or "").strip()
    if not value:
        return UNKNOWN_REPO
    if value == UNKNOWN_REPO:
        return UNKNOWN_REPO

    # 去除协议前缀
    had_protocol = False
    for prefix in ("https://", "http://", "ssh://", "git://", "file://"):
        if value.lower().startswith(prefix):
            value = value[len(prefix):]
            had_protocol = True
            break

    # 去除 git@ 前缀
    # 无协议时（git@host:path.git），将第一个 : 替换为 /
    # 有协议时（ssh://git@host:port/path），冒号是端口号，不替换
    if value.lower().startswith("git@"):
        value = value[4:]
        if not had_protocol:
            colon_pos = value.find(":")
            if colon_pos != -1:
                value = value[:colon_pos] + "/" + value[colon_pos + 1:]

    # 去除首尾斜杠（在去 .git 之前先清理可能的尾部斜杠）
    value = value.strip("/")

    # 去除末尾 .git
    if value.lower().endswith(".git"):
        value = value[:-4]

    # 再次去除首尾斜杠（处理 repo.git/ → strip → repo.git → remove .git → repo 情况不需要，
    # 但处理 host/org/repo.git/ 这种 trailing slash + .git 场景）
    value = value.strip("/")

    return value.lower() or UNKNOWN_REPO


def restore_repo_url(normalized: str, protocol: str = "ssh") -> str:
    """将归一化地址还原为完整 Git URL。"""
    if not normalized or normalized == UNKNOWN_REPO:
        return normalized or ""

    if protocol == "https":
        return f"https://{normalized}.git"
    elif protocol == "http":
        return f"http://{normalized}.git"
    elif protocol == "git":
        return f"git://{normalized}.git"
    else:
        return f"ssh://git@{normalized}.git"
