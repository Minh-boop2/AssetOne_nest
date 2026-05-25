import math
import re
from datetime import datetime
from bson import ObjectId

from .assign_model import (
    count_assign_assets,
    find_assign_assets,
    find_assign_assets_for_counts,
    find_assign_asset_by_query,
    delete_assign_asset_by_query,
    update_assign_asset_by_query,
)


SEARCH_FIELDS = [
    "asset_name",
    "asset",
    "asset_code",
    "user",
    "receiver",
    "user_id",
    "employee_code",
    "department",
    "location",
    "status",
    "type",
    "category",
    "warranty",
    "spec",
    "notes",
]


USING_STATUS_VALUES = [
    "using",
    "Đang sử dụng",
    "Dang su dung",
    "Hoàn thành",
]

UNUSED_STATUS_VALUES = [
    "available",
    "Chưa sử dụng",
    "Chua su dung",
    "Chưa dùng",
]

FULL_ASSIGN_ROLES = [
    "ADMIN",
    "QUAN_LY",
]


def serialize_datetime(value):
    if not value:
        return ""

    if isinstance(value, datetime):
        return value.isoformat()

    return value


def get_current_user_id(current_user):
    if not current_user:
        return ""

    return str(
        current_user.get("_id")
        or current_user.get("id")
        or current_user.get("user_id")
        or ""
    )


def user_can_view_all_assigns(current_user):
    if not current_user:
        return False

    return current_user.get("role") in FULL_ASSIGN_ROLES


def merge_assign_queries(*queries):
    clean_queries = []

    for query in queries:
        if query:
            clean_queries.append(query)

    if not clean_queries:
        return {}

    if len(clean_queries) == 1:
        return clean_queries[0]

    return {
        "$and": clean_queries
    }


def build_assign_visibility_query(current_user=None):
    if not current_user:
        return {}

    if user_can_view_all_assigns(current_user):
        return {}

    current_user_id = get_current_user_id(current_user)
    employee_code = current_user.get("employee_code") or ""

    owner_conditions = []

    if current_user_id:
        owner_conditions.append({
            "user_id": current_user_id
        })

    if employee_code:
        owner_conditions.append({
            "employee_code": employee_code
        })

    if not owner_conditions:
        return {
            "_id": {
                "$exists": False
            }
        }

    return {
        "$or": owner_conditions
    }


def map_asset_status_to_assign_status(status):
    status = (status or "").strip()

    if status in USING_STATUS_VALUES:
        return "Đang sử dụng"

    if status in UNUSED_STATUS_VALUES:
        return "Chưa dùng"

    return None


def map_assign_status_to_asset_status_values(status):
    status = (status or "").strip()

    if not status or status == "Tất cả":
        return USING_STATUS_VALUES + UNUSED_STATUS_VALUES

    if status == "Đang sử dụng":
        return USING_STATUS_VALUES

    if status in ["Chưa dùng", "Chưa sử dụng"]:
        return UNUSED_STATUS_VALUES

    return []


def normalize_assign_from_asset(item):
    row = dict(item)

    mongo_id = str(row.get("_id", ""))

    asset_name = row.get("asset") or row.get("asset_name") or ""
    user = row.get("receiver") or row.get("user") or ""

    assign_status = map_asset_status_to_assign_status(row.get("status"))

    return {
        "id": mongo_id,
        "mongo_id": mongo_id,

        "asset_code": row.get("asset_code") or "",
        "asset": asset_name,
        "asset_name": asset_name,

        "type": row.get("type") or row.get("category") or "",
        "category": row.get("category") or row.get("type") or "",

        "status": assign_status,
        "asset_status": row.get("status") or "",

        "user_id": row.get("user_id") or "",
        "employee_code": row.get("employee_code") or "",

        "receiver": user,
        "user": user,

        "department": row.get("department") or "",
        "location": row.get("location") or "",

        "date": serialize_datetime(
            row.get("date")
            or row.get("assigned_date")
            or row.get("assigned_at")
            or ""
        ),
        "return_date": serialize_datetime(
            row.get("return_date")
            or row.get("returned_at")
            or ""
        ),

        "assigned_at": serialize_datetime(row.get("assigned_at")),
        "returned_at": serialize_datetime(row.get("returned_at")),
        "created_at": serialize_datetime(row.get("created_at")),
        "updated_at": serialize_datetime(row.get("updated_at")),

        "warranty": row.get("warranty") or "",
        "spec": row.get("spec") or row.get("notes") or "",
        "notes": row.get("notes") or row.get("spec") or "",
    }


