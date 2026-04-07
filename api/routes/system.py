import jwt
import datetime
from types import SimpleNamespace
from flask import Blueprint, jsonify, request
from functools import wraps
from core.database.system_db import SystemDatabase

system_bp = Blueprint("system", __name__, url_prefix="/api")
_db = SystemDatabase()

SECRET_KEY = "git-ai-secret-2024"


def _expires_at_ms(now: datetime.datetime, hours: int = 2) -> int:
    return int((now + datetime.timedelta(hours=hours)).timestamp() * 1000)


def _menu_to_frontend(menu):
    return {
        "id": menu.id,
        "parentId": menu.parent_id,
        "title": menu.title,
        "path": menu.path,
        "component": menu.component,
        "icon": menu.icon,
        "rank": menu.rank,
        "menuType": menu.menu_type,
        "status": menu.status,
        "showLink": bool(menu.show_link),
        "keepAlive": bool(menu.keep_alive),
        "createTime": menu.created_at,
    }


def _dept_to_frontend(dept):
    return {
        "id": dept.id,
        "parentId": dept.parent_id,
        "name": dept.name,
        "sort": dept.sort,
        "status": dept.status,
        "createTime": dept.created_at,
        "remark": "",
        "principal": "",
        "phone": "",
        "email": "",
    }


def _user_to_frontend(user, dept_name: str = ""):
    return {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname or user.username,
        "avatar": user.avatar or "",
        "phone": user.phone or "",
        "email": user.email or "",
        "status": user.status,
        "sex": 0,
        "password": "",
        "remark": "",
        "createTime": user.created_at,
        "deptId": user.dept_id,
        "dept": {"id": user.dept_id, "name": dept_name or ""},
    }


def _token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            return jsonify({"code": 401, "message": "未授权"}), 401
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.environ["current_user"] = payload
        except jwt.ExpiredSignatureError:
            return jsonify({"code": 401, "message": "token已过期"}), 401
        except Exception:
            return jsonify({"code": 401, "message": "token无效"}), 401
        return f(*args, **kwargs)

    return decorated


