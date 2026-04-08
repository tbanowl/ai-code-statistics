INSERT INTO sys_menu (
    parent_id,
    title,
    path,
    component,
    icon,
    rank,
    menu_type,
    status,
    show_link,
    keep_alive,
    created_at
)
SELECT
    0,
    '指标报表',
    '/metrics',
    NULL,
    'ri:bar-chart-grouped-line',
    3,
    0,
    1,
    1,
    0,
    1770000000000
WHERE NOT EXISTS (
    SELECT 1 FROM sys_menu WHERE path = '/metrics'
);

INSERT INTO sys_menu (
    parent_id,
    title,
    path,
    component,
    icon,
    rank,
    menu_type,
    status,
    show_link,
    keep_alive,
    created_at
)
SELECT
    parent_menu.id,
    '提交列表',
    '/metrics/commit-list',
    'metrics/commit-list/index',
    'ri:file-list-3-line',
    1,
    1,
    1,
    1,
    0,
    1770000000000
FROM sys_menu AS parent_menu
WHERE parent_menu.path = '/metrics'
  AND NOT EXISTS (
      SELECT 1 FROM sys_menu WHERE path = '/metrics/commit-list'
  );

INSERT INTO sys_role_menu (role_id, menu_id)
SELECT admin_role.id, menu_item.id
FROM sys_role AS admin_role
JOIN sys_menu AS menu_item
WHERE admin_role.code = 'admin'
  AND menu_item.path IN ('/metrics', '/metrics/commit-list')
  AND NOT EXISTS (
      SELECT 1
      FROM sys_role_menu AS role_menu
      WHERE role_menu.role_id = admin_role.id
        AND role_menu.menu_id = menu_item.id
  );
