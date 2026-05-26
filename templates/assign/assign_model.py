from mongo import assets_collection


# Đếm số lượng bản ghi cấp phát tài sản.
# Nếu có query thì đếm theo điều kiện đó.
# Nếu không có query thì đếm tất cả tài sản trong collection.
def count_assign_assets(query=None):
    return assets_collection.count_documents(query or {})


# Tìm danh sách bản ghi cấp phát tài sản.
# Hàm này có phân trang bằng skip + limit.
# Có thể sắp xếp theo field truyền vào, mặc định là _id mới nhất trước.
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


# Lấy danh sách bản ghi để phục vụ phần đếm, lọc hoặc thống kê.
# Không giới hạn field, vì service cần đọc nhiều thông tin khác nhau.
def find_assign_assets_for_counts(query=None):
    return assets_collection.find(query or {})


# Tìm một bản ghi cấp phát tài sản theo điều kiện truyền vào.
# Ví dụ: tìm theo _id, asset_code hoặc user_id.
def find_assign_asset_by_query(query):
    return assets_collection.find_one(query)


# Xóa một bản ghi cấp phát tài sản theo điều kiện truyền vào.
# Kết quả trả về có deleted_count để biết xóa thành công hay chưa.
def delete_assign_asset_by_query(query):
    return assets_collection.delete_one(query)


# Cập nhật một bản ghi cấp phát tài sản theo điều kiện truyền vào.
# update_data thường là dạng {"$set": {...}} để chỉ sửa các field cần đổi.
def update_assign_asset_by_query(query, update_data):
    return assets_collection.update_one(query, update_data)
