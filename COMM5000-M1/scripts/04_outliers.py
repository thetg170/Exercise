"""
04_outliers.py — Mục 5 EDA: phân tích ngoại lệ (outliers).

Mục đích :
  - Đếm outlier theo IQR rule (1.5×IQR, 3×IQR) và z-score (|z| > 3) cho biến numeric; so sánh hai cách.
    Với biến lệch phải mạnh (Kms_Driven, Car_Price) làm thêm trên thang log.
  - Tách: (a) implausible — phi lý theo logic nội tại (hoặc ví dụ trong Assessment Guide: Kms > 1,000,000);
          (b) extreme nhưng có thể hợp lệ — vượt 3×IQR nhưng không vi phạm logic;
          (c) giá trị sàn (censored) — point mass đúng ở giá trị min (không phải outlier theo IQR nhưng
              làm méo phân phối).
  - Kiểm tra outlier / giá trị sàn có tập trung ở segment Luxury không.
Input    : data_interim.parquet
Output   : tables/04*.csv; figures/fig_04a_price_box_segment.png, fig_04b_floor_share_by_age.png,
           fig_04c_kms_tail.png
Bước EDA : Mục 5 — outliers. Không sampling.
"""
import numpy as np
import pandas as pd

from _common import (load_raw, analysis_view, floor_values, TAB, FIG, KMS_IMPLAUSIBLE, KMS_PER_YEAR_MAX, SEG_COLORS,
                     setup_plot, thousands, C1, C2, INK, INK2, pct)

plt = setup_plot()
raw = load_raw()
v = analysis_view(raw)
N = len(v)


def outlier_counts(s: pd.Series, name: str) -> dict:
    s = s.dropna()
    q1, q3 = s.quantile([0.25, 0.75])
    iqr = q3 - q1
    z = (s - s.mean()) / s.std()
    r = {"variable": name, "n": len(s), "Q1": q1, "Q3": q3, "IQR": iqr,
         "lower_1.5": q1 - 1.5 * iqr, "upper_1.5": q3 + 1.5 * iqr,
         "n_low_1.5": int((s < q1 - 1.5 * iqr).sum()), "n_high_1.5": int((s > q3 + 1.5 * iqr).sum()),
         "n_low_3": int((s < q1 - 3 * iqr).sum()), "n_high_3": int((s > q3 + 3 * iqr).sum()),
         "n_abs_z_gt_3": int((z.abs() > 3).sum())}
    r["pct_1.5"] = pct(r["n_low_1.5"] + r["n_high_1.5"], len(s))
    r["pct_3"] = pct(r["n_low_3"] + r["n_high_3"], len(s))
    r["pct_z3"] = pct(r["n_abs_z_gt_3"], len(s))
    return r


# ---------------------------------------------------------------- IQR vs z-score
cols = ["Mileage_kmpl", "Engine_CC", "Horsepower", "Kms_Driven", "Car_Price", "Accidents"]
rows = [outlier_counts(v[c], c) for c in cols]
rows += [outlier_counts(np.log(v["Kms_Driven"]), "log(Kms_Driven)"),
         outlier_counts(np.log(v["Car_Price"]), "log(Car_Price)")]
oc = pd.DataFrame(rows)
oc.to_csv(TAB / "04a_outlier_counts_iqr_vs_z.csv", index=False)
with pd.option_context("display.float_format", lambda x: f"{x:,.2f}", "display.width", 250):
    print("=== IQR (1.5×, 3×) vs z-score (|z|>3) — toàn bộ dữ liệu ===")
    print(oc.to_string(index=False))

# ---------------------------------------------------------------- (a) implausible
print("\n=== (a) Implausible — theo logic nội tại (chỉ gắn cờ, không xoá) ===")
imp_cols = [c for c in v.columns if c.startswith("imp_")]
imp = pd.DataFrame({"rule": imp_cols, "n_rows": [int(v[c].sum()) for c in imp_cols]})
imp["pct"] = imp["n_rows"].map(lambda k: pct(k, N))
imp["luxury_share_of_flagged_pct"] = [pct((v[c] & (v.Segment == "Luxury")).sum(), v[c].sum()) if v[c].sum() else np.nan
                                      for c in imp_cols]
