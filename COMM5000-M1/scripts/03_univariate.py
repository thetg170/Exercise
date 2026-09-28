"""
03_univariate.py — Mục 4 EDA: phân tích từng biến (univariate).

Mục đích :
  - Numeric: count, missing, mean, median, mode (+ tần suất), std, min, Q1, Q3, max, IQR, skewness,
    kurtosis (excess) — trên TOÀN BỘ dữ liệu thô (chưa loại duplicate/implausible; xem 08 cho so sánh).
  - Bảng theo mẫu Assessment Guide (Mean, Mode, Median, SD, Min, Max) cho 3 nhóm: Entire / Luxury /
    Non-luxury. Segment dựa trên Brand đã chuẩn hoá TRONG BỘ NHỚ (mapping đề xuất ở 02).
  - Categorical: tần suất & %, số nhóm, nhóm hiếm (<1%) — cả nhãn gốc lẫn nhãn chuẩn hoá.
  - Biểu đồ: histogram + boxplot (continuous), bar (discrete & categorical), nhãn gốc bị lỗi.
Input    : data_interim.parquet
Output   : tables/03*.csv; figures/fig_03a..fig_03e*.png
Bước EDA : Mục 4 — univariate. (Không sampling: mọi hình dùng toàn bộ 1,005,000 dòng.)
"""
import pandas as pd
from matplotlib.ticker import MaxNLocator

from _common import (load_raw, analysis_view, TAB, FIG, NUMERIC_COLS, BINARY_COLS, CATEGORICAL_COLS,
                     setup_plot, thousands, C1, C2, INK, INK2, HIGHLIGHT_GREY, pct)

plt = setup_plot()
raw = load_raw()
v = analysis_view(raw)
N = len(v)


def describe_num(s: pd.Series) -> dict:
    n_miss = int(s.isna().sum())
    s = s.dropna()
    q1, med, q3 = s.quantile([0.25, 0.5, 0.75])
    mode = s.mode().iloc[0]
    mode_n = int((s == mode).sum())
    return {"count": len(s), "missing": n_miss, "mean": s.mean(), "median": med, "mode": mode,
            "mode_freq": mode_n, "mode_pct": pct(mode_n, len(s)), "std": s.std(), "min": s.min(),
            "Q1": q1, "Q3": q3, "max": s.max(), "IQR": q3 - q1, "skewness": s.skew(),
            "kurtosis_excess": s.kurt(), "mean_minus_median": s.mean() - med}


# ---------------------------------------------------------------- numeric: toàn bộ
num_cols = NUMERIC_COLS + BINARY_COLS
stats = pd.DataFrame({c: describe_num(v[c]) for c in num_cols}).T
stats.to_csv(TAB / "03a_numeric_descriptives.csv")
with pd.option_context("display.float_format", lambda x: f"{x:,.3f}", "display.width", 250):
    print("=== Numeric descriptives (toàn bộ, dữ liệu thô) ===")
    print(stats.to_string())

# ---------------------------------------------------------------- bảng theo mẫu Guide x 3 nhóm
guide_cols = ["mean", "mode", "median", "std", "min", "max"]
groups = {"Entire": v, "Luxury": v[v.Segment == "Luxury"], "Non-luxury": v[v.Segment == "Non-luxury"]}
long = []
for g, d in groups.items():
    t = pd.DataFrame({c: describe_num(d[c]) for c in num_cols}).T[["count"] + guide_cols]
    t.insert(0, "group", g)
    long.append(t)
    print(f"\n=== Bảng Guide — {g} (n = {len(d):,}) ===")
    with pd.option_context("display.float_format", lambda x: f"{x:,.2f}", "display.width", 250):
        print(t.drop(columns="group").to_string())
pd.concat(long).rename_axis("variable").to_csv(TAB / "03b_guide_table_by_segment.csv")

