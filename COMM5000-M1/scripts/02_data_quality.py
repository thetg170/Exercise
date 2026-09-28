"""
02_data_quality.py — Mục 3 EDA: kiểm tra chất lượng dữ liệu (chỉ PHÁT HIỆN + ĐỊNH LƯỢNG, không sửa).

Mục đích :
  A. Missing values (NaN thật): số lượng, %, dạng đồng thời (pattern), có tập trung theo nhóm không.
  B. 'Unknown' và các biến thể (N/A, '-', '', chuỗi toàn khoảng trắng...) — đếm riêng, tách khỏi NaN;
     số 0 / số âm vô nghĩa trong biến numeric.
  C. Inconsistent category labels -> bảng mapping ĐỀ XUẤT (nhãn gốc -> nhãn chuẩn -> số dòng);
     tác động tới việc gán Luxury (Audi/BMW/Mercedes).
  D. Tính nhất quán Model–Brand (mỗi Model thuộc đúng 1 Brand?).
  E. Duplicated records: exact duplicates và near-duplicates.
  F. Kiểu dữ liệu & tính nhất quán nội tại: tập giá trị biến nhị phân, Year + Registration_Age,
     "point mass" (giá trị lặp bất thường, thường ở min/max -> dấu hiệu bị chặn/clipping).
Input    : data_interim.parquet
Output   : tables/02_*.csv
Bước EDA : Mục 3 — kiểm tra chất lượng dữ liệu.
"""
import numpy as np
import pandas as pd

from _common import (load_raw, TAB, CATEGORICAL_COLS, NUMERIC_COLS, BINARY_COLS, LUXURY_BRANDS,
                     UNKNOWN_TOKENS, build_label_mapping, pct)

df = load_raw()
N = len(df)
mapping = build_label_mapping(df)
# nhãn đã chuẩn hoá (copy trong bộ nhớ) — chỉ dùng để nhóm khi kiểm tra
std = df.copy()
for c, g in mapping.groupby("variable"):
    std[c] = std[c].map(dict(zip(g["raw_label"], g["standard_label"])))
std["Segment"] = np.where(std["Brand"].isin(LUXURY_BRANDS), "Luxury", "Non-luxury")

# =================================================================== A. Missing (NaN)
print("=== A. Missing values (NaN thật) ===")
miss = pd.DataFrame({"n_missing": df.isna().sum(), "pct_missing": (100 * df.isna().mean()).round(3)})
print(miss[miss.n_missing > 0].to_string())
print(f"Tổng ô trống: {int(df.isna().sum().sum()):,} / {df.size:,} ô ({pct(df.isna().sum().sum(), df.size)}%)")
miss.to_csv(TAB / "02a_missing_by_column.csv")

miss_cols = miss.index[miss.n_missing > 0].tolist()
any_miss = df[miss_cols].isna().any(axis=1)
n_miss_per_row = df[miss_cols].isna().sum(axis=1)
print(f"Số dòng có >=1 NaN: {any_miss.sum():,} ({pct(any_miss.sum(), N)}%)")
print("Phân bố số NaN / dòng:", n_miss_per_row.value_counts().sort_index().to_dict())
pattern = df[miss_cols].isna().value_counts().rename("n_rows").reset_index()
print("Mẫu hình missing (True = thiếu):\n", pattern.to_string(index=False))
pattern.to_csv(TAB / "02a_missing_patterns.csv", index=False)

# Missing có tập trung theo nhóm không? (% missing theo nhóm; so sánh min–max giữa các nhóm)
rows = []
for gcol in ["City", "Brand", "Segment", "Year", "Fuel_Type", "Transmission", "Owner_Type"]:
    for mc in miss_cols:
        r = std[mc].isna().groupby(std[gcol]).mean() * 100
        rows.append({"group_var": gcol, "missing_col": mc, "overall_pct": round(100 * df[mc].isna().mean(), 3),
                     "min_group_pct": round(r.min(), 3), "min_group": r.idxmin(),
                     "max_group_pct": round(r.max(), 3), "max_group": r.idxmax(),
                     "range_pp": round(r.max() - r.min(), 3)})
conc = pd.DataFrame(rows)
print("\n% missing theo nhóm (range_pp = chênh lệch max–min, điểm %):")
print(conc.to_string(index=False))
conc.to_csv(TAB / "02a_missing_by_group.csv", index=False)

# Car_Price có khác nhau giữa dòng thiếu và không thiếu? (dấu hiệu missing không ngẫu nhiên)
print("\nMedian Car_Price theo trạng thái missing:")
for mc in miss_cols:
    m = df.groupby(df[mc].isna())["Car_Price"].agg(["count", "median", "mean"])
    print(f"  {mc:<13} thiếu: n={m.loc[True, 'count']:,} median={m.loc[True, 'median']:,.0f} | "
          f"không thiếu: n={m.loc[False, 'count']:,} median={m.loc[False, 'median']:,.0f}")

