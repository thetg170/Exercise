"""
05_bivariate.py — Mục 6 EDA: quan hệ giữa các biến.

Mục đích :
  - Correlation matrix Pearson & Spearman (pairwise, bỏ NaN) cho biến numeric + nhị phân; heatmap.
  - Độ nhạy: correlation của Car_Price với từng biến khi (i) toàn bộ, (ii) bỏ dòng implausible,
    (iii) bỏ thêm dòng Car_Price = giá sàn.
  - Scatter Car_Price vs biến numeric quan trọng trên SAMPLE ngẫu nhiên n = 5,000 (seed = 5000),
    tô màu theo Segment; kèm đường mean/median theo nhóm tính trên TOÀN BỘ dữ liệu.
  - Crosstab giữa biến categorical quan trọng (row %).
  - Cảnh báo multicollinearity (|r| >= 0.7 giữa các biến giải thích).
Input    : data_interim.parquet
Output   : tables/05*.csv; figures/fig_05a_corr_heatmaps.png, fig_05b_scatter_sample.png,
           fig_05c_group_means_age_kms.png, fig_05d_composition_by_segment.png
Bước EDA : Mục 6 — bivariate / multivariate mô tả (chưa chạy mô hình).
"""
import numpy as np
import pandas as pd

from _common import (load_raw, analysis_view, TAB, FIG, SEED, SEG_COLORS, setup_plot, thousands,
                     diverging_cmap, C1, C2, INK, INK2, pct)

plt = setup_plot()
raw = load_raw()
v = analysis_view(raw)
N = len(v)

num = ["Car_Price", "Registration_Age", "Year", "Kms_Driven", "Mileage_kmpl", "Engine_CC", "Horsepower",
       "Accidents", "Number_of_Doors", "Seats", "Insurance_Valid", "Service_History", "Tax_Paid"]
d = v[num].copy()
d.insert(1, "log_Car_Price", np.log(v["Car_Price"]))

# ---------------------------------------------------------------- correlation matrices
pear = d.corr("pearson")
spear = d.corr("spearman")
pear.to_csv(TAB / "05a_corr_pearson.csv")
spear.to_csv(TAB / "05a_corr_spearman.csv")
with pd.option_context("display.float_format", lambda x: f"{x:6.3f}", "display.width", 250):
    print("=== Pearson (toàn bộ dữ liệu, pairwise) ===")
    print(pear.to_string())
    print("\n=== Spearman ===")
    print(spear.to_string())

# ---------------------------------------------------------------- multicollinearity
print("\n=== Cặp biến giải thích có |r| >= 0.3 (Pearson hoặc Spearman) ===")
X = [c for c in d.columns if c not in ("Car_Price", "log_Car_Price")]
rows = []
for i, a in enumerate(X):
    for b in X[i + 1:]:
        rp, rs = pear.loc[a, b], spear.loc[a, b]
        if max(abs(rp), abs(rs)) >= 0.3:
            rows.append({"var_1": a, "var_2": b, "pearson": round(rp, 4), "spearman": round(rs, 4),
                         "flag": "MULTICOLLINEARITY (|r|>=0.7)" if max(abs(rp), abs(rs)) >= 0.7 else "trung bình"})
mc = pd.DataFrame(rows).sort_values("pearson", key=abs, ascending=False)
print(mc.to_string(index=False))
mc.to_csv(TAB / "05b_multicollinearity_pairs.csv", index=False)
others = [(a, b) for i, a in enumerate(X) for b in X[i + 1:]
          if max(abs(pear.loc[a, b]), abs(spear.loc[a, b])) < 0.3]
mx = max(max(abs(pear.loc[a, b]), abs(spear.loc[a, b])) for a, b in others)
print(f"Các cặp còn lại ({len(others)} cặp): |r| lớn nhất = {mx:.4f}")

# ---------------------------------------------------------------- độ nhạy correlation với Car_Price
print("\n=== Correlation với Car_Price: toàn bộ vs bỏ implausible vs bỏ thêm giá sàn ===")
views = {"all": v, "excl_implausible": v[~v.imp_any],
         "excl_implausible_and_floor": v[~v.imp_any & ~v.floor_Car_Price]}
rows = []
for name, dv in views.items():
    for c in X:
        rows.append({"view": name, "n": len(dv), "variable": c,
                     "pearson_price": dv["Car_Price"].corr(dv[c]),
                     "spearman_price": dv["Car_Price"].corr(dv[c], method="spearman"),
                     "pearson_logprice": np.log(dv["Car_Price"]).corr(dv[c])})
