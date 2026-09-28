"""
00_load_and_inspect.py — BƯỚC 0: Kiểm tra file trước khi phân tích.

Mục đích :
  (a) Liệt kê các phần bên trong file .xlsm (zip), danh sách sheet, kích thước, merged cells.
  (b) Đọc sheet mô tả "Dataset" (data dictionary gốc) và kiểm tra ô B6 (dấu hiệu randomization).
  (c) Liệt kê macro/VBA bằng olevba — CHỈ đọc mã nguồn, KHÔNG chạy macro.
  (d) Quét XML của sheet DATA: công thức, dòng bị ẩn, kiểu ô (số / chuỗi / lỗi / boolean).
  (e) So sánh tốc độ đọc (openpyxl vs calamine), rồi lưu data_interim.parquet (CHƯA làm sạch).
Input    : [22_9] COMM5000-Used_Car_Price_Prediction.xlsm (không sửa)
Output   : data_interim.parquet, tables/00_*.csv, tables/00_vba_source.txt
Bước EDA : Bước 0 — kiểm tra file.
"""
import re
import time
import zipfile

import pandas as pd

from _common import (RAW_XLSM, INTERIM, INTERIM_SOURCE, TAB, DATA_SHEET, read_raw_xlsm,
                     source_signature)

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

# ---------------------------------------------------------------- (a) cấu trúc zip
z = zipfile.ZipFile(RAW_XLSM)
parts = pd.DataFrame([(i.filename, i.file_size, i.compress_size) for i in z.infolist()],
                     columns=["part", "bytes_uncompressed", "bytes_compressed"])
print("=== (a) Các phần trong file .xlsm ===")
print(parts.to_string(index=False))
parts.to_csv(TAB / "00_xlsm_parts.csv", index=False)

wb_xml = z.read("xl/workbook.xml").decode()
sheets = re.findall(r'<sheet name="([^"]+)" sheetId="(\d+)" r:id="(rId\d+)"', wb_xml)
rels = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="([^"]+)"',
                       z.read("xl/_rels/workbook.xml.rels").decode()))
rows = []
for name, sid, rid in sheets:
    target = "xl/" + rels[rid]
    with z.open(target) as f:
        head = f.read(4000).decode("utf-8", "replace")
    dim = re.search(r'<dimension ref="([^"]+)"', head).group(1)
    rows.append((name, target, dim))
sheet_info = pd.DataFrame(rows, columns=["sheet", "xml_part", "dimension"])
print("\n=== Danh sách sheet ===")
print(sheet_info.to_string(index=False))
print("Defined names:", re.findall(r'<definedName name="([^"]+)"[^>]*>([^<]*)<', wb_xml))
sheet_info.to_csv(TAB / "00_sheets.csv", index=False)

# ---------------------------------------------------------------- (b) sheet mô tả "Dataset"
# Không load cả workbook bằng openpyxl (sheet DATA ~710MB XML); đọc thẳng XML của sheet nhỏ.
sst =[re.sub(r"<[^>]+>", "", s) for s in
       re.findall(r"<si>(.*?)</si>", z.read("xl/sharedStrings.xml").decode(), flags=re.S)]
desc_xml = z.read("xl/worksheets/sheet1.xml").decode()
print("\n=== (b) Sheet 'Dataset' (mô tả) ===")
print("Merged cells:", re.findall(r'<mergeCell ref="([^"]+)"', desc_xml))
# (sửa lỗi bản đầu: regex cũ bỏ sót thuộc tính t="s" nên in ra index thay vì nội dung chuỗi)
cells = re.findall(r'<c r="([A-Z]+\d+)"([^>]*?)(?:/>|>(.*?)</c>)', desc_xml)
for ref, attrs, inner in cells:
    v = re.search(r"<v>(.*?)</v>", inner or "")
    if v:
        val = sst[int(v.group(1))] if 't="s"' in attrs else v.group(1)
        print(f"--- {ref} ---\n{val}\n")
b6 = [c for c in cells if c[0] == "B6"]
b6_has_value = bool(b6 and re.search(r"<v>", b6[0][2] or ""))
print(f"Ô B6 có giá trị? {b6_has_value}  "
      "(slide intro: B6 trống => randomization CHƯA được áp dụng)")
