"""Git-AI 相关 API（用户界面端点）"""
from flask import Blueprint

git_ai_bp = Blueprint('git_ai', __name__, url_prefix='/api/git-ai')

# 预留的 Git-AI 用户界面 API
# 例如：数据查询、展示页面等