sens = pd.DataFrame(rows)
sens.to_csv(TAB / "05c_price_corr_sensitivity.csv", index=False)
wide = sens.pivot(index="variable", columns="view", values=["pearson_price", "spearman_price"]).round(3)
print(wide.reindex(X).to_string())

# ---------------------------------------------------------------- hình 05a: heatmaps
fig, axes = plt.subplots(1, 2, figsize=(16, 7.2))
cmap = diverging_cmap()
for ax, (name, m) in zip(axes, [("Pearson", pear), ("Spearman", spear)]):
    im = ax.imshow(m.values, cmap=cmap, vmin=-1, vmax=1)
    ax.set_xticks(range(len(m)))
    ax.set_xticklabels(m.columns, rotation=60, ha="right", fontsize=8)
    ax.set_yticks(range(len(m)))
    ax.set_yticklabels(m.index, fontsize=8)
    ax.grid(False)
    for i in range(len(m)):
        for j in range(len(m)):
            val = m.values[i, j]
            if abs(val) >= 0.05 and i != j:
                ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=6.5,
                        color="white" if abs(val) > 0.6 else INK)
    ax.set_title(f"{name} correlation (toàn bộ dữ liệu; chỉ ghi số khi |r| >= 0.05)")
fig.colorbar(im, ax=axes, shrink=0.7, label="r")
fig.savefig(FIG / "fig_05a_corr_heatmaps.png")
plt.close(fig)

# ---------------------------------------------------------------- hình 05b: scatter trên sample
N_SAMPLE = 5_000
s = v.sample(n=N_SAMPLE, random_state=SEED)
print(f"\nSample scatter: n = {N_SAMPLE:,}, seed = {SEED}; Luxury trong sample = {pct((s.Segment == 'Luxury').sum(), N_SAMPLE)}%"
      f"; implausible trong sample = {int(s.imp_any.sum())}; giá sàn trong sample = {int(s.floor_Car_Price.sum())}")
s.to_csv(TAB / "05d_scatter_sample_5000.csv", index_label="row_index")
xs = ["Registration_Age", "Kms_Driven", "Engine_CC", "Horsepower", "Mileage_kmpl", "Accidents"]
fig, axes = plt.subplots(2, 3, figsize=(14, 8.5))
rng = np.random.default_rng(SEED)
for ax, c in zip(axes.flat, xs):
    for seg in ["Non-luxury", "Luxury"]:
        ss = s[s.Segment == seg]
        x = ss[c] + (rng.uniform(-0.3, 0.3, len(ss)) if c in ("Registration_Age", "Accidents") else 0)
        ax.scatter(x, ss["Car_Price"], s=7, color=SEG_COLORS[seg], alpha=0.35, linewidths=0, label=seg)
    ax.set_yscale("log")
    thousands(ax)
    ax.set_xlabel(c + (" (jitter ±0.3)" if c in ("Registration_Age", "Accidents") else ""))
    ax.set_ylabel("Car_Price (log)")
    r_s = v["Car_Price"].corr(v[c], method="spearman")
    ax.set_title(f"Car_Price vs {c}  (Spearman toàn bộ = {r_s:.3f})", fontsize=9.5)
    if c == "Kms_Driven":
        ax.set_xscale("log")
        thousands(ax, "x")
axes[0, 0].legend(loc="lower left", markerscale=2.5)
fig.suptitle(f"Scatter trên sample ngẫu nhiên n = {N_SAMPLE:,} (seed {SEED}); trục y thang log", x=0.01, ha="left",
             fontsize=12, fontweight="bold")
fig.tight_layout()
fig.savefig(FIG / "fig_05b_scatter_sample.png")
plt.close(fig)