core = z.read("docProps/core.xml").decode()
print("docProps/core:", dict(re.findall(r"<(?:dc|cp|dcterms):(\w+)[^>]*>([^<]*)<", core)))

# ---------------------------------------------------------------- (c) macro / VBA (chỉ liệt kê)
from oletools.olevba import VBA_Parser  # noqa: E402

print("\n=== (c) Macro / VBA (chỉ đọc, KHÔNG chạy) ===")
vp = VBA_Parser(str(RAW_XLSM))
print("Có VBA macro?", vp.detect_vba_macros())
with open(TAB / "00_vba_source.txt", "w") as out:
    for (_, stream_path, vba_filename, code) in vp.extract_macros():
        n_lines = len([ln for ln in code.splitlines() if ln.strip()])
        print(f"  module: {vba_filename:<20} stream: {stream_path:<25} dòng code (không rỗng): {n_lines}")
        out.write(f"'==== {vba_filename} ({stream_path}) ====\n{code}\n")
kw = pd.DataFrame(vp.analyze_macros(), columns=["type", "keyword", "description"])
print(kw.to_string(index=False))
kw.to_csv(TAB / "00_vba_keywords.csv", index=False)
vp.close()

# ---------------------------------------------------------------- (d) quét XML sheet DATA
print("\n=== (d) Quét XML sheet DATA (stream theo khối) ===")
data_part = sheet_info.loc[sheet_info.sheet == DATA_SHEET, "xml_part"].item()
patterns = {"rows": b"<row ", "cells_shared_string": b't="s"', "cells_inline_string": b't="inlineStr"',
            "cells_formula_string": b't="str"', "cells_error": b't="e"', "cells_boolean": b't="b"',
            "formulas": b"<f", "hidden_rows": b'hidden="1"', "values": b"<v>"}
counts = dict.fromkeys(patterns, 0)
t0 = time.time()
tail = b""
with z.open(data_part) as f:
    while chunk := f.read(64 * 1024 * 1024):
        buf = tail + chunk
        for k, p in patterns.items():
            # chỉ đếm các lần xuất hiện KẾT THÚC trong phần mới (tránh đếm trùng ở vùng nối)
            counts[k] += buf.count(p) - tail.count(p)
        tail = buf[-32:]
print({k: f"{v:,}" for k, v in counts.items()}, f"({time.time() - t0:.0f}s)")
pd.Series(counts, name="count").to_csv(TAB / "00_data_xml_scan.csv")

# ---------------------------------------------------------------- (e) tốc độ đọc + parquet
print("\n=== (e) Tốc độ đọc ===")
N_BENCH = 50_000
t0 = time.time()
_ = read_raw_xlsm(engine="openpyxl", nrows=N_BENCH)
t_opx = time.time() - t0
print(f"openpyxl: {N_BENCH:,} dòng trong {t_opx:.1f}s -> ước tính ~{t_opx * 1_005_000 / N_BENCH / 60:.1f} phút cho toàn bộ")
t0 = time.time()
df = read_raw_xlsm(engine="calamine")
t_cal = time.time() - t0
print(f"calamine: {len(df):,} dòng x {df.shape[1]} cột trong {t_cal:.1f}s")

print("\nKiểu dữ liệu pandas ngay sau khi đọc + kiểu Python thực tế trong từng cột:")
type_rows = []
for c in df.columns:
    tc = df[c].map(lambda v: type(v).__name__).value_counts().to_dict()
    type_rows.append((c, str(df[c].dtype), tc))
    print(f"  {c:<18} {str(df[c].dtype):<10} {tc}")
pd.DataFrame(type_rows, columns=["column", "pandas_dtype", "python_types"]) \
    .to_csv(TAB / "00_read_dtypes.csv", index=False)

# Parquet trung gian: giữ nguyên giá trị như đọc được (chưa trim, chưa đổi nhãn, chưa xoá dòng).
t0 = time.time()
df.to_parquet(INTERIM, index=False)
INTERIM_SOURCE.write_text(source_signature())
print(f"\nĐã lưu {INTERIM.name} ({INTERIM.stat().st_size / 1e6:.1f} MB) trong {time.time() - t0:.1f}s")
t0 = time.time()
chk = pd.read_parquet(INTERIM)
print(f"Đọc lại parquet: {time.time() - t0:.1f}s; khớp với dữ liệu đọc từ xlsm: {chk.equals(df)}")