print(imp.to_string(index=False))
print(f"(Tỉ trọng Luxury trong toàn bộ mẫu = {pct((v.Segment == 'Luxury').sum(), N)}%)")
imp.to_csv(TAB / "04b_implausible_flags.csv", index=False)

hp_neg = v.loc[v.imp_hp_nonpos, ["Brand", "Model", "Engine_CC", "Horsepower", "Car_Price"]]
print(f"\nHorsepower <= 0: {len(hp_neg)} dòng; min = {hp_neg.Horsepower.min():.2f}; "
      f"Engine_CC của các dòng này: median = {hp_neg.Engine_CC.median():,.0f}")

k = v["Kms_Driven"]
print(f"\nKms_Driven > {KMS_IMPLAUSIBLE:,}: {(k > KMS_IMPLAUSIBLE).sum():,} dòng ({pct((k > KMS_IMPLAUSIBLE).sum(), N)}%); "
      f"max = {k.max():,.0f}")
print("  Phân vị cao của Kms_Driven:", {f"P{q * 100:g}": f"{k.quantile(q):,.0f}" for q in [0.9, 0.99, 0.995, 0.999]})
# Có "khoảng trống" trong phân phối không? (giá trị > 1M có tách rời khỏi phần thân?)
edges = [600_000, 650_000, 700_000, 800_000, 1_000_000, 2_000_000, 5_000_000]
print("  Số dòng theo khoảng Kms:", pd.cut(k, [0] + edges).value_counts().sort_index().to_dict())
kpy = k / v["Registration_Age"]
print(f"  Kms / Registration_Age (km mỗi năm tuổi): median = {kpy.median():,.0f}; "
      f"P99 = {kpy.quantile(0.99):,.0f}; ở nhóm Kms > 1M: median = {kpy[k > KMS_IMPLAUSIBLE].median():,.0f}")

# (bổ sung sau lần chạy đầu: fig_04c cho thấy "điểm gãy" ~620k km, sau đó là một quần thể phẳng tới 4.4M.
#  Kiểm tra: phần thân dữ liệu có bị chặn trên về km/năm không?)
print("\n  --- Km mỗi năm tuổi (Kms_Driven / Registration_Age) ---")
print("  Phân vị:", {f"P{q * 100:g}": f"{kpy.quantile(q):,.0f}" for q in [0, 0.001, 0.5, 0.99, 0.994, 0.995, 0.999, 1]})
edges_kpy = [0, 4_999, 5_000, 24_999, 25_000, 25_001, 30_000, 50_000, 100_000, 1e7]
print("  Số dòng theo khoảng km/năm:", pd.cut(kpy, edges_kpy).value_counts().sort_index().to_dict())
KPY_MAX = KMS_PER_YEAR_MAX   # biên trên quan sát được của phần thân (kiểm chứng bằng bảng trên)
over = kpy > KPY_MAX
print(f"  Dòng có km/năm > {KPY_MAX:,}: {over.sum():,} ({pct(over.sum(), N)}%) | "
      f"trong đó Kms > 1M: {(over & (k > KMS_IMPLAUSIBLE)).sum():,}; Kms <= 1M: {(over & (k <= KMS_IMPLAUSIBLE)).sum():,}")
print(f"  Ngược lại: Kms > 1M mà km/năm <= {KPY_MAX:,}: {((k > KMS_IMPLAUSIBLE) & ~over).sum():,}")
print("  Phân bố Registration_Age của nhóm km/năm > 25k (so với toàn mẫu ~4%/tuổi):",
      (v.loc[over, "Registration_Age"].value_counts(normalize=True).sort_index() * 100).round(1).to_dict())
print(f"  Luxury trong nhóm này: {pct((over & (v.Segment == 'Luxury')).sum(), over.sum())}%")
print(f"  Median Car_Price: nhóm km/năm > 25k = {v.loc[over, 'Car_Price'].median():,.0f}; "
      f"phần còn lại = {v.loc[~over, 'Car_Price'].median():,.0f}")
