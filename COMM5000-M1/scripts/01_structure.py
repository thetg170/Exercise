"""
01_structure.py — Mục 1–2 EDA: xác định đơn vị phân tích và hiểu cấu trúc dữ liệu.

Mục đích : Số dòng/cột, kiểu dữ liệu thực tế vs kiểu nên có, phân loại biến, số giá trị unique,
           ví dụ giá trị, và lập data dictionary (ý nghĩa lấy từ sheet "Dataset"; phần tự suy ra
           được ghi là GIẢ ĐỊNH). In toàn bộ nhãn gốc của biến categorical (dùng repr để lộ khoảng trắng).
Input    : data_interim.parquet (hoặc file .xlsm gốc nếu parquet chưa có)
Output   : tables/01_data_dictionary.csv, tables/01_raw_value_counts.csv,
           tables/01_discrete_value_counts.csv
Bước EDA : Mục 1 (mục tiêu, đơn vị phân tích) và Mục 2 (cấu trúc dữ liệu).
"""
import re

import pandas as pd

from _common import load_raw, TAB, TARGET, CATEGORICAL_COLS, BINARY_COLS

df = load_raw()
n = len(df)
print(f"Kích thước: {n:,} dòng x {df.shape[1]} cột")
print("Cột:", list(df.columns))

# ---- đơn vị phân tích: có cột ID không?
# (sửa lỗi bản đầu: tìm chuỗi con "id" báo nhầm Insurance_Valid/Accidents/Tax_Paid -> dùng từ nguyên vẹn)
id_like = [c for c in df.columns if re.search(r"(^|_)(id|index|listing)($|_)", c.lower())]
print("Cột dạng ID:", id_like or "KHÔNG có -> GIẢ ĐỊNH: 1 dòng = 1 listing")

# ---- ý nghĩa gốc (sheet 'Dataset', B5) và phân loại do người phân tích đề xuất
meaning = {
    "Brand": "Manufacturer of the vehicle", "Model": "Model name", "Year": "Manufacturing year",
    "Mileage_kmpl": "Fuel efficiency (km/l)", "Engine_CC": "Engine displacement in cubic centimeters",
    "Horsepower": "Engine power output", "Fuel_Type": "Fuel category",
    "Transmission": "Manual or Automatic", "Owner_Type": "Ownership history", "Color": "Vehicle color",
    "City": "Registration city", "Kms_Driven": "Total distance traveled",
    "Insurance_Valid": "Insurance status", "Service_History": "Availability of service records",
    "Accidents": "Number of reported accidents", "Tax_Paid": "Road tax payment status",
    "Number_of_Doors": "Vehicle door count", "Seats": "Seating capacity",
    "Registration_Age": "Vehicle age since registration", "Car_Price": "Target variable, in Rupees",
}
spec = {  # cột: (kiểu nên có, nhóm biến, ghi chú / GIẢ ĐỊNH)
    "Brand": ("category", "categorical – nominal", "Dùng để tạo Segment (luxury = Audi, BMW, Mercedes)"),
    "Model": ("category", "categorical – nominal", "Lồng trong Brand (mỗi model thuộc 1 brand — kiểm tra ở 02)"),
    "Year": ("int", "numeric – discrete (thời gian)", "Năm sản xuất; có thể xem như biến thời gian"),
    "Mileage_kmpl": ("float", "numeric – continuous", "Đơn vị km/l theo mô tả gốc"),
    "Engine_CC": ("float", "numeric – continuous", "Đơn vị cc theo mô tả gốc"),
    "Horsepower": ("float", "numeric – continuous", "GIẢ ĐỊNH đơn vị hp (mô tả gốc không ghi đơn vị)"),
    "Fuel_Type": ("category", "categorical – nominal", ""),
    "Transmission": ("category", "categorical – nominal", "Mô tả gốc: Manual hoặc Automatic"),
    "Owner_Type": ("ordered category", "categorical – ordinal", "Thứ tự First < Second < Third < Fourth+ (suy từ nhãn)"),
    "Color": ("category", "categorical – nominal", ""),
    "City": ("category", "categorical – nominal", "Mô tả gốc: registration city (không phải nơi đăng tin)"),
    "Kms_Driven": ("int/float", "numeric – continuous", "GIẢ ĐỊNH đơn vị km (tên cột)"),
    "Insurance_Valid": ("bool (0/1)", "categorical – binary", "GIẢ ĐỊNH 1 = còn hiệu lực, 0 = không"),
    "Service_History": ("bool (0/1)", "categorical – binary", "GIẢ ĐỊNH 1 = có hồ sơ bảo dưỡng"),
    "Accidents": ("int", "numeric – discrete (count)", "Số vụ tai nạn được báo cáo"),
    "Tax_Paid": ("bool (0/1)", "categorical – binary", "GIẢ ĐỊNH 1 = đã nộp road tax"),
    "Number_of_Doors": ("int", "numeric – discrete", "Ít giá trị -> có thể xem như categorical ordinal"),
    "Seats": ("int", "numeric – discrete", "Ít giá trị -> có thể xem như categorical ordinal"),
    "Registration_Age": ("int", "numeric – discrete", "GIẢ ĐỊNH đơn vị năm; quan hệ với Year kiểm tra ở 02"),
    "Car_Price": ("float", "numeric – continuous (TARGET)", "Đơn vị Rupees theo mô tả gốc"),
}