@system_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(force=True, silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    user = _db.get_user_by_username(username)
    if not user or not _db.verify_password(user, password):
        return jsonify({"code": 400, "message": "用户名或密码错误"})
    roles = _db.get_user_roles(user.id)
    now = datetime.datetime.utcnow()
    access_token = jwt.encode(
        {
            "userId": user.id,
            "username": user.username,
            "roles": roles,
            "exp": now + datetime.timedelta(hours=2),
        },
        SECRET_KEY,
        algorithm="HS256",
    )
    refresh_token = jwt.encode(
        {"userId": user.id, "exp": now + datetime.timedelta(days=30)},
        SECRET_KEY,
        algorithm="HS256",
    )
    expires = _expires_at_ms(now)
    return jsonify(
        {
            "code": 0,
            "message": "操作成功",
            "data": {
                "avatar": user.avatar or "",
                "username": user.username,
                "nickname": user.nickname or user.username,
                "roles": roles,
                "permissions": [],
                "accessToken": access_token,
                "refreshToken": refresh_token,
                "expires": expires,
            },
        }
    )


@system_bp.route("/refresh-token", methods=["POST"])
def refresh_token():
    data = request.get_json(force=True, silent=True) or {}
    token = data.get("refreshToken", "")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except Exception:
        return jsonify({"code": 401, "message": "refreshToken无效"})
    now = datetime.datetime.utcnow()
    user_id = payload["userId"]
    roles = _db.get_user_roles(user_id)
    access_token = jwt.encode(
        {"userId": user_id, "roles": roles, "exp": now + datetime.timedelta(hours=2)},
        SECRET_KEY,
        algorithm="HS256",
    )
    new_refresh = jwt.encode(
        {"userId": payload["userId"], "exp": now + datetime.timedelta(days=30)},
        SECRET_KEY,
        algorithm="HS256",
    )
    expires = _expires_at_ms(now)
    return jsonify(
        {
            "code": 0,
            "message": "操作成功",
            "data": {
                "accessToken": access_token,
                "refreshToken": new_refresh,
                "expires": expires,
            },
        }
    )


@system_bp.route("/get-async-routes", methods=["GET"])
@_token_required
def get_async_routes():
    current_user = request.environ.get("current_user", {})
    roles = current_user.get("roles", []) if isinstance(current_user, dict) else []
    menus = _db.get_menus_by_role_codes(roles)
    menu_map = {}
    for m in menus:
        d = {
            "path": m.path or "",
            "name": m.path.replace("/", "_").strip("_") if m.path else str(m.id),
            "meta": {
                "title": m.title,
                "icon": m.icon or "",
                "rank": m.rank,
                "showLink": bool(m.show_link),
                "keepAlive": bool(m.keep_alive),
            },
        }
        if m.component:
            d["component"] = m.component
        menu_map[m.id] = {"data": d, "parent_id": m.parent_id, "children": []}

    roots = []
    for mid, item in menu_map.items():
        pid = item["parent_id"]
        if pid == 0 or pid not in menu_map:
            roots.append(item)
        else:
            menu_map[pid]["children"].append(item)

    def build(item):
        node = item["data"]
        if item["children"]:
            node["children"] = [
                build(c)
                for c in sorted(
                    item["children"], key=lambda x: x["data"]["meta"]["rank"]
                )
            ]
        return node

    return jsonify(
        {
            "code": 0,
            "message": "操作成功",
            "data": [
                build(r) for r in sorted(roots, key=lambda x: x["data"]["meta"]["rank"])
            ],
        }
    )


@system_bp.route("/user", methods=["POST"])
@_token_required
def user_list():
    data = request.get_json(force=True, silent=True) or {}
    username = data.get("username")
    phone = data.get("phone")
    status = data.get("status")
    dept_id = data.get("deptId")
    result = _db.get_user_list(
        page=data.get("currentPage", 1),
        page_size=data.get("pageSize", 10),
        username=username if isinstance(username, str) else None,
        phone=phone if isinstance(phone, str) else None,
        status=status if isinstance(status, (int, str)) else None,
        dept_id=dept_id if isinstance(dept_id, (int, str)) else None,
    )
    depts = {d.id: d.name for d in _db.get_dept_list()}
    result["list"] = [
        _user_to_frontend(SimpleNamespace(**row), depts.get(row.get("dept_id"), ""))
        for row in result["list"]
    ]
    return jsonify({"code": 0, "message": "操作成功", "data": result})


@system_bp.route("/user/add", methods=["POST"])
@_token_required
def user_add():
    _db.create_user(request.get_json(force=True, silent=True) or {})
    return jsonify({"code": 0, "message": "操作成功"})


@system_bp.route("/user/<int:user_id>", methods=["PUT"])
@_token_required
def user_update(user_id):
    _db.update_user(user_id, request.get_json(force=True, silent=True) or {})
    return jsonify({"code": 0, "message": "操作成功"})


@system_bp.route("/user/<int:user_id>", methods=["DELETE"])
@_token_required
def user_delete(user_id):
    _db.delete_user(user_id)
    return jsonify({"code": 0, "message": "操作成功"})


@system_bp.route("/user/reset-password", methods=["POST"])
@_token_required
def user_reset_password():
    data = request.get_json(force=True, silent=True) or {}
    _db.reset_password(data["id"], data.get("password", "admin123"))
    return jsonify({"code": 0, "message": "操作成功"})


@system_bp.route("/list-all-role", methods=["GET"])
@_token_required
def list_all_role():
    roles = _db.get_all_roles()
    return jsonify(
        {
            "code": 0,
            "message": "操作成功",
            "data": [
                {
                    "id": r.id,
                    "name": r.name,
                    "code": r.code,
                    "status": r.status,
                    "remark": r.remark,
                    "createTime": r.created_at,
                }
                for r in roles
            ],
        }
    )


@system_bp.route("/list-role-ids", methods=["POST"])
@_token_required
def list_role_ids():
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get("userId")
    ids = _db.get_role_ids_by_user(int(user_id)) if user_id is not None else []
    return jsonify({"code": 0, "message": "操作成功", "data": ids})


@system_bp.route("/role", methods=["POST"])
@_token_required
def role_list():
    data = request.get_json(force=True, silent=True) or {}
    name = data.get("name")
    code = data.get("code")
    status = data.get("status")
    result = _db.get_role_list(
        page=data.get("currentPage", 1),
        page_size=data.get("pageSize", 10),
        name=name if isinstance(name, str) else None,
        code=code if isinstance(code, str) else None,
        status=status if isinstance(status, (int, str)) else None,
    )
    result["list"] = [
        {
            "id": r["id"],
            "name": r["name"],
            "code": r["code"],
            "status": r["status"],
            "remark": r.get("remark"),
            "createTime": r["created_at"],
        }
        for r in result["list"]
    ]
    return jsonify({"code": 0, "message": "操作成功", "data": result})


@system_bp.route("/role/add", methods=["POST"])
@_token_required
def role_add():
    _db.create_role(request.get_json(force=True, silent=True) or {})
    return jsonify({"code": 0, "message": "操作成功"})


@system_bp.route("/role/<int:role_id>", methods=["PUT"])
@_token_required
def role_update(role_id):
    _db.update_role(role_id, request.get_json(force=True, silent=True) or {})
    return jsonify({"code": 0, "message": "操作成功"})


@system_bp.route("/role/<int:role_id>", methods=["DELETE"])
@_token_required
def role_delete(role_id):
    _db.delete_role(role_id)
    return jsonify({"code": 0, "message": "操作成功"})


@system_bp.route("/role/menu", methods=["POST"])
@_token_required
def role_set_menus():
    data = request.get_json(force=True, silent=True) or {}
    _db.set_role_menus(data["roleId"], data.get("menuIds", []))
    return jsonify({"code": 0, "message": "操作成功"})


@system_bp.route("/role/<int:role_id>/menu-ids", methods=["GET"])
@_token_required
def role_menu_ids(role_id):
    ids = _db.get_menu_ids_by_role(role_id)
    return jsonify({"code": 0, "message": "操作成功", "data": ids})


@system_bp.route("/menu", methods=["POST"])
@_token_required
def menu_list():
    data = request.get_json(force=True, silent=True) or {}
    title = data.get("title")
    menus = _db.get_menu_list(title=title if isinstance(title, str) else None)
    return jsonify(
        {
            "code": 0,
            "message": "操作成功",
            "data": [_menu_to_frontend(m) for m in menus],
        }
    )


@system_bp.route("/menu/add", methods=["POST"])
@_token_required
def menu_add():
    _db.create_menu(request.get_json(force=True, silent=True) or {})
    return jsonify({"code": 0, "message": "操作成功"})


@system_bp.route("/menu/<int:menu_id>", methods=["PUT"])
@_token_required
def menu_update(menu_id):
    _db.update_menu(menu_id, request.get_json(force=True, silent=True) or {})
    return jsonify({"code": 0, "message": "操作成功"})


@system_bp.route("/menu/<int:menu_id>", methods=["DELETE"])
@_token_required
def menu_delete(menu_id):
    _db.delete_menu(menu_id)
    return jsonify({"code": 0, "message": "操作成功"})


@system_bp.route("/dept", methods=["POST"])
@_token_required
def dept_list():
    data = request.get_json(force=True, silent=True) or {}
    name = data.get("name")
    status = data.get("status")
    depts = _db.get_dept_list(
        name=name if isinstance(name, str) else None,
        status=status if isinstance(status, (int, str)) else None,
    )
    return jsonify(
        {
            "code": 0,
            "message": "操作成功",
            "data": [_dept_to_frontend(d) for d in depts],
        }
    )


@system_bp.route("/dept/add", methods=["POST"])
@_token_required
def dept_add():
    _db.create_dept(request.get_json(force=True, silent=True) or {})
    return jsonify({"code": 0, "message": "操作成功"})


@system_bp.route("/dept/<int:dept_id>", methods=["PUT"])
@_token_required
def dept_update(dept_id):
    _db.update_dept(dept_id, request.get_json(force=True, silent=True) or {})
    return jsonify({"code": 0, "message": "操作成功"})


@system_bp.route("/dept/<int:dept_id>", methods=["DELETE"])
@_token_required
def dept_delete(dept_id):
    _db.delete_dept(dept_id)
    return jsonify({"code": 0, "message": "操作成功"})
