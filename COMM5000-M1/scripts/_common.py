"""
_common.py — Hằng số và hàm dùng chung cho mọi script EDA (không phải một bước EDA).

Mục đích : Đường dẫn, seed, định nghĩa luxury, hàm load dữ liệu (ưu tiên parquet trung gian,
           nếu chưa có thì đọc thẳng file .xlsm gốc ở chế độ chỉ đọc).
Input    : [22_9] COMM5000-Used_Car_Price_Prediction.xlsm  hoặc  data_interim.parquet
Output   : không ghi file.
Nguyên tắc: KHÔNG ghi đè file gốc; mọi chuẩn hoá chỉ tạo bản copy trong bộ nhớ.
"""
from pathlib import Path
import os
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
# Có thể trỏ sang file khác (vd. bản đã randomize) mà không sửa code:
#   EDA_XLSM="/đường/dẫn/file.xlsm" python 00_load_and_inspect.py
RAW_XLSM = Path(os.environ.get("EDA_XLSM", ROOT / "[22_9] COMM5000-Used_Car_Price_Prediction.xlsm"))
INTERIM = ROOT / "data_interim.parquet"
INTERIM_SOURCE = ROOT / "data_interim.source.txt"   # ghi lại parquet được tạo từ file nào
FIG = ROOT / "figures"
TAB = ROOT / "tables"
FIG.mkdir(exist_ok=True)
TAB.mkdir(exist_ok=True)

DATA_SHEET = "DATA"
SEED = 5000                      # seed cố định cho mọi thao tác sampling
LUXURY_BRANDS = {"Audi", "BMW", "Mercedes"}   # theo Assessment Guide

TARGET = "Car_Price"
NUMERIC_COLS = ["Year", "Mileage_kmpl", "Engine_CC", "Horsepower", "Kms_Driven",
                "Accidents", "Number_of_Doors", "Seats", "Registration_Age", "Car_Price"]
BINARY_COLS = ["Insurance_Valid", "Service_History", "Tax_Paid"]
CATEGORICAL_COLS = ["Brand", "Model", "Fuel_Type", "Transmission", "Owner_Type", "Color", "City"]


def read_raw_xlsm(engine: str = "calamine", nrows=None) -> pd.DataFrame:
    """Đọc sheet DATA từ file gốc (read-only). Ô trống -> NaN. Không chạy macro."""
    return pd.read_excel(RAW_XLSM, sheet_name=DATA_SHEET, engine=engine, nrows=nrows)


def source_signature() -> str:
    st = RAW_XLSM.stat()
    return f"{RAW_XLSM.resolve()}|{st.st_size}|{int(st.st_mtime)}"


def load_raw() -> pd.DataFrame:
    """Dữ liệu thô (chưa làm sạch). Ưu tiên parquet trung gian do 00_load_and_inspect.py tạo,
    nhưng chỉ khi parquet đó được tạo từ đúng file nguồn hiện tại (so khớp đường dẫn/size/mtime)."""
    t0 = time.time()
    fresh = (INTERIM.exists() and INTERIM_SOURCE.exists()
             and INTERIM_SOURCE.read_text().strip() == source_signature())
    if fresh:
        df = pd.read_parquet(INTERIM)
        src = INTERIM.name
    else:
        print("[load_raw] parquet trung gian không có hoặc không khớp file nguồn -> đọc trực tiếp .xlsm")
        df = read_raw_xlsm()
        src = RAW_XLSM.name
    print(f"[load_raw] {len(df):,} dòng x {df.shape[1]} cột từ {src} ({time.time() - t0:.1f}s)")
    return df


