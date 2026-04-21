from mongo import assets_collection

sample_assets = [
    {
        "asset_code": "LAP-0201",
        "asset_name": "Laptop Dell Latitude 5440",
        "type": "laptop",
        "status": "using",
        "user": "Nguyễn Văn A",
        "department": "Phòng Kỹ Thuật",
        "location": "Tầng 3",
        "warranty": "15/08/2027"
    },
    {
        "asset_code": "LAP-0202",
        "asset_name": "Laptop HP ProBook 440",
        "type": "laptop",
        "status": "available",
        "user": "",
        "department": "Phòng Hành Chính",
        "location": "Kho thiết bị",
        "warranty": "21/05/2027"
    },
    {
        "asset_code": "LAP-0203",
        "asset_name": "Laptop Lenovo ThinkPad E14",
        "type": "laptop",
        "status": "maintenance",
        "user": "Trần Văn B",
        "department": "Phòng IT",
        "location": "Phòng Server",
        "warranty": "10/11/2026"
    },
    {
        "asset_code": "LAP-0204",
        "asset_name": "MacBook Pro M3",
        "type": "laptop",
        "status": "using",
        "user": "Lê Thị C",
        "department": "Phòng Thiết Kế",
        "location": "Tầng 4",
        "warranty": "30/09/2028"
    },
    {
        "asset_code": "LAP-0205",
        "asset_name": "Laptop Asus Vivobook 15",
        "type": "laptop",
        "status": "broken",
        "user": "Phạm Gia Bảo",
        "department": "Phòng Kỹ Thuật",
        "location": "Tầng 2",
        "warranty": "05/02/2026"
    },
    {
        "asset_code": "PC-0206",
        "asset_name": "PC Dell OptiPlex 7010",
        "type": "pc",
        "status": "using",
        "user": "Hoàng Minh D",
        "department": "Phòng Hành Chính",
        "location": "Tầng 1",
        "warranty": "12/12/2026"
    },
    {
        "asset_code": "PC-0207",
        "asset_name": "PC HP ProDesk 400 G9",
        "type": "pc",
        "status": "available",
        "user": "",
        "department": "Kho thiết bị",
        "location": "Phòng IT",
        "warranty": "18/06/2027"
    },
    {
        "asset_code": "PC-0208",
        "asset_name": "PC Lenovo ThinkCentre M70s",
        "type": "pc",
        "status": "using",
        "user": "Ngô Thị E",
        "department": "Phòng Kế Toán",
        "location": "Tầng 2",
        "warranty": "25/04/2027"
    },
    {
        "asset_code": "PC-0209",
        "asset_name": "PC Asus ExpertCenter D5",
        "type": "pc",
        "status": "maintenance",
        "user": "Bùi Quốc F",
        "department": "Phòng IT",
        "location": "Phòng Server",
        "warranty": "14/01/2026"
    },
    {
        "asset_code": "PC-0210",
        "asset_name": "PC Acer Veriton X",
        "type": "pc",
        "status": "using",
        "user": "Đỗ Mai G",
        "department": "Phòng Hành Chính",
        "location": "Tầng 1",
        "warranty": "09/10/2027"
    },
    {
        "asset_code": "PRI-0211",
        "asset_name": "Máy in HP LaserJet Pro 4003",
        "type": "printer",
        "status": "using",
        "user": "Lê Thị B",
        "department": "Phòng Hành Chính",
        "location": "Tầng 2",
        "warranty": "08/11/2025"
    },
    {
        "asset_code": "PRI-0212",
        "asset_name": "Máy in Canon LBP 2900",
        "type": "printer",
        "status": "available",
        "user": "",
        "department": "Kho thiết bị",
        "location": "Kho tầng 1",
        "warranty": "17/07/2026"
    },
    {
        "asset_code": "PRI-0213",
        "asset_name": "Máy in Brother HL-L2366DW",
        "type": "printer",
        "status": "maintenance",
        "user": "Trịnh Văn H",
        "department": "Phòng IT",
        "location": "Phòng Server",
        "warranty": "11/03/2026"
    },
    {
        "asset_code": "PRI-0214",
        "asset_name": "Máy in Epson EcoTank L3250",
        "type": "printer",
        "status": "using",
        "user": "Nguyễn Thu I",
        "department": "Phòng Thiết Kế",
        "location": "Tầng 4",
        "warranty": "29/12/2027"
    },
    {
        "asset_code": "NET-0215",
        "asset_name": "Router Mikrotik RB4011",
        "type": "router",
        "status": "using",
        "user": "Phạm Gia Bảo",
        "department": "Phòng IT",
        "location": "Phòng Server",
        "warranty": "15/03/2026"
    },
    {
        "asset_code": "NET-0216",
        "asset_name": "Router Cisco RV340",
        "type": "router",
        "status": "available",
        "user": "",
        "department": "Kho thiết bị",
        "location": "Kho tầng 1",
        "warranty": "22/08/2026"
    },
    {
        "asset_code": "NET-0217",
        "asset_name": "Router TP-Link ER605",
        "type": "router",
        "status": "maintenance",
        "user": "Vũ Khánh J",
        "department": "Phòng IT",
        "location": "Phòng Server",
        "warranty": "05/05/2027"
    },
    {
        "asset_code": "MON-0218",
        "asset_name": "Màn hình Dell P2422H",
        "type": "monitor",
        "status": "using",
        "user": "Nguyễn Văn A",
        "department": "Phòng Kỹ Thuật",
        "location": "Tầng 3",
        "warranty": "19/09/2027"
    },
    {
        "asset_code": "MON-0219",
        "asset_name": "Màn hình LG 27UP850",
        "type": "monitor",
        "status": "using",
        "user": "Lê Thị C",
        "department": "Phòng Thiết Kế",
        "location": "Tầng 4",
        "warranty": "07/01/2028"
    },
    {
        "asset_code": "ACC-0220",
        "asset_name": "Bộ lưu điện APC BX1600MI",
        "type": "ups",
        "status": "available",
        "user": "",
        "department": "Phòng IT",
        "location": "Phòng Server",
        "warranty": "28/02/2027"
    }
]

result = assets_collection.insert_many(sample_assets)
print("Inserted:", len(result.inserted_ids))
print("IDs:", result.inserted_ids)