# ---------------------------------------------------------------- categorical
print("\n=== Categorical (nhãn chuẩn hoá trong bộ nhớ) ===")
rows = []
for c in CATEGORICAL_COLS + ["Segment"]:
    vc = v[c].value_counts()
    rare = vc[vc / N < 0.01]
    print(f"{c:<12} {len(vc):>2} nhóm | lớn nhất {vc.index[0]!s} {pct(vc.iloc[0], N)}% | "
          f"nhỏ nhất {vc.index[-1]!s} {pct(vc.iloc[-1], N)}% | nhóm hiếm (<1%): {list(rare.index) or 'không'}")
    rows += [(c, "standardised", lab, k, pct(k, N), k / N < 0.01) for lab, k in vc.items()]
print("\n=== Categorical (nhãn GỐC) — nhóm hiếm (<1%) ===")
for c in CATEGORICAL_COLS:
    vc = raw[c].value_counts()
    rare = vc[vc / N < 0.01]
    print(f"{c:<12} {len(vc):>2} nhãn gốc, {len(rare)} nhãn hiếm: "
          + (", ".join(f"{k!r}" for k in rare.index) if len(rare) else "không"))
    rows += [(c, "raw", repr(lab), k, pct(k, N), k / N < 0.01) for lab, k in vc.items()]
pd.DataFrame(rows, columns=["variable", "labels", "label", "count", "pct", "rare_lt_1pct"]) \
    .to_csv(TAB / "03c_categorical_frequencies.csv", index=False)

# ---------------------------------------------------------------- hình 03a: continuous
cont = ["Mileage_kmpl", "Engine_CC", "Horsepower", "Kms_Driven", "Car_Price"]
fig, axes = plt.subplots(len(cont), 2, figsize=(11, 13), gridspec_kw={"width_ratios": [2.2, 1]})
for i, c in enumerate(cont):
    s = v[c].dropna()
    ax = axes[i, 0]
    # (chỉnh sau lần chạy đầu: đuôi phải rất dài làm nén histogram -> với biến skew > 1, trục x cắt ở P99.9;
    #  boxplot bên phải vẫn hiển thị TOÀN BỘ giá trị)
    hi = s.quantile(0.999) if s.skew() > 1 else s.max()
    ax.hist(s[s <= hi], bins=120, range=(s.min(), hi), color=C1, linewidth=0)
    ax.axvline(s.mean(), color=C2, linewidth=1.5, label=f"mean = {s.mean():,.1f}")
    ax.axvline(s.median(), color=INK, linewidth=1.5, label=f"median = {s.median():,.1f}")
    cut = f"; trục x cắt ở P99.9 = {hi:,.0f}, ẩn {(s > hi).sum():,} dòng" if hi < s.max() else ""
    ax.set_title(f"{c}  (n = {len(s):,}; skew = {s.skew():.2f}{cut})")
    ax.set_ylabel("Số listing")
    thousands(ax)
    if s.max() > 10_000:
        thousands(ax, "x")
    ax.legend(loc="upper right")
    ax = axes[i, 1]
    ax.boxplot(s, orientation="horizontal", widths=0.45, patch_artist=True,
               boxprops=dict(facecolor="#cde2fb", edgecolor=C1), medianprops=dict(color=INK, linewidth=1.5),
               whiskerprops=dict(color=C1), capprops=dict(color=C1),
               flierprops=dict(marker="o", markersize=2, markerfacecolor=C1, markeredgecolor="none", alpha=0.3))
    ax.set_yticks([])
    ax.set_title("Boxplot (1.5×IQR)")
    if s.max() > 10_000:
        thousands(ax, "x")
fig.suptitle("Phân phối các biến continuous (toàn bộ 1,005,000 dòng, dữ liệu thô)", x=0.01, ha="left",
             fontsize=12, fontweight="bold")
fig.tight_layout()
fig.savefig(FIG / "fig_03a_continuous_hist_box.png")
plt.close(fig)

# ---------------------------------------------------------------- hình 03b: discrete & binary
disc = ["Year", "Registration_Age", "Accidents", "Number_of_Doors", "Seats"] + BINARY_COLS
fig, axes = plt.subplots(2, 4, figsize=(13, 6.2))
for ax, c in zip(axes.flat, disc):
    vc = v[c].value_counts().sort_index()
    ax.bar(vc.index.astype(str), vc.values, color=C1, width=0.7)
    ax.set_title(c)
    thousands(ax)
    ax.grid(axis="x", visible=False)
    if len(vc) > 10:
        ax.set_xticks(range(0, len(vc), 4))
        ax.set_xticklabels(vc.index.astype(str)[::4])
    else:
        for x, y in zip(vc.index.astype(str), vc.values):
            ax.annotate(f"{100 * y / N:.1f}%", (x, y), ha="center", va="bottom", fontsize=8, color=INK2,
                        xytext=(0, 2), textcoords="offset points")