# Giá có bị "phóng đại" cùng lúc với Kms không? So sánh giá với median giá của xe CÙNG Model & CÙNG tuổi
# (tham chiếu tính trên nhóm km/năm <= 25k và không ở giá sàn).
ref_mask = ~over & ~v["floor_Car_Price"]
ref = v[ref_mask].groupby(["Model", "Registration_Age"])["Car_Price"].median().rename("ref_price")
rel = v.join(ref, on=["Model", "Registration_Age"])
rel["price_rel"] = rel["Car_Price"] / rel["ref_price"]
rel["kpy_rel"] = kpy / kpy[~over].median()
qs = [0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99]
print("  Car_Price / median(Car_Price | Model, Registration_Age) — phân vị:")
print("    nhóm km/năm <= 25k (không sàn):", {f"P{q * 100:g}": round(rel.loc[ref_mask, 'price_rel'].quantile(q), 2) for q in qs})
print("    nhóm km/năm  > 25k            :", {f"P{q * 100:g}": round(rel.loc[over, 'price_rel'].quantile(q), 2) for q in qs})
print(f"  Spearman(kpy_rel, price_rel) trong nhóm > 25k: {rel.loc[over, ['kpy_rel', 'price_rel']].corr('spearman').iloc[0, 1]:.3f}")
ratio = (rel["price_rel"] / rel["kpy_rel"])[over]
print("  Tỉ số price_rel / kpy_rel trong nhóm > 25k:", {f"P{q * 100:g}": round(ratio.quantile(q), 2) for q in qs})
hi_price_rest = (rel["price_rel"] > rel.loc[over, "price_rel"].quantile(0.1)) & ref_mask
print(f"  Số dòng NGOÀI nhóm có price_rel > P10 của nhóm ({rel.loc[over, 'price_rel'].quantile(0.1):.2f}): "
      f"{hi_price_rest.sum():,} ({pct(hi_price_rest.sum(), ref_mask.sum())}%)")
p_ext = v["Car_Price"] > v["Car_Price"].quantile(0.75) + 3 * (v["Car_Price"].quantile(0.75) - v["Car_Price"].quantile(0.25))
print(f"  Car_Price > 3×IQR: {p_ext.sum():,} dòng, trong đó thuộc nhóm km/năm > 25k: {(p_ext & over).sum():,} "
      f"({pct((p_ext & over).sum(), p_ext.sum())}%)")
rel.loc[over, ["Brand", "Model", "Registration_Age", "Kms_Driven", "Car_Price", "ref_price", "price_rel", "kpy_rel"]] \
    .head(12).assign(excel_row=lambda d: d.index + 2).to_csv(TAB / "04h_kms_anomaly_examples.csv", index=False)

pd.DataFrame({"rule": ["Kms > 1,000,000 (Guide)", f"km/năm > {KPY_MAX:,} (logic nội tại)", "cả hai", "chỉ km/năm"],
              "n_rows": [int((k > KMS_IMPLAUSIBLE).sum()), int(over.sum()),
                         int((over & (k > KMS_IMPLAUSIBLE)).sum()), int((over & (k <= KMS_IMPLAUSIBLE)).sum())]}) \
    .to_csv(TAB / "04g_kms_rules_compare.csv", index=False)

# ---------------------------------------------------------------- (b) extreme nhưng có thể hợp lệ
print("\n=== (b) Extreme (> 3×IQR) nhưng KHÔNG vi phạm quy tắc (a) ===")
rows = []
for c in ["Kms_Driven", "Car_Price", "Engine_CC", "Horsepower", "Mileage_kmpl"]:
    s = v[c]
    q1, q3 = s.quantile([0.25, 0.75])
    ext = (s > q3 + 3 * (q3 - q1)) | (s < q1 - 3 * (q3 - q1))
    ext_valid = ext & ~v["imp_any"]
    rows.append({"variable": c, "n_extreme_3iqr": int(ext.sum()), "of_which_implausible": int((ext & v.imp_any).sum()),
                 "extreme_not_implausible": int(ext_valid.sum()),
                 "luxury_share_pct": pct((ext_valid & (v.Segment == "Luxury")).sum(), ext_valid.sum())})
ext_tab = pd.DataFrame(rows)
print(ext_tab.to_string(index=False))
ext_tab.to_csv(TAB / "04c_extreme_not_implausible.csv", index=False)

