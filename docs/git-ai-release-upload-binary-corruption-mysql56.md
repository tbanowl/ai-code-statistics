# Git-AI Release 上传文件乱码排查（MySQL 5.6 + PyMySQL）

## 现象

通过 `POST /worker/releases/admin/upload` 上传 Git-AI 发布文件（`install.ps1`、`git-ai-windows-x64.exe` 等）后：

- 在 **MySQL 5.6** 上，上传接口返回成功，但下载下来的文件内容损坏 / 乱码。
- 下载文件的 sha256 与上传时服务端计算的不一致。
- 表结构与连接字符集都已确认为 `utf8mb4`，`content_blob` 列为 `LONGBLOB`。

## 受影响链路

| 环节 | 位置 | 说明 |
|------|------|------|
| 接口入口 | `api/routes/git_ai_worker.py:300` `upload_admin_release` | 接收 multipart 文件 |
| 读取文件 | `core/services/release_service.py:111` `_read_upload_file` | `file.read()` 得到 **bytes**，sha256 在 `:114` 基于原始 bytes 计算 |
| 入库 | `core/database/release_db.py:40` | `session.add(GitAiReleaseArtifact(...))`，`content_blob` 为 bytes |
| 列定义 | `core/database/models.py:540` | `LargeBinary(length=(2**32)-1)` → MySQL `LONGBLOB` |
| 引擎 | `core/database/base.py:26` | `mysql+pymysql://...?charset=utf8mb4` |

## 根因

**PyMySQL 1.4.6 默认用 `escape_bytes`（不带 `_binary` 前缀）转义 `bytes`**，因此文件内容被当作**普通 utf8mb4 字符串字面量** `'...'` 发送给 MySQL，而不是二进制字面量 `_binary'...'`。

PyMySQL `converters.py` 关键定义：

```python
def escape_bytes_prefixed(value, mapping=None):       # 带 _binary，二进制安全
    return "_binary'%s'" % value.decode("ascii", "surrogateescape").translate(_escape_table)

def escape_bytes(value, mapping=None):                # 不带 _binary（默认注册的就是它）
    return "'%s'" % value.decode("ascii", "surrogateescape").translate(_escape_table)

encoders = {
    ...
    bytes: escape_bytes,                              # ← 默认走这个，无 _binary
    ...
}
```

实测（样本 `b'MZ\x90\x00\xff\xfe\xc0'`）：

```
escape_bytes          → 'MZ\x90\0\xff\xfe\xc0'        (普通字面量，MySQL 按 utf8mb4 校验)
escape_bytes_prefixed → _binary'MZ\x90\0\xff\xfe\xc0'  (二进制字面量，MySQL 原样存)
```

MySQL 在 utf8mb4 连接上解析那个**无前缀**字面量时，会把字节按 utf8mb4 文本校验。exe / ps1 里到处都是的 `\x90 \xff \xfe \xc0` 等字节都不是合法 UTF-8 → 被丢弃 / 替换 → 存入 `LONGBLOB` 的 bytes 已被破坏。

> 与表字符集无关：`LONGBLOB` 本身没问题，问题出在字面量缺少 `_binary` introducer，字节在传输解析阶段就被改坏了。

## 为什么偏偏是 5.6

| MySQL 版本 | 默认 `sql_mode` | 遇到非法 UTF-8 字节的表现 |
|------------|-----------------|---------------------------|
| **5.6** | `''`（空，非严格） | **静默丢弃 / 替换为 `?`**，仅产生 warning，INSERT 仍"成功" → 表现为乱码 |
| 5.7 / 8.0 | 默认带 `STRICT_TRANS_TABLES` | 直接报 `1366 Incorrect string value`，INSERT 失败 |

所以同一份代码：5.6 上是"上传成功但文件坏"；5.7+ / 8.0 上则会报错。

## 修复方案

### 方案 A（推荐）：强制 PyMySQL 使用带 `_binary` 的转义器

在 `core/database/base.py` 建引擎处注册 connect 事件，覆盖 `encoders[bytes]`：

```python
from sqlalchemy import create_engine, event
from pymysql.converters import escape_bytes_prefixed


def _register_binary_encoder(engine):
    """让 bytes 以 _binary 字面量发送，避免 utf8mb4 连接下二进制被字符集校验破坏。"""
    @event.listens_for(engine, "connect")
    def _force_binary_bytes(dbapi_conn, _):
        dbapi_conn.encoders[bytes] = escape_bytes_prefixed


global_engine = create_engine(database_config.get("url"), echo=echo, ...)

_register_binary_encoder(global_engine)
```

> ⚠️ 项目里还有另外两个引擎需要同步挂上，否则 CAS / Notes 等写二进制的路径会踩同样的坑：
> - `core/database/base.py:100` `BaseDatabase.get_shared_engine` 内新建的引擎
> - `core/database/authorship_notes_db.py:98` `AuthorshipNotesDatabase` 自建的引擎
>
> `release` 上传走的是 `global_engine`，方案 A 对它直接生效。

### 方案 B：换驱动为 mysqlclient

`mysql+mysqldb://`（C 库，走二进制协议绑定参数，不存在 `_binary` 缺失问题）。

```bash
pip install mysqlclient
```

将 `DB_URL` 的 `mysql+pymysql://` 改为 `mysql+mysqldb://`（保留 `?charset=utf8mb4`）。

### 不推荐

把 5.6 的 `sql_mode` 设严只会让"静默乱码"变成"报错"，不是修复。

## 验证

1. 打补丁后重新上传一个 `.exe`。
2. 下载该文件，比对 sha256 与 `git_ai_release_artifacts.sha256` 列一致。
3. 或直接查库：`SELECT sha256, sha256(content_blob) FROM git_ai_release_artifacts WHERE filename='git-ai-windows-x64.exe';`（补丁前两者不等，补丁后相等）。

## 存量数据

5.6 上已经写坏的 `content_blob` 无法还原，需要在打补丁后**重新上传**对应 release。

## 参考

- PyMySQL `converters.py`：`escape_bytes` / `escape_bytes_prefixed` / `encoders` 注册
- 触发条件：`charset=utf8mb4` 连接 + `bytes` 入 `BLOB/LONGBLOB` + MySQL 非严格 `sql_mode`