fig.suptitle("Biến rời rạc & nhị phân — số listing theo giá trị", x=0.01, ha="left", fontsize=12,
             fontweight="bold")
fig.tight_layout()
fig.savefig(FIG / "fig_03b_discrete_bars.png")
plt.close(fig)

# ---------------------------------------------------------------- hình 03c: categorical (chuẩn hoá)
cats = ["Brand", "Fuel_Type", "Transmission", "Owner_Type", "Color", "City"]
order = {"Owner_Type": ["First", "Second", "Third", "Fourth+"]}
fig, axes = plt.subplots(2, 3, figsize=(13, 8))
for ax, c in zip(axes.flat, cats):
    vc = v[c].value_counts()
    if c in order:
        vc = vc.reindex(order[c])
    vc = vc.iloc[::-1]
    colors = [HIGHLIGHT_GREY if lab == "Unknown" else C1 for lab in vc.index]
    ax.barh(vc.index, vc.values, color=colors, height=0.6)
    for y, val in enumerate(vc.values):
        ax.annotate(f"{100 * val / N:.1f}%", (val, y), va="center", fontsize=7.5, color=INK2,
                    xytext=(3, 0), textcoords="offset points")
    ax.set_title(f"{c} ({len(vc)} nhóm)")
    ax.xaxis.set_major_locator(MaxNLocator(4))
    thousands(ax, "x")
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, vc.max() * 1.18)
fig.suptitle("Biến categorical — nhãn đã chuẩn hoá trong bộ nhớ (xám = 'Unknown')", x=0.01, ha="left",
             fontsize=12, fontweight="bold")
fig.tight_layout()
fig.savefig(FIG / "fig_03c_categorical_bars.png")
plt.close(fig)

# ---------------------------------------------------------------- hình 03d: Model
vc = v["Model"].value_counts().iloc[::-1]
fig, ax = plt.subplots(figsize=(8, 9))
ax.barh(vc.index, vc.values, color=C1, height=0.6)
ax.set_title(f"Model — {len(vc)} nhóm, mỗi nhóm {100 * vc.min() / N:.2f}%–{100 * vc.max() / N:.2f}% số listing")
thousands(ax, "x")
ax.grid(axis="y", visible=False)
fig.tight_layout()
fig.savefig(FIG / "fig_03d_model_bars.png")
plt.close(fig)

# ---------------------------------------------------------------- hình 03e: nhãn gốc lỗi
fig, axes = plt.subplots(1, 2, figsize=(13, 6))
for ax, c in zip(axes, ["Fuel_Type", "Brand"]):
    vc = raw[c].value_counts().iloc[::-1]
    std_labels = set(v[c].unique())
    colors = [C1 if lab in std_labels else C2 for lab in vc.index]
    ax.barh([repr(x) for x in vc.index], vc.values, color=colors, height=0.6)
    ax.set_xscale("log")
    ax.set_title(f"{c}: {len(vc)} nhãn gốc -> {len(std_labels)} nhãn chuẩn")
    ax.set_xlabel("Số listing (thang log)")
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", labelsize=8)
from matplotlib.patches import Patch  # noqa: E402
axes[1].legend(handles=[Patch(color=C1, label="Nhãn chuẩn"), Patch(color=C2, label="Biến thể lỗi (khoảng trắng/hoa-thường/typo)")],
               loc="lower right")
fig.suptitle("Nhãn gốc không thống nhất (repr() để thấy khoảng trắng)", x=0.01, ha="left", fontsize=12,
             fontweight="bold")
fig.tight_layout()
fig.savefig(FIG / "fig_03e_raw_label_variants.png")
plt.close(fig)
print("\nĐã lưu hình: fig_03a..fig_03e")