# ---------------------------------------------------------------- outlier của Car_Price theo segment
print("\n=== Car_Price: outlier tập trung ở Luxury? ===")
p = v["Car_Price"]
q1, q3 = p.quantile([0.25, 0.75])
hi15 = q3 + 1.5 * (q3 - q1)
rows = []
for seg, d in v.groupby("Segment"):
    ps = d["Car_Price"]
    s1, s3 = ps.quantile([0.25, 0.75])
    rows.append({"Segment": seg, "n": len(d),
                 "pct_above_overall_fence_1.5": pct((ps > hi15).sum(), len(d)),
                 "share_of_all_high_outliers_pct": pct((ps > hi15).sum(), (p > hi15).sum()),
                 "within_segment_fence_1.5": s3 + 1.5 * (s3 - s1),
                 "pct_above_within_segment_fence": pct((ps > s3 + 1.5 * (s3 - s1)).sum(), len(d)),
                 "pct_above_within_segment_3iqr": pct((ps > s3 + 3 * (s3 - s1)).sum(), len(d))})
seg_out = pd.DataFrame(rows)
print(f"Fence 1.5×IQR toàn mẫu = {hi15:,.0f}")
with pd.option_context("display.float_format", lambda x: f"{x:,.2f}", "display.width", 250):
    print(seg_out.to_string(index=False))
seg_out.to_csv(TAB / "04d_price_outliers_by_segment.csv", index=False)

# ---------------------------------------------------------------- (c) giá trị sàn (censored)
print("\n=== (c) Giá trị sàn (point mass tại min) ===")
fv = floor_values(raw)
rows = []
for c, m in fv.items():
    fl = v[f"floor_{c}"]
    rows.append({"variable": c, "floor_value": m, "n_rows": int(fl.sum()), "pct": pct(fl.sum(), v[c].notna().sum()),
                 "pct_in_Luxury": pct((fl & (v.Segment == "Luxury")).sum(), (v.Segment == "Luxury").sum()),
                 "pct_in_Non-luxury": pct((fl & (v.Segment == "Non-luxury")).sum(), (v.Segment == "Non-luxury").sum()),
                 "next_value_above_floor": v.loc[v[c] > m, c].min()})
fl_tab = pd.DataFrame(rows)
print(fl_tab.to_string(index=False))
fl_tab.to_csv(TAB / "04e_floor_values.csv", index=False)

fp = v["floor_Car_Price"]
age_seg = (v.assign(floor=fp).groupby(["Registration_Age", "Segment"])["floor"].mean().unstack() * 100)
print("\n% listing có Car_Price = sàn, theo Registration_Age x Segment:")
print(age_seg.round(2).T.to_string())
age_seg.to_csv(TAB / "04f_price_floor_share_by_age_segment.csv")
kms_bins = pd.qcut(v["Kms_Driven"], 5)
print("\n% Car_Price = sàn theo nhóm Kms_Driven (quintile):")
print((v.groupby(kms_bins, observed=True)["floor_Car_Price"].mean() * 100).round(2).to_string())
for c in ["Fuel_Type", "Owner_Type", "Accidents", "City"]:
    r = v.groupby(c)["floor_Car_Price"].mean() * 100
    print(f"% sàn theo {c}: min {r.min():.2f}% ({r.idxmin()}) – max {r.max():.2f}% ({r.idxmax()})")

# ---------------------------------------------------------------- hình 04a: boxplot price theo segment (log)
fig, ax = plt.subplots(figsize=(9, 4.2))
segs = ["Non-luxury", "Luxury"]
data = [v.loc[v.Segment == s, "Car_Price"] for s in segs]
bp = ax.boxplot(data, orientation="horizontal", widths=0.5, patch_artist=True, tick_labels=segs,
                medianprops=dict(color=INK, linewidth=1.5),
                flierprops=dict(marker="o", markersize=2, markeredgecolor="none", alpha=0.25))
for patch, s in zip(bp["boxes"], segs):
    patch.set_facecolor(SEG_COLORS[s] + "33")
    patch.set_edgecolor(SEG_COLORS[s])
for fl, s in zip(bp["fliers"], segs):
    fl.set_markerfacecolor(SEG_COLORS[s])
for i, s in enumerate(segs, start=1):
    for w in bp["whiskers"][2 * (i - 1): 2 * i] + bp["caps"][2 * (i - 1): 2 * i]:
        w.set_color(SEG_COLORS[s])