def build_id_query(asset_id):
    queries = [
        {
            "asset_code": asset_id
        },
        {
            "id": asset_id
        },
    ]

    if ObjectId.is_valid(asset_id):
        queries.insert(0, {
            "_id": ObjectId(asset_id)
        })

    return {
        "$or": queries
    }


def build_assign_query(
    search="",
    asset_type="Tất cả",
    department="Tất cả",
    status="Tất cả",
    location="Tất cả",
):
    conditions = []

    allowed_status_values = map_assign_status_to_asset_status_values(status)

    if not allowed_status_values:
        return {
            "_id": {
                "$exists": False
            }
        }

    conditions.append({
        "status": {
            "$in": allowed_status_values
        }
    })

    if search:
        safe_search = re.escape(search.strip())

        conditions.append({
            "$or": [
                {
                    field: {
                        "$regex": safe_search,
                        "$options": "i"
                    }
                }
                for field in SEARCH_FIELDS
            ]
        })

    if asset_type and asset_type != "Tất cả":
        conditions.append({
            "$or": [
                {
                    "type": asset_type
                },
                {
                    "category": asset_type
                },
            ]
        })

    if department and department != "Tất cả":
        conditions.append({
            "department": department
        })

    if location and location != "Tất cả":
        conditions.append({
            "location": location
        })

    if len(conditions) == 1:
        return conditions[0]

    return {
        "$and": conditions
    }


def build_status_count_query(status_values, visibility_query=None):
    return merge_assign_queries(
        {
            "status": {
                "$in": status_values
            }
        },
        visibility_query,
    )


def get_assign_filter_counts(current_user=None):
    visibility_query = build_assign_visibility_query(current_user)

    base_query = merge_assign_queries(
        {
            "status": {
                "$in": USING_STATUS_VALUES + UNUSED_STATUS_VALUES
            }
        },
        visibility_query,
    )

    total = count_assign_assets(base_query)

    type_counts = {
        "all": total
    }

    department_counts = {
        "all": total
    }

    location_counts = {
        "all": total
    }

    status_counts = {
        "all": total,
        "Đang sử dụng": count_assign_assets(
            build_status_count_query(
                USING_STATUS_VALUES,
                visibility_query,
            )
        ),
        "Chưa dùng": count_assign_assets(
            build_status_count_query(
                UNUSED_STATUS_VALUES,
                visibility_query,
            )
        ),
    }

    for item in find_assign_assets_for_counts(base_query):
        asset_type = item.get("type") or item.get("category")
        department = item.get("department")
        location = item.get("location")

        if asset_type:
            type_counts[asset_type] = type_counts.get(asset_type, 0) + 1

        if department:
            department_counts[department] = department_counts.get(department, 0) + 1

        if location:
            location_counts[location] = location_counts.get(location, 0) + 1

    return {
        "type": type_counts,
        "department": department_counts,
        "location": location_counts,
        "status": status_counts,
    }