# ---------------------------------------------------------------- hình 05c: group means (toàn bộ dữ liệu)
v["Kms_decile"] = pd.qcut(v["Kms_Driven"], 10, labels=False) + 1
age_tab = v.groupby(["Registration_Age", "Segment"])["Car_Price"].agg(["count", "mean", "median"]).unstack()
kms_tab = v.groupby(["Kms_decile", "Segment"])["Car_Price"].agg(["count", "mean", "median"]).unstack()
kms_edges = v.groupby("Kms_decile")["Kms_Driven"].agg(["min", "max"])
# (sửa lỗi lần chạy đầu: join bảng 2 tầng cột với bảng 1 tầng -> MergeError; đưa kms_edges về 2 tầng)
kms_edges.columns = pd.MultiIndex.from_product([["Kms_range"], ["min", "max"]])
age_tab.to_csv(TAB / "05e_price_by_age_segment.csv")
kms_tab.join(kms_edges).to_csv(TAB / "05e_price_by_kms_decile_segment.csv")
with pd.option_context("display.float_format", lambda x: f"{x:,.0f}", "display.width", 250):
    print("\nMean / median Car_Price theo Registration_Age x Segment (toàn bộ dữ liệu):")
    print(age_tab[["mean", "median"]].to_string())
    print("\nMean / median Car_Price theo decile Kms_Driven x Segment:")
    print(kms_tab[["mean", "median"]].join(kms_edges).to_string())

fig, axes = plt.subplots(1, 2, figsize=(14, 4.8))
for ax, tab, xl in [(axes[0], age_tab, "Registration_Age (năm)"), (axes[1], kms_tab, "Decile Kms_Driven (1 = thấp nhất)")]:
    for seg in ["Non-luxury", "Luxury"]:
        ax.plot(tab.index, tab[("mean", seg)], color=SEG_COLORS[seg], linewidth=2, label=f"{seg} — mean")
        ax.plot(tab.index, tab[("median", seg)], color=SEG_COLORS[seg], linewidth=1, alpha=0.9,
                marker="o", markersize=3.5, label=f"{seg} — median")
    thousands(ax)
    ax.set_xlabel(xl)
    ax.set_ylabel("Car_Price (Rupees)")
    ax.set_ylim(0, None)
axes[0].set_title("Car_Price trung bình theo tuổi xe (toàn bộ 1,005,000 dòng)")
axes[1].set_title("Car_Price trung bình theo decile Kms_Driven (toàn bộ dữ liệu)")
axes[0].legend(loc="upper right", ncols=2)
fig.tight_layout()
fig.savefig(FIG / "fig_05c_group_means_age_kms.png")
plt.close(fig)

# ---------------------------------------------------------------- crosstabs categorical
print("\n=== Crosstab (row %) ===")
pairs = [("Segment", "Fuel_Type"), ("Segment", "Transmission"), ("Segment", "Owner_Type"), ("Segment", "City"),
         ("Segment", "Color"), ("Fuel_Type", "Transmission"), ("Brand", "Fuel_Type"), ("City", "Fuel_Type")]
ct_rows = []
for a, b in pairs:
    ct = pd.crosstab(v[a], v[b], normalize="index") * 100
    spread = (ct.max() - ct.min()).max()
    print(f"\n{a} x {b}: chênh lệch lớn nhất giữa các hàng trong cùng một cột = {spread:.2f} điểm %")
    if ct.shape[0] <= 3:
        print(ct.round(2).to_string())
    ct_rows.append({"row_var": a, "col_var": b, "max_row_pct_spread_pp": round(spread, 3)})
    ct.round(3).to_csv(TAB / f"05f_crosstab_{a}_x_{b}.csv")
pd.DataFrame(ct_rows).to_csv(TAB / "05f_crosstab_summary.csv", index=False)

# ---------------------------------------------------------------- hình 05d: thành phần theo segment
fig, axes = plt.subplots(1, 3, figsize=(14, 4))
for ax, c in zip(axes, ["Fuel_Type", "Transmission", "Owner_Type"]):
    ct = pd.crosstab(v[c], v["Segment"], normalize="columns") * 100
    if c == "Owner_Type":
        ct = ct.reindex(["First", "Second", "Third", "Fourth+"])
    y = np.arange(len(ct))
    ax.barh(y - 0.19, ct["Non-luxury"], height=0.36, color=SEG_COLORS["Non-luxury"], label="Non-luxury")
    ax.barh(y + 0.19, ct["Luxury"], height=0.36, color=SEG_COLORS["Luxury"], label="Luxury")
    ax.set_yticks(y)
    ax.set_yticklabels(ct.index)
    ax.invert_yaxis()
    ax.set_xlabel("% listing trong segment")
    ax.set_title(c)
    ax.grid(axis="y", visible=False)
axes[0].legend(loc="lower right")
fig.suptitle("Cơ cấu Fuel / Transmission / Owner theo segment", x=0.01, ha="left", fontsize=12, fontweight="bold")
fig.tight_layout()
fig.savefig(FIG / "fig_05d_composition_by_segment.png")
plt.close(fig)
print("\nĐã lưu hình: fig_05a..fig_05d")