ax.axvline(hi15, color=INK2, linewidth=1)
ax.annotate(f"Fence 1.5×IQR toàn mẫu = {hi15:,.0f}", (hi15, 2.42), fontsize=8, color=INK2, xytext=(4, 0),
            textcoords="offset points")
ax.set_xscale("log")
ax.set_xlabel("Car_Price (Rupees, thang log)")
thousands(ax, "x")
ax.set_title("Car_Price theo segment — boxplot (whisker 1.5×IQR trong từng segment)")
fig.tight_layout()
fig.savefig(FIG / "fig_04a_price_box_segment.png")
plt.close(fig)

# ---------------------------------------------------------------- hình 04b: % sàn theo tuổi xe
fig, ax = plt.subplots(figsize=(9, 4.2))
for s in segs:
    ax.plot(age_seg.index, age_seg[s], color=SEG_COLORS[s], marker="o", markersize=4, label=s)
    ax.annotate(s, (age_seg.index[-1], age_seg[s].iloc[-1]), fontsize=8.5, color=INK2, xytext=(6, 0),
                textcoords="offset points", va="center")
ax.set_xlabel("Registration_Age (năm)")
ax.set_ylabel(f"% listing có Car_Price = {fv.get('Car_Price', np.nan):,.0f}")
ax.set_title("Tỉ lệ Car_Price bằng giá trị sàn theo tuổi xe và segment")
ax.legend(loc="upper left")
fig.tight_layout()
fig.savefig(FIG / "fig_04b_floor_share_by_age.png")
plt.close(fig)

# ---------------------------------------------------------------- hình 04c: đuôi Kms_Driven
fig, ax = plt.subplots(figsize=(9, 4.2))
ax.hist(np.log10(k), bins=150, color=C1, linewidth=0)
ax.set_yscale("log")
ax.axvline(np.log10(KMS_IMPLAUSIBLE), color=C2, linewidth=1.5)
ax.annotate(f"1,000,000 km (ví dụ implausible trong Guide)\n{(k > KMS_IMPLAUSIBLE).sum():,} dòng vượt ngưỡng",
            (np.log10(KMS_IMPLAUSIBLE), ax.get_ylim()[1] * 0.3), fontsize=8.5, color=INK2, xytext=(6, 0),
            textcoords="offset points")
ticks = [5e3, 1e4, 5e4, 1e5, 5e5, 1e6, 4e6]
ax.set_xticks(np.log10(ticks))
ax.set_xticklabels([f"{t:,.0f}" for t in ticks])
ax.set_xlabel("Kms_Driven (thang log10)")
ax.set_ylabel("Số listing (thang log)")
ax.set_title("Phân phối Kms_Driven — đuôi phải và ngưỡng 1,000,000 km")
fig.tight_layout()
fig.savefig(FIG / "fig_04c_kms_tail.png")
plt.close(fig)

# ---------------------------------------------------------------- hình 04d: km mỗi năm tuổi
fig, ax = plt.subplots(figsize=(9, 4.2))
ax.hist(np.log10(kpy), bins=150, color=C1, linewidth=0)
ax.set_yscale("log")
ax.axvline(np.log10(KPY_MAX), color=C2, linewidth=1.5)
ax.annotate(f"{KPY_MAX:,} km/năm — biên trên của {pct((~over).sum(), N)}% dữ liệu\n"
            f"{over.sum():,} dòng vượt biên", (np.log10(KPY_MAX), ax.get_ylim()[1] * 0.3), fontsize=8.5,
            color=INK2, xytext=(6, 0), textcoords="offset points")
ticks = [5e3, 1e4, 2.5e4, 5e4, 1e5, 5e5, 2e6]
ax.set_xticks(np.log10(ticks))
ax.set_xticklabels([f"{t:,.0f}" for t in ticks])
ax.set_xlabel("Kms_Driven / Registration_Age (km mỗi năm tuổi, thang log10)")
ax.set_ylabel("Số listing (thang log)")
ax.set_title("Km mỗi năm tuổi xe — phần thân bị chặn trong [5,000; 25,000]")
fig.tight_layout()
fig.savefig(FIG / "fig_04d_kms_per_year.png")
plt.close(fig)
print("\nĐã lưu hình: fig_04a..fig_04d")