# ----------------------------------------------------------------------------------------------
# Chuẩn hoá nhãn categorical — CHỈ tạo bản copy trong bộ nhớ để phân tích (không ghi ra file dữ liệu).
# Quy tắc (theo thứ tự):
#   R1 "unknown-token": nhãn sau khi strip + casefold thuộc UNKNOWN_TOKENS  -> "Unknown"
#   R2 "trim/case"    : gộp các nhãn trùng nhau sau strip + casefold; nhãn chuẩn = dạng viết phổ biến nhất
#   R3 "typo (fuzzy)" : nhóm hiếm (<1% cột) giống >= 0.8 (difflib) với một nhóm phổ biến -> gộp vào nhóm đó
# ----------------------------------------------------------------------------------------------
UNKNOWN_TOKENS = {"unknown", "unk", "n/a", "na", "nan", "none", "null", "-", "--", "?", ""}


def build_label_mapping(df: pd.DataFrame, cols=CATEGORICAL_COLS, rare_share=0.01,
                        fuzzy_cutoff=0.8) -> pd.DataFrame:
    import difflib
    out = []
    for c in cols:
        vc = df[c].value_counts(dropna=False)
        n_col = vc.sum()
        raw = pd.DataFrame({"raw": vc.index, "count": vc.values})
        raw["key"] = raw["raw"].map(lambda v: str(v).strip().casefold() if pd.notna(v) else "")
        key_tot = raw.groupby("key")["count"].sum().sort_values(ascending=False)
        # dạng viết phổ biến nhất (đã strip) của mỗi key
        canon = (raw.assign(stripped=raw["raw"].map(lambda v: str(v).strip()))
                 .sort_values("count", ascending=False).drop_duplicates("key")
                 .set_index("key")["stripped"])
        common_keys = [k for k, t in key_tot.items() if t / n_col >= rare_share and k not in UNKNOWN_TOKENS]
        for _, r in raw.iterrows():
            k = r["key"]
            if k in UNKNOWN_TOKENS:
                std, rule = "Unknown", "R1 unknown-token" if r["raw"] != "Unknown" else "giữ nguyên"
            else:
                std, rule = canon[k], "giữ nguyên"
                if key_tot[k] / n_col < rare_share:
                    m = difflib.get_close_matches(k, common_keys, n=1, cutoff=fuzzy_cutoff)
                    if m:
                        std, rule = canon[m[0]], "R3 typo (fuzzy)"
                if rule == "giữ nguyên" and r["raw"] != std:
                    rule = "R2 trim/case"
            out.append({"variable": c, "raw_label": r["raw"], "raw_label_repr": repr(r["raw"]),
                        "standard_label": std, "rule": rule, "count": int(r["count"])})
    return pd.DataFrame(out)


def analysis_view(df: pd.DataFrame, mapping: pd.DataFrame | None = None) -> pd.DataFrame:
    """Bản copy để phân tích: nhãn categorical đã chuẩn hoá (theo mapping ĐỀ XUẤT) + cột Segment
    + các cờ implausible_* (không xoá, không impute)."""
    v = df.copy()
    if mapping is None:
        mapping = build_label_mapping(df)
    for c, g in mapping.groupby("variable"):
        v[c] = v[c].map(dict(zip(g["raw_label"], g["standard_label"])))
    v["Segment"] = np.where(v["Brand"].isin(LUXURY_BRANDS), "Luxury", "Non-luxury")
    v = v.join(implausible_flags(df)).join(floor_flags(df))
    return v


def floor_values(df: pd.DataFrame, cols=("Car_Price", "Engine_CC", "Mileage_kmpl", "Kms_Driven"),
                 min_count=100) -> dict:
    """Phát hiện 'giá trị sàn': giá trị MIN của cột lặp lại >= min_count lần (point mass ở biên trái),
    dấu hiệu dữ liệu bị chặn (censoring/clipping). Trả về {cột: giá trị sàn}."""
    out = {}
    for c in cols:
        m = df[c].min()
        if (df[c] == m).sum() >= min_count:
            out[c] = m
    return out


def floor_flags(df: pd.DataFrame) -> pd.DataFrame:
    f = pd.DataFrame(index=df.index)
    for c, m in floor_values(df).items():
        f[f"floor_{c}"] = df[c] == m
    return f


