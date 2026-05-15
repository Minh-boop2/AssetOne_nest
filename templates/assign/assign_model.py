from mongo import assets_collection


# Đếm số lượng bản ghi cấp phát tài sản
# Nếu có query thì đếm theo điều kiện, không có thì đếm tất cả
def count_assign_assets(query=None):
    return assets_collection.count_documents(query or {})


# Tìm danh sách bản ghi cấp phát tài sản
# Có hỗ trợ phân trang, giới hạn số lượng và sắp xếp
def find_assign_assets(
    query=None,
    skip=0,
    limit=10,
    sort_field="_id",
    sort_order=-1,
):
    return list(
        assets_collection
        .find(query or {})
        .sort(sort_field, sort_order)
        .skip(skip)
        .limit(limit)
    )


# Lấy danh sách bản ghi để phục vụ việc đếm, lọc hoặc thống kê
def find_assign_assets_for_counts(query=None):
    return assets_collection.find(query or {})


# Tìm một bản ghi cấp phát tài sản theo điều kiện truyền vào
def find_assign_asset_by_query(query):
    return assets_collection.find_one(query)


# Xóa một bản ghi cấp phát tài sản theo điều kiện truyền vào
def delete_assign_asset_by_query(query):
    return assets_collection.delete_one(query)


# Cập nhật một bản ghi cấp phát tài sản theo điều kiện truyền vào
def update_assign_asset_by_query(query, update_data):
    return assets_collection.update_one(query, update_data)