rows = []
for c in df.columns:
    s = df[c]
    nun = s.nunique(dropna=True)
    if s.dtype.kind in "if":
        ex = f"min={s.min():.4g}; median={s.median():.4g}; max={s.max():.4g}"
    else:
        ex = "; ".join(repr(v) for v in s.value_counts().index[:4])
    rows.append({
        "variable": c, "pandas_dtype": str(s.dtype), "suggested_type": spec[c][0],
        "variable_class": spec[c][1], "n_unique": nun, "n_missing_NaN": int(s.isna().sum()),
        "example_values": ex, "meaning_original": meaning[c], "notes_assumptions": spec[c][2],
    })
dd = pd.DataFrame(rows)
dd.to_csv(TAB / "01_data_dictionary.csv", index=False)
with pd.option_context("display.max_colwidth", 60, "display.width", 250):
    print("\n=== Data dictionary ===")
    print(dd.drop(columns=["meaning_original"]).to_string(index=False))

# ---- toàn bộ nhãn gốc của biến categorical (repr để thấy khoảng trắng/hoa-thường)
vc_rows = []
print("\n=== Nhãn gốc của biến categorical ===")
for c in CATEGORICAL_COLS:
    vc = df[c].value_counts(dropna=False)
    print(f"\n--- {c}: {len(vc)} nhãn gốc ---")
    print(", ".join(f"{v!r}:{k:,}" for v, k in vc.items()))
    vc_rows += [(c, repr(v), k, round(100 * k / n, 3)) for v, k in vc.items()]
pd.DataFrame(vc_rows, columns=["variable", "raw_label_repr", "count", "pct"]) \
    .to_csv(TAB / "01_raw_value_counts.csv", index=False)

# ---- biến numeric rời rạc / nhị phân: tập giá trị
print("\n=== Tập giá trị của biến rời rạc / nhị phân ===")
dv_rows = []
for c in ["Year", "Registration_Age", "Accidents", "Number_of_Doors", "Seats"] + BINARY_COLS:
    vc = df[c].value_counts(dropna=False).sort_index()
    print(f"{c:<17} ({len(vc)} giá trị): " + ", ".join(f"{v}:{k:,}" for v, k in vc.items()))
    dv_rows += [(c, v, k, round(100 * k / n, 3)) for v, k in vc.items()]
pd.DataFrame(dv_rows, columns=["variable", "value", "count", "pct"]) \
    .to_csv(TAB / "01_discrete_value_counts.csv", index=False)

# ---- độ chính xác lưu trữ của biến continuous (số chữ số thập phân)
print("\n=== Biến continuous: tỉ lệ giá trị nguyên / số giá trị unique ===")
for c in ["Mileage_kmpl", "Engine_CC", "Horsepower", "Kms_Driven", TARGET]:
    s = df[c].dropna()
    print(f"{c:<14} % nguyên = {100 * (s == s.round()).mean():6.2f}%   unique = {s.nunique():,} / {len(s):,}")