# =================================================================== B. Unknown & biến thể
print("\n=== B. 'Unknown' và các biến thể (tách khỏi NaN) ===")
rows = []
for c in CATEGORICAL_COLS:
    s = df[c]
    stripped = s.str.strip()
    key = stripped.str.casefold()
    rows.append({
        "variable": c,
        "NaN": int(s.isna().sum()),
        "exact_'Unknown'": int((s == "Unknown").sum()),
        "unknown_variants_other_case_or_space": int((key == "unknown").sum() - (s == "Unknown").sum()),
        "other_tokens(N/A,-,?,none,null)": int(key.isin(UNKNOWN_TOKENS - {"unknown", ""}).sum()),
        "empty_or_whitespace_only": int((stripped == "").sum()),
        "has_leading_trailing_space": int((s != stripped).sum()),
    })
unk = pd.DataFrame(rows)
unk["pct_unknown_total"] = ((unk["exact_'Unknown'"] + unk.iloc[:, 3:6].sum(axis=1)) / N * 100).round(3)
print(unk.to_string(index=False))
unk.to_csv(TAB / "02b_unknown_by_column.csv", index=False)

unk_cols = unk.loc[unk["exact_'Unknown'"] > 0, "variable"].tolist()
is_unk = df[unk_cols] == "Unknown"
print(f"\nSố dòng có >=1 'Unknown' (trong {unk_cols}): {is_unk.any(axis=1).sum():,} "
      f"({pct(is_unk.any(axis=1).sum(), N)}%)")
print("Phân bố số 'Unknown' / dòng:", is_unk.sum(axis=1).value_counts().sort_index().to_dict())
bad_any = is_unk.any(axis=1) | any_miss
print(f"Số dòng có >=1 NaN HOẶC >=1 'Unknown': {bad_any.sum():,} ({pct(bad_any.sum(), N)}%) "
      f"-> nếu xoá toàn bộ (listwise deletion) chỉ còn {N - bad_any.sum():,} dòng")

print("\n% 'Unknown' theo nhóm (range_pp = chênh lệch max–min):")
rows = []
for gcol in ["City", "Brand", "Segment", "Year"]:
    for uc in unk_cols:
        if uc == gcol:
            continue
        r = (std[uc] == "Unknown").groupby(std[gcol]).mean() * 100
        rows.append({"group_var": gcol, "unknown_col": uc, "min_group_pct": round(r.min(), 3),
                     "max_group_pct": round(r.max(), 3), "range_pp": round(r.max() - r.min(), 3)})
unk_conc = pd.DataFrame(rows)
print(unk_conc.to_string(index=False))
unk_conc.to_csv(TAB / "02b_unknown_by_group.csv", index=False)

print("\nSố 0 / số âm trong biến numeric (giá trị vô nghĩa nếu biến phải > 0):")
rows = []
for c in NUMERIC_COLS:
    s = df[c]
    rows.append({"variable": c, "n_zero": int((s == 0).sum()), "n_negative": int((s < 0).sum()),
                 "min": s.min(), "max": s.max()})
zn = pd.DataFrame(rows)
print(zn.to_string(index=False))
zn.to_csv(TAB / "02b_zero_negative_numeric.csv", index=False)

# =================================================================== C. Inconsistent labels
print("\n=== C. Inconsistent category labels — bảng mapping ĐỀ XUẤT ===")
changes = mapping[mapping["rule"] != "giữ nguyên"]
print(changes[["variable", "raw_label_repr", "standard_label", "rule", "count"]].to_string(index=False))
mapping.to_csv(TAB / "02c_label_mapping_proposed.csv", index=False)
summ = (mapping.assign(changed=mapping["rule"] != "giữ nguyên")
        .groupby("variable").agg(n_raw_labels=("raw_label", "size"),
                                 n_standard_labels=("standard_label", "nunique"),
                                 rows_affected=("count", lambda x: int(x[mapping.loc[x.index, "rule"] != "giữ nguyên"].sum()))))
summ["pct_rows_affected"] = (100 * summ["rows_affected"] / N).round(3)
print("\nTóm tắt theo cột:\n", summ.to_string())
summ.to_csv(TAB / "02c_label_summary.csv")

lux_raw = df["Brand"].isin(LUXURY_BRANDS).sum()
lux_std = std["Brand"].isin(LUXURY_BRANDS).sum()
print(f"\nTác động tới Segment: Luxury theo nhãn gốc = {lux_raw:,} ({pct(lux_raw, N)}%); "
      f"sau chuẩn hoá = {lux_std:,} ({pct(lux_std, N)}%); "
      f"=> {lux_std - lux_raw:,} dòng luxury sẽ bị xếp nhầm vào Non-luxury nếu không TRIM Brand")
lux_detail = mapping[(mapping.variable == "Brand") & mapping.standard_label.isin(LUXURY_BRANDS)]
print(lux_detail[["raw_label_repr", "standard_label", "count"]].to_string(index=False))

