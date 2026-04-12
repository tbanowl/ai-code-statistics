from typing import List, Optional, Dict, Any
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import select, delete
from .base import BaseDatabase, session_scope
from .models import SysUser, SysRole, SysMenu, SysDept, SysUserRole, SysRoleMenu, Base


class SystemDatabase(BaseDatabase):
    def __init__(self):
        super().__init__()
        Base.metadata.create_all(self.engine)


    def get_user_by_username(self, username: str) -> Optional[SysUser]:
        with session_scope(self.engine) as session:
            return session.execute(
                select(SysUser).where(SysUser.username == username)
            ).scalar_one_or_none()

    def verify_password(self, user: SysUser, password: str) -> bool:
        return check_password_hash(user.password, password)

    def get_user_roles(self, user_id: str) -> List[str]:
        with session_scope(self.engine) as session:
            rows = (
                session.execute(
                    select(SysRole.code)
                    .join(SysUserRole, SysRole.id == SysUserRole.role_id)
                    .where(SysUserRole.user_id == user_id)
                )
                .scalars()
                .all()
            )
            return list(rows)

    def get_menus_by_role_codes(self, role_codes: List[str]) -> List[SysMenu]:
        with session_scope(self.engine) as session:
            if "admin" in role_codes:
                return list(
                    session.execute(
                        select(SysMenu)
                        .where(SysMenu.status == 1)
                        .order_by(SysMenu.rank)
                    )
                    .scalars()
                    .all()
                )
            rows = (
                session.execute(
                    select(SysMenu)
                    .join(SysRoleMenu, SysMenu.id == SysRoleMenu.menu_id)
                    .join(SysRole, SysRole.id == SysRoleMenu.role_id)
                    .where(SysRole.code.in_(role_codes), SysMenu.status == 1)
                    .order_by(SysMenu.rank)
                )
                .scalars()
                .all()
            )
            return list(rows)

    def get_user_list(
        self,
        page: int,
        page_size: int,
        username: Optional[str] = None,
        phone: Optional[str] = None,
        status: Optional[int | str] = None,
        dept_id: Optional[int | str] = None,
    ) -> Dict:
        with session_scope(self.engine) as session:
            q = select(SysUser)
            if isinstance(status, str) and status != "":
                status = int(status)
            if isinstance(dept_id, str) and dept_id not in ("", "0"):
                dept_id = int(dept_id)
            if username:
                q = q.where(SysUser.username.like(f"%{username}%"))
            if phone:
                q = q.where(SysUser.phone.like(f"%{phone}%"))
            if status not in (None, ""):
                q = q.where(SysUser.status == status)
            if dept_id not in (None, "", 0, "0"):
                q = q.where(SysUser.dept_id == dept_id)
            total = len(session.execute(q).scalars().all())
            users = (
                session.execute(q.offset((page - 1) * page_size).limit(page_size))
                .scalars()
                .all()
            )
            return {
                "list": [u.to_dict() for u in users],
                "total": total,
                "pageSize": page_size,
                "currentPage": page,
            }

    def create_user(self, data: Dict) -> SysUser:
        with session_scope(self.engine) as session:
            user = SysUser(
                username=data["username"],
                password=generate_password_hash(data.get("password", "admin123")),
                nickname=data.get("nickname"),
                phone=data.get("phone"),
                email=data.get("email"),
                dept_id=data.get("deptId", data.get("parentId")),
                status=data.get("status", 1),
            )
            session.add(user)
            session.flush()
            for role_id in data.get("roleIds", []):
                session.add(SysUserRole(user_id=user.id, role_id=role_id))
            return user

    def update_user(self, user_id: str, data: Dict):
        with session_scope(self.engine) as session:
            user = session.get(SysUser, user_id)
            if not user:
                return None
            for field in ("nickname", "phone", "email", "status"):
                if field in data:
                    setattr(user, field, data[field])
            if "deptId" in data or "parentId" in data:
                next_dept_id = data.get("deptId", data.get("parentId"))
                user.dept_id = "0" if next_dept_id in (None, "") else next_dept_id
            if "roleIds" in data:
                session.execute(
                    delete(SysUserRole).where(SysUserRole.user_id == user_id)
                )
                for role_id in data["roleIds"]:
                    session.add(SysUserRole(user_id=user_id, role_id=role_id))
            return user

    def delete_user(self, user_id: int):
        with session_scope(self.engine) as session:
            session.execute(delete(SysUserRole).where(SysUserRole.user_id == user_id))
            session.execute(delete(SysUser).where(SysUser.id == user_id))

    def reset_password(self, user_id: int, password: str):
        with session_scope(self.engine) as session:
            user = session.get(SysUser, user_id)
            if user:
                user.password = generate_password_hash(password)

    def get_role_ids_by_user(self, user_id: str) -> List[str]:
        with session_scope(self.engine) as session:
            return list(
                session.execute(
                    select(SysUserRole.role_id).where(SysUserRole.user_id == user_id)
                )
                .scalars()
                .all()
            )

    def get_all_roles(self) -> List[SysRole]:
        with session_scope(self.engine) as session:
            return list(
                session.execute(select(SysRole).where(SysRole.status == 1))
                .scalars()
                .all()
            )

    def get_role_list(
        self,
        page: int,
        page_size: int,
        name: Optional[str] = None,
        code: Optional[str] = None,
        status: Optional[int | str] = None,
    ) -> Dict:
        with session_scope(self.engine) as session:
            q = select(SysRole)
            if isinstance(status, str) and status != "":
                status = int(status)
            if name:
                q = q.where(SysRole.name.like(f"%{name}%"))
            if code:
                q = q.where(SysRole.code.like(f"%{code}%"))
            if status is not None and status != "":
                q = q.where(SysRole.status == status)
            total = len(session.execute(q).scalars().all())
            roles = (
                session.execute(q.offset((page - 1) * page_size).limit(page_size))
                .scalars()
                .all()
            )
            return {
                "list": [r.to_dict() for r in roles],
                "total": total,
                "pageSize": page_size,
                "currentPage": page,
            }

    def create_role(self, data: Dict) -> SysRole:
        with session_scope(self.engine) as session:
            role = SysRole(
                name=data["name"],
                code=data["code"],
                remark=data.get("remark"),
                status=data.get("status", 1),
            )
            session.add(role)
            return role

    def update_role(self, role_id: int, data: Dict):
        with session_scope(self.engine) as session:
            role = session.get(SysRole, role_id)
            if not role:
                return None
            for field in ("name", "code", "remark", "status"):
                if field in data:
                    setattr(role, field, data[field])
            return role

    def delete_role(self, role_id: int):
        with session_scope(self.engine) as session:
            session.execute(delete(SysRoleMenu).where(SysRoleMenu.role_id == role_id))
            session.execute(delete(SysUserRole).where(SysUserRole.role_id == role_id))
            session.execute(delete(SysRole).where(SysRole.id == role_id))

    def set_role_menus(self, role_id: int, menu_ids: List[int]):
        with session_scope(self.engine) as session:
            session.execute(delete(SysRoleMenu).where(SysRoleMenu.role_id == role_id))
            for menu_id in menu_ids:
                session.add(SysRoleMenu(role_id=role_id, menu_id=menu_id))

    def get_menu_ids_by_role(self, role_id: str) -> List[str]:
        with session_scope(self.engine) as session:
            return list(
                session.execute(
                    select(SysRoleMenu.menu_id).where(SysRoleMenu.role_id == role_id)
                )
                .scalars()
                .all()
            )

    def get_menu_list(self, title: Optional[str] = None) -> List[SysMenu]:
        with session_scope(self.engine) as session:
            q = select(SysMenu)
            if title:
                q = q.where(SysMenu.title.like(f"%{title}%"))
            return list(session.execute(q.order_by(SysMenu.rank)).scalars().all())

    def create_menu(self, data: Dict) -> SysMenu:
        with session_scope(self.engine) as session:
            menu = SysMenu(
                parent_id=data.get("parentId", "0"),
                title=data["title"],
                router_name=data["name"],
                path=data.get("path"),
                component=data.get("component"),
                icon=data.get("icon"),
                rank=data.get("rank", 0),
                menu_type=data.get("menuType", 0),
                status=data.get("status", 1),
                show_link=data.get("showLink", True),
                keep_alive=data.get("keepAlive", False),
            )
            menu.show_link = 1 if data.get("showLink", True) else 0
            menu.keep_alive = 1 if data.get("keepAlive", False) else 0
            session.add(menu)
            return menu

    def update_menu(self, menu_id: int, data: Dict):
        with session_scope(self.engine) as session:
            menu = session.get(SysMenu, menu_id)
            if not menu:
                return None
            field_map = {
                "parentId": "parent_id",
                "title": "title",
                "router_name":"name",
                "path": "path",
                "component": "component",
                "icon": "icon",
                "rank": "rank",
                "menuType": "menu_type",
                "status": "status",
                "showLink": "show_link",
                "keepAlive": "keep_alive",
            }
            for k, v in field_map.items():
                if k in data:
                    setattr(menu, v, data[k])
            return menu

    def delete_menu(self, menu_id: int):
        with session_scope(self.engine) as session:
            session.execute(delete(SysRoleMenu).where(SysRoleMenu.menu_id == menu_id))
            session.execute(delete(SysMenu).where(SysMenu.id == menu_id))

    def get_dept_list(
        self, name: Optional[str] = None, status: Optional[int | str] = None
    ) -> List[SysDept]:
        with session_scope(self.engine) as session:
            q = select(SysDept)
            if isinstance(status, str) and status != "":
                status = int(status)
            if name:
                q = q.where(SysDept.name.like(f"%{name}%"))
            if status is not None and status != "":
                q = q.where(SysDept.status == status)
            return list(session.execute(q.order_by(SysDept.sort)).scalars().all())

    def create_dept(self, data: Dict) -> SysDept:
        with session_scope(self.engine) as session:
            dept = SysDept(
                parent_id=data.get("parentId", 0),
                name=data["name"],
                sort=data.get("sort", 0),
                status=data.get("status", 1),
            )
            session.add(dept)
            return dept

    def update_dept(self, dept_id: int, data: Dict):
        with session_scope(self.engine) as session:
            dept = session.get(SysDept, dept_id)
            if not dept:
                return None
            for field in ("name", "sort", "status"):
                if field in data:
                    setattr(dept, field, data[field])
            if "parentId" in data:
                dept.parent_id = data["parentId"]
            return dept

    def delete_dept(self, dept_id: int):
        with session_scope(self.engine) as session:
            session.execute(delete(SysDept).where(SysDept.id == dept_id))