def list_assigns(
    page=1,
    per_page=10,
    search="",
    asset_type="Tất cả",
    department="Tất cả",
    status="Tất cả",
    location="Tất cả",
    current_user=None,
):
    try:
        page = int(page)
    except Exception:
        page = 1

    try:
        per_page = int(per_page)
    except Exception:
        per_page = 10

    page = max(1, page)
    per_page = max(1, min(per_page, 100))

    filter_query = build_assign_query(
        search=search,
        asset_type=asset_type,
        department=department,
        status=status,
        location=location,
    )

    visibility_query = build_assign_visibility_query(current_user)

    query = merge_assign_queries(
        filter_query,
        visibility_query,
    )

    total_items = count_assign_assets(query)
    total_pages = math.ceil(total_items / per_page) if total_items > 0 else 1

    if page > total_pages:
        page = total_pages

    skip = (page - 1) * per_page

    raw_items = find_assign_assets(
        query=query,
        skip=skip,
        limit=per_page,
        sort_field="_id",
        sort_order=-1,
    )

    items = []

    for item in raw_items:
        row = normalize_assign_from_asset(item)

        if row["status"] in ["Đang sử dụng", "Chưa dùng"]:
            items.append(row)

    return {
        "items": items,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_items": total_items,
            "total_pages": total_pages,
        },
        "filter_counts": get_assign_filter_counts(current_user=current_user),
        "scope": {
            "view_all": user_can_view_all_assigns(current_user),
            "role": current_user.get("role") if current_user else None,
            "user_id": get_current_user_id(current_user),
            "employee_code": current_user.get("employee_code") if current_user else None,
        }
    }


def find_assign(assign_id, current_user=None):
    id_query = build_id_query(assign_id)
    visibility_query = build_assign_visibility_query(current_user)

    query = merge_assign_queries(
        id_query,
        visibility_query,
    )

    item = find_assign_asset_by_query(query)

    if not item:
        return None

    row = normalize_assign_from_asset(item)

    if row["status"] not in ["Đang sử dụng", "Chưa dùng"]:
        return None

    return row


def delete_assign(assign_id, current_user=None):
    id_query = build_id_query(assign_id)
    visibility_query = build_assign_visibility_query(current_user)

    query = merge_assign_queries(
        id_query,
        visibility_query,
    )

    result = delete_assign_asset_by_query(query)

    return {
        "deleted": result.deleted_count > 0,
        "deleted_count": result.deleted_count,
    }


def build_update_data_for_assign_status(assign_status):
    assign_status = (assign_status or "").strip()
    now = datetime.utcnow()

    if assign_status == "Đang sử dụng":
        return {
            "status": "using",
            "returned_at": "",
            "updated_at": now,
        }

    if assign_status in ["Chưa dùng", "Chưa sử dụng"]:
        return {
            "status": "available",
            "user_id": "",
            "employee_code": "",
            "user": "",
            "receiver": "",
            "department": "",
            "location": "",
            "returned_at": now,
            "updated_at": now,
        }

    return None


def update_assign_status_by_id(assign_id, assign_status, current_user=None):
    update_data = build_update_data_for_assign_status(assign_status)

    if not update_data:
        return {
            "updated": False,
            "modified_count": 0,
            "item": None,
            "message": "Trạng thái không hợp lệ",
            "status_code": 400,
        }

    id_query = build_id_query(assign_id)
    visibility_query = build_assign_visibility_query(current_user)

    query = merge_assign_queries(
        id_query,
        visibility_query,
    )

    result = update_assign_asset_by_query(
        query,
        {
            "$set": update_data
        }
    )

    if result.matched_count <= 0:
        return {
            "updated": False,
            "modified_count": 0,
            "item": None,
            "message": "Không tìm thấy bản ghi cấp phát",
            "status_code": 404,
        }

    updated_item = find_assign(
        assign_id,
        current_user=current_user,
    )

    return {
        "updated": True,
        "modified_count": result.modified_count,
        "item": updated_item,
        "message": "Cập nhật trạng thái cấp phát thành công",
        "status_code": 200,
    }


def approve_assign(assign_id, current_user=None):
    return update_assign_status_by_id(
        assign_id=assign_id,
        assign_status="Đang sử dụng",
        current_user=current_user,
    )


def reject_assign(assign_id, current_user=None):
    return update_assign_status_by_id(
        assign_id=assign_id,
        assign_status="Chưa dùng",
        current_user=current_user,
    )


def update_assign_status(assign_id, status, current_user=None):
    return update_assign_status_by_id(
        assign_id=assign_id,
        assign_status=status,
        current_user=current_user,
    )