# =================================================================== D. Model–Brand
print("\n=== D. Nhất quán Model–Brand ===")
mb = std.groupby("Model")["Brand"].nunique()
print(f"Số Model: {len(mb)}; Model gắn với >1 Brand: {(mb > 1).sum()}")
bm = std.groupby("Brand")["Model"].unique().map(sorted)
for b, ms in bm.items():
    print(f"  {b:<11} -> {ms}")
bm.to_frame("models").to_csv(TAB / "02d_brand_models.csv")

# =================================================================== E. Duplicates
print("\n=== E. Duplicated records ===")
cont = ["Mileage_kmpl", "Engine_CC", "Horsepower", "Kms_Driven", "Car_Price"]
defs = {
    "E1 exact (20 cột, nhãn gốc)": (df, list(df.columns)),
    "E2 sau chuẩn hoá nhãn (20 cột)": (std, list(df.columns)),
    "E3 trùng mọi cột trừ Car_Price (nhãn chuẩn)": (std, [c for c in df.columns if c != "Car_Price"]),
    "E4 chỉ trùng 5 biến continuous": (df, cont),
}
rows = []
for name, (d, cols) in defs.items():
    dup_all = d.duplicated(subset=cols, keep=False)
    dup_extra = d.duplicated(subset=cols, keep="first")
    rows.append({"definition": name, "rows_in_dup_groups": int(dup_all.sum()),
                 "extra_copies(would_drop)": int(dup_extra.sum()), "pct_extra": pct(dup_extra.sum(), N)})
dups = pd.DataFrame(rows)
print(dups.to_string(index=False))
dups.to_csv(TAB / "02e_duplicates.csv", index=False)

d1 = df.duplicated(keep=False)
grp_sizes = df[d1].groupby(list(df.columns), dropna=False).size()
print("Kích thước nhóm trùng (E1):", grp_sizes.value_counts().sort_index().to_dict())
print("Ví dụ exact duplicates (E1), 3 cặp đầu, kèm số dòng Excel (= index + 2):")
ex = df[d1].copy()
ex.insert(0, "excel_row", ex.index + 2)
ex = ex.sort_values(list(df.columns)).head(6)
with pd.option_context("display.width", 250, "display.max_columns", 30):
    print(ex.to_string(index=False))
ex.to_csv(TAB / "02e_duplicate_examples.csv", index=False)

# near-duplicates E3 nhưng không phải E1/E2 -> cùng xe, giá khác?
e3 = std.duplicated(subset=[c for c in df.columns if c != "Car_Price"], keep=False) & \
     ~std.duplicated(keep=False)
print(f"Near-dup E3 mà KHÔNG phải trùng hoàn toàn: {e3.sum():,} dòng")
e2_only = std.duplicated(keep=False) & ~d1
print(f"Near-dup E2 (chỉ trùng sau chuẩn hoá nhãn, không trùng nhãn gốc): {e2_only.sum():,} dòng")
if e2_only.any():
    ex2 = df[e2_only].copy()
    ex2.insert(0, "excel_row", ex2.index + 2)
    print(ex2.sort_values(["Car_Price"]).head(4).to_string(index=False))

# vị trí các dòng trùng: rải rác hay nằm cuối file?
pos = df.index[df.duplicated(keep="first")]
print(f"Vị trí (dòng Excel) của bản sao thừa E1: min={pos.min() + 2:,}, median={int(np.median(pos)) + 2:,}, "
      f"max={pos.max() + 2:,}; % nằm sau dòng 1,000,001: {pct((pos + 2 > 1_000_001).sum(), len(pos))}%")

# =================================================================== F. Kiểu dữ liệu & nhất quán nội tại
print("\n=== F. Kiểu dữ liệu & nhất quán nội tại ===")
print("Kiểu lưu trữ (từ 00): mọi ô numeric là số, mọi ô categorical là chuỗi; không có số lưu dạng text,"
      " không có công thức, không có ô lỗi.")
for c in BINARY_COLS:
    print(f"  {c}: tập giá trị = {sorted(df[c].unique())}")
ya = df["Year"] + df["Registration_Age"]
print("Year + Registration_Age:", ya.value_counts().to_dict())
print(f"  -> {'nhất quán ở 100% dòng' if ya.nunique() == 1 else 'KHÔNG nhất quán'}; "
      f"GIẢ ĐỊNH năm tham chiếu (năm listing/thu thập) = {int(ya.mode()[0])}")
print(f"  Year max = {df['Year'].max()} -> số dòng Year > năm tham chiếu: {(df['Year'] > ya.mode()[0]).sum():,}")

print("\n'Point mass' — 5 giá trị lặp nhiều nhất của biến continuous:")
rows = []
for c in cont:
    vc = df[c].value_counts().head(5)
    for v, k in vc.items():
        rows.append({"variable": c, "value": v, "count": int(k), "pct": pct(k, N),
                     "is_min": v == df[c].min(), "is_max": v == df[c].max()})
pm = pd.DataFrame(rows)
print(pm.to_string(index=False))
pm.to_csv(TAB / "02f_point_masses.csv", index=False)
