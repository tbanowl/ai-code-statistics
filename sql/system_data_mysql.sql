-- 系统默认数据初始化脚本 (MySQL)
-- 注意：如果表中已有数据（例如 sys_user），脚本将跳过插入

-- 插入默认部门
INSERT IGNORE INTO sys_dept (id, parent_id, name, sort, status, created_at)
VALUES ('1', '0', '总公司', 0, 1, UNIX_TIMESTAMP(NOW()) * 1000);

-- 插入默认角色
INSERT IGNORE INTO sys_role (id, name, code, status, remark, created_at)
VALUES ('1', '超级管理员', 'admin', 1, NULL, UNIX_TIMESTAMP(NOW()) * 1000);

-- 插入默认用户 (用户名: admin, 密码: admin123)
-- 密码哈希使用 werkzeug.security.generate_password_hash('admin123')
INSERT IGNORE INTO sys_user (id, username, password, nickname, dept_id, status, created_at)
VALUES ('1', 'admin',
        'scrypt:32768:8:1$KXwP2szVcL3jUWJE$1585e0551cbcbe2d41fe829235237cad7bba4ce625e0a986b0c5979a0edc4e9fb5f681cd5dda03b54d9f1e41bcfb1a524b853514074932ef5152e347e65ff7a6',
        '管理员',
        LAST_INSERT_ID(),
        1,
        UNIX_TIMESTAMP(NOW()) * 1000);

-- 给管理员分配角色
INSERT IGNORE INTO sys_user_role (id, user_id, role_id)
VALUES ('1', '1', '1');

-- 插入系统管理根菜单
SET @system_menu_id = '1';
INSERT IGNORE INTO sys_menu (id, parent_id, title, path, icon, `rank`, menu_type, status, created_at)
VALUES (@system_menu_id, '0', '系统管理', '/system', 'ri:settings-3-line', 1, 0, 1, UNIX_TIMESTAMP(NOW()) * 1000);


INSERT IGNORE INTO sys_menu (id, parent_id, title, router_name, path, component, icon, `rank`, menu_type, status, created_at)
VALUES
    ('2', @system_menu_id, '用户管理', '用户管理', '/system/user/index', 'system/user/index', 'ri:admin-line', 1, 1, 1, UNIX_TIMESTAMP(NOW()) * 1000),
    ('3', @system_menu_id, '角色管理', '角色管理', '/system/role/index', 'system/role/index', 'ri:admin-fill', 2, 1, 1, UNIX_TIMESTAMP(NOW()) * 1000),
    ('4', @system_menu_id, '菜单管理', '菜单管理', '/system/menu/index', 'system/menu/index', 'ep:menu', 3, 1, 1, UNIX_TIMESTAMP(NOW()) * 1000),
    ('5', @system_menu_id, '部门管理', '部门管理', '/system/dept/index', 'system/dept/index', 'ri:git-branch-line', 4, 1, 1, UNIX_TIMESTAMP(NOW()) * 1000),
    ('6', @system_menu_id, '指标报表', '指标报表', '/metrics/commit-list/index', '/metrics/commit-list/index', 'ri:bar-chart-grouped-line', 5, 1, 1, UNIX_TIMESTAMP(NOW()) * 1000);


-- 插入仓库管理根菜单
SET @repo_menu_id = '7';
INSERT IGNORE INTO sys_menu (id, parent_id, title, router_name, path, icon, `rank`, menu_type, status, created_at)
VALUES (@repo_menu_id, '0', '仓库管理', '仓库管理', '/repo-manage', 'ri:git-repository-line', 2, 0, 1, UNIX_TIMESTAMP(NOW()) * 1000);


INSERT IGNORE INTO sys_menu (id, parent_id, title, router_name, path, component, icon, `rank`, menu_type, status, created_at)
VALUES
    ('8', @repo_menu_id, '仓库列表', '仓库列表', '/repo-manage/list', 'repo-manage/list/index', 'ri:git-repository-fill', 1, 1, 1, UNIX_TIMESTAMP(NOW()) * 1000),
    ('9', @repo_menu_id, 'SSH Key 管理', 'SSH Key 管理', '/repo-manage/ssh-key', 'repo-manage/ssh-key/index', 'ri:key-line', 2, 1, 1, UNIX_TIMESTAMP(NOW()) * 1000);

-- 给管理员角色分配所有菜单权限
INSERT IGNORE INTO sys_role_menu (id, role_id, menu_id)
SELECT id, (SELECT id FROM sys_role WHERE code = 'admin' LIMIT 1), id
FROM sys_menu;
