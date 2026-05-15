import math
import re
from bson import ObjectId

from .assign_model import (
    count_assign_assets,
    find_assign_assets,
    find_assign_assets_for_counts,
    find_assign_asset_by_query,
    delete_assign_asset_by_query,
    update_assign_asset_by_query,
)


# Những cột sẽ được dùng khi người dùng nhập từ khóa tìm kiếm cấp phát
SEARCH_FIELDS = [
    "asset_name",
    "asset",
    "asset_code",
    "user",
    "receiver",
    "department",
    "location",
    "status",
    "type",
    "category",
    "warranty",
    "spec",
    "notes",
]


# Những trạng thái trong bảng assets được hiểu là tài sản đang được sử dụng
USING_STATUS_VALUES = ["using", "Đang sử dụng"]

# Những trạng thái trong bảng assets được hiểu là tài sản chưa được sử dụng
UNUSED_STATUS_VALUES = ["available", "Chưa sử dụng"]


# Đổi trạng thái của asset sang trạng thái hiển thị bên màn cấp phát
def map_asset_status_to_assign_status(status):
    status = (status or "").strip()

    if status in USING_STATUS_VALUES:
        return "Đang sử dụng"

    if status in UNUSED_STATUS_VALUES:
        return "Chưa dùng"

    return None


# Đổi trạng thái người dùng chọn ở màn cấp phát thành danh sách trạng thái trong assets
# Dùng để lọc dữ liệu đúng trong database
def map_assign_status_to_asset_status_values(status):
    status = (status or "").strip()

    if not status or status == "Tất cả":
        return USING_STATUS_VALUES + UNUSED_STATUS_VALUES

    if status == "Đang sử dụng":
        return USING_STATUS_VALUES

    if status in ["Chưa dùng", "Chưa sử dụng"]:
        return UNUSED_STATUS_VALUES

    return []


# Lấy dữ liệu từ assets rồi đổi sang dạng dữ liệu mà màn cấp phát cần dùng
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

        "receiver": user,
        "user": user,

        "department": row.get("department") or "",
        "location": row.get("location") or "",

        "date": row.get("date") or row.get("assigned_date") or "",
        "return_date": row.get("return_date") or "",

        "warranty": row.get("warranty") or "",
        "spec": row.get("spec") or row.get("notes") or "",
        "notes": row.get("notes") or row.get("spec") or "",
    }


# Tạo điều kiện tìm một bản ghi cấp phát
# Có thể tìm bằng _id, asset_code hoặc id
def build_id_query(asset_id):
    queries = [
        {"asset_code": asset_id},
        {"id": asset_id},
    ]

    if ObjectId.is_valid(asset_id):
        queries.insert(0, {"_id": ObjectId(asset_id)})

    return {"$or": queries}


# Tạo điều kiện lọc danh sách cấp phát
# Có thể lọc theo tìm kiếm, loại tài sản, phòng ban, trạng thái và vị trí
def build_assign_query(
    search="",
    asset_type="Tất cả",
    department="Tất cả",
    status="Tất cả",
    location="Tất cả",
):
    conditions = []

    # Assign chỉ lấy 2 trạng thái này từ assets.
    allowed_status_values = map_assign_status_to_asset_status_values(status)

    if not allowed_status_values:
        return {"_id": {"$exists": False}}

    conditions.append({
        "status": {
            "$in": allowed_status_values
        }
    })

    if search:
        safe_search = re.escape(search.strip())

        conditions.append({
            "$or": [
                {field: {"$regex": safe_search, "$options": "i"}}
                for field in SEARCH_FIELDS
            ]
        })

    if asset_type and asset_type != "Tất cả":
        conditions.append({
            "$or": [
                {"type": asset_type},
                {"category": asset_type},
            ]
        })

    if department and department != "Tất cả":
        conditions.append({"department": department})

    if location and location != "Tất cả":
        conditions.append({"location": location})

    if len(conditions) == 1:
        return conditions[0]

    return {"$and": conditions}


# Đếm số lượng bản ghi cấp phát theo loại, phòng ban, vị trí và trạng thái
# Dữ liệu này dùng cho bộ lọc và thống kê nhanh trên giao diện
def get_assign_filter_counts():
    base_query = {
        "status": {
            "$in": USING_STATUS_VALUES + UNUSED_STATUS_VALUES
        }
    }

    total = count_assign_assets(base_query)

    type_counts = {"all": total}
    department_counts = {"all": total}
    location_counts = {"all": total}

    status_counts = {
        "all": total,
        "Đang sử dụng": count_assign_assets({
            "status": {"$in": USING_STATUS_VALUES}
        }),
        "Chưa dùng": count_assign_assets({
            "status": {"$in": UNUSED_STATUS_VALUES}
        }),
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


# Lấy danh sách cấp phát có phân trang, tìm kiếm, lọc và thống kê bộ lọc
def list_assigns(
    page=1,
    per_page=10,
    search="",
    asset_type="Tất cả",
    department="Tất cả",
    status="Tất cả",
    location="Tất cả",
):
    page = max(1, int(page))
    per_page = max(1, int(per_page))

    query = build_assign_query(
        search=search,
        asset_type=asset_type,
        department=department,
        status=status,
        location=location,
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

        # Chặn chắc chắn: không cho trạng thái khác lọt qua.
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
        "filter_counts": get_assign_filter_counts(),
    }


# Tìm một bản ghi cấp phát theo id, mã tài sản hoặc mongo id
def find_assign(assign_id):
    item = find_assign_asset_by_query(build_id_query(assign_id))

    if not item:
        return None

    row = normalize_assign_from_asset(item)

    if row["status"] not in ["Đang sử dụng", "Chưa dùng"]:
        return None

    return row


# Xóa một bản ghi cấp phát
def delete_assign(assign_id):
    # Cẩn thận: assign đang là view từ assets.
    # Nếu gọi delete thì sẽ xóa asset.
    result = delete_assign_asset_by_query(build_id_query(assign_id))

    return {
        "deleted": result.deleted_count > 0,
        "deleted_count": result.deleted_count,
    }


# Cập nhật trạng thái cấp phát theo id
# Trạng thái cấp phát sẽ được đổi ngược lại thành trạng thái trong assets
def update_assign_status_by_id(assign_id, assign_status):
    if assign_status == "Đang sử dụng":
        asset_status = "Đang sử dụng"
    elif assign_status in ["Chưa dùng", "Chưa sử dụng"]:
        asset_status = "Chưa sử dụng"
    else:
        return {
            "updated": False,
            "modified_count": 0,
            "item": None,
        }

    result = update_assign_asset_by_query(
        build_id_query(assign_id),
        {"$set": {"status": asset_status}}
    )

    if result.matched_count <= 0:
        return {
            "updated": False,
            "modified_count": 0,
            "item": None,
        }

    return {
        "updated": True,
        "modified_count": result.modified_count,
        "item": find_assign(assign_id),
    }


# Duyệt cấp phát, chuyển trạng thái sang đang sử dụng
def approve_assign(assign_id):
    return update_assign_status_by_id(assign_id, "Đang sử dụng")


# Từ chối hoặc hủy cấp phát, chuyển trạng thái sang chưa dùng
def reject_assign(assign_id):
    return update_assign_status_by_id(assign_id, "Chưa dùng")


# Cập nhật trạng thái cấp phát theo trạng thái được gửi lên
def update_assign_status(assign_id, status):
    return update_assign_status_by_id(assign_id, status)