# ----------------------------------------------------------------------------------------------
# Cờ giá trị phi lý (implausible) — chỉ dựa trên logic nội tại của dữ liệu hoặc ví dụ trong
# Assessment Guide (Kms_Driven > 1,000,000). Chỉ GẮN CỜ, không xoá.
# ----------------------------------------------------------------------------------------------
REF_YEAR = 2025   # GIẢ ĐỊNH: Year + Registration_Age = 2025 ở mọi dòng (kiểm chứng trong 02)
KMS_IMPLAUSIBLE = 1_000_000
# Biên trên km/năm của phần thân dữ liệu: 99.04% dòng có Kms_Driven / Registration_Age trong [5,000; 25,000);
# nhóm vượt biên có Car_Price cao ~4.8 lần xe cùng Model & tuổi (kiểm chứng trong 04). Chỉ đúng với file
# CHƯA randomize (macro sinh lại Kms_Driven độc lập với tuổi xe).
KMS_PER_YEAR_MAX = 25_000


def implausible_flags(df: pd.DataFrame) -> pd.DataFrame:
    f = pd.DataFrame(index=df.index)
    f["imp_price_nonpos"] = df["Car_Price"] <= 0
    f["imp_kms_gt_1m"] = df["Kms_Driven"] > KMS_IMPLAUSIBLE
    f["imp_kms_per_year_gt_25k"] = df["Kms_Driven"] / df["Registration_Age"] > KMS_PER_YEAR_MAX
    f["imp_kms_nonpos"] = df["Kms_Driven"] <= 0
    f["imp_hp_nonpos"] = df["Horsepower"] <= 0
    f["imp_engine_nonpos"] = df["Engine_CC"] <= 0
    f["imp_mileage_nonpos"] = df["Mileage_kmpl"] <= 0
    f["imp_year_age_mismatch"] = (df["Year"] + df["Registration_Age"]) != REF_YEAR
    f["imp_any"] = f.any(axis=1)
    return f


# ----------------------------------------------------------------------------------------------
# Style biểu đồ (PNG tĩnh, nền sáng). Bảng màu categorical đã kiểm tra CVD bằng validator
# (3 slot đầu: blue, orange, aqua — PASS). Mỗi hình có bảng số liệu tương ứng trong tables/.
# ----------------------------------------------------------------------------------------------
SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"          # slot 1 blue, slot 2 orange, slot 3 aqua
SEG_COLORS = {"Non-luxury": C1, "Luxury": C2}
HIGHLIGHT_GREY = "#c3c2b7"                            # nhóm được làm mờ (vd. 'Unknown')
SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def setup_plot():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.labelsize": 9.5, "text.color": INK, "axes.labelcolor": INK2,
        "axes.edgecolor": AXIS, "axes.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "grid.linestyle": "-",
        "axes.axisbelow": True, "xtick.color": MUTED, "ytick.color": MUTED,
        "xtick.labelcolor": INK2, "ytick.labelcolor": INK2, "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
        "lines.linewidth": 2, "lines.solid_capstyle": "round", "legend.frameon": False, "legend.fontsize": 9,
        "figure.dpi": 110, "savefig.dpi": 150, "savefig.bbox": "tight",
    })
    return plt


def diverging_cmap():
    from matplotlib.colors import LinearSegmentedColormap
    # red (âm) <-> xám trung tính <-> blue (dương)
    return LinearSegmentedColormap.from_list(
        "div", ["#a8302f", "#e34948", "#f3b3b2", "#f0efec", "#9ec5f4", "#2a78d6", "#184f95"])


def thousands(ax, axis="y"):
    from matplotlib.ticker import FuncFormatter
    f = FuncFormatter(lambda x, _: f"{x:,.0f}")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(f)


def fmt_int(x) -> str:
    return f"{int(x):,}"


def pct(n, d) -> float:
    return round(100.0 * n / d, 3) if d else np.nan
