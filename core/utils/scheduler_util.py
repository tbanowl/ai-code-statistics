from apscheduler.triggers.cron import CronTrigger
from regex import F

# corn 表达式数组索引映射
CORN_INDEX_MAP = {
    'second': 0,
    'minute': 1,
    'hour': 2,
    'day': 3,
    'week': 3,
    'month': 4,
    'day_of_week': 5,
    'year': 6,
}

def convert_corn(trigger: CronTrigger) -> str:
    """
    转换 corn 表达式字符
    """
    corn_list = ["*", "*", "*", "*", "*", "?", "*"]
    for field in trigger.fields:
        index = CORN_INDEX_MAP[field.name]
        if index and index >= 0 and index < 7:
            corn_list[CORN_INDEX_MAP[field.name]] = f'{field}'     
    
    return " ".join(corn_list)

