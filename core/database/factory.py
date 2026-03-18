from typing import Dict
from .base import Database
from .sqlite import SQLiteDatabase


def create_database(config: Dict) -> Database:
    """创建数据库实例"""
    db_config = config.get('database', config)
    db_type = db_config.get('type', 'sqlite')

    # 根据类型获取对应的配置子节点
    database_config = db_config.get(db_type, db_config)
    database_config['type'] = db_type

    if db_type == 'sqlite':
        return SQLiteDatabase(database_config)
    elif db_type == 'postgresql':
        # 待实现
        raise NotImplementedError("PostgreSQL database not yet implemented")
    elif db_type == 'mysql':
        # 待实现
        raise NotImplementedError("MySQL database not yet implemented")
    else:
        raise ValueError(f"Unsupported database: {db_type}")


__all__ = ['create_database', 'Database', 'SQLiteDatabase']
