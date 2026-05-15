from datetime import datetime, timezone, timedelta


VN_TZ = timezone(timedelta(hours=7))

VALID_PERMISSION_ROLES = ["QUAN_LY", "NHAN_VIEN"]

# ADMIN không cần lưu quyền vì ADMIN luôn được làm tất cả
ADMIN_ROLE = "ADMIN"

# Các action dùng chung cho nhiều trang
VALID_ACTIONS = ["view", "create", "update", "delete", "export", "approve"]

# Danh sách page/module trong hệ thống
# Sau này có trang mới thì chỉ cần thêm vào đây
PERMISSION_MODULES = {
    "dashboard": {
        "name": "Dashboard",
        "actions": ["view"]
    },
    "users": {
        "name": "Người dùng",
        "actions": ["view", "create", "update", "delete"]
    },
    "permissions": {
        "name": "Phân quyền",
        "actions": ["view", "update"]
    },
    "employees": {
        "name": "Nhân viên",
        "actions": ["view", "create", "update", "delete", "export"]
    },
    "departments": {
        "name": "Phòng ban",
        "actions": ["view", "create", "update", "delete"]
    },
    "floors": {
        "name": "Tầng",
        "actions": ["view", "create", "update", "delete"]
    },
    "reports": {
        "name": "Báo cáo",
        "actions": ["view", "export"]
    },
}


# Quyền mặc định nếu role chưa có trong database
DEFAULT_ROLE_PERMISSIONS = {
    "QUAN_LY": {
        "dashboard": ["view"],
        "users": ["view"],
        "employees": ["view", "create", "update", "export"],
        "departments": ["view"],
        "floors": ["view"],
        "reports": ["view", "export"],
    },
    "NHAN_VIEN": {
        "dashboard": ["view"],
        "employees": ["view"],
        "reports": ["view"],
    }
}


def now_vietnam():
    return datetime.now(VN_TZ)


def format_datetime_vietnam(value):
    if not value:
        return None

    if isinstance(value, str):
        return value

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    vietnam_time = value.astimezone(VN_TZ)
    return vietnam_time.strftime("%d/%m/%Y %H:%M")


def permission_serializer(permission):
    return {
        "id": str(permission["_id"]),
        "role": permission.get("role"),
        "permissions": permission.get("permissions", {}),
        "created_at": format_datetime_vietnam(permission.get("created_at")),
        "updated_at": format_datetime_vietnam(permission.get("updated_at")),
    }


def create_permission_model(role, permissions):
    now = now_vietnam()

    return {
        "role": role,
        "permissions": permissions or {},
        "created_at": now,
        "updated_at": now,
    }


def update_permission_model(permissions):
    return {
        "permissions": permissions or {},
        "updated_at": now_vietnam(),
    }


def normalize_permissions(permissions):
    """
    Làm sạch dữ liệu quyền trước khi lưu DB.

    Input:
    {
        "users": ["view", "create"],
        "reports": ["view", "export"]
    }

    Output chỉ giữ module/action hợp lệ.
    """

    if not isinstance(permissions, dict):
        return {}

    clean_permissions = {}

    for module_key, actions in permissions.items():
        if module_key not in PERMISSION_MODULES:
            continue

        if not isinstance(actions, list):
            continue

        valid_actions_of_module = PERMISSION_MODULES[module_key]["actions"]

        clean_actions = []

        for action in actions:
            if action in valid_actions_of_module and action not in clean_actions:
                clean_actions.append(action)

        clean_permissions[module_key] = clean_actions

    return clean_permissions


def is_valid_permission(role, module_key, action):
    if role == ADMIN_ROLE:
        return True

    if role not in VALID_PERMISSION_ROLES:
        return False

    if module_key not in PERMISSION_MODULES:
        return False

    if action not in PERMISSION_MODULES[module_key]["actions"]:
        return False

    return True