"""
06_target_price.py — Mục 7 EDA: phân tích biến mục tiêu Car_Price.

Mục đích :
  - Phân phối Car_Price gốc vs log(Car_Price): skewness, kurtosis; mean vs median (câu hỏi Guide A(iv)).
  - Car_Price theo từng biến categorical / rời rạc: count, mean, median, Q1, Q3, IQR.
  - TRỌNG TÂM: Luxury vs Non-luxury — count, mean, median, std, CV, phân vị, phân phối; trên 3 "view":
      all = toàn bộ; clean = bỏ exact duplicates + implausible; clean_nofloor = clean và bỏ giá sàn
      (view chỉ để so sánh độ nhạy — KHÔNG phải quyết định làm sạch).
  - Quan hệ price với biến khác THEO TỪNG SEGMENT: Pearson/Spearman và độ dốc trendline (least squares,
    thuần mô tả như trendline trong Excel — không phải mô hình suy luận) của price và log(price)
    theo Registration_Age, Kms_Driven... -> gợi ý interaction effect cho M2.
Input    : data_interim.parquet
Output   : tables/06*.csv; figures/fig_06a_price_vs_logprice.png, fig_06b_price_by_brand.png,
           fig_06c_price_by_categoricals.png, fig_06d_segment_distribution.png, fig_06e_depreciation_index.png
Bước EDA : Mục 7 — target variable. Không sampling.
"""
import numpy as np
import pandas as pd

from _common import (load_raw, analysis_view, TAB, FIG, SEG_COLORS, setup_plot, thousands, C1, C2, INK, INK2,
                     HIGHLIGHT_GREY, pct)

plt = setup_plot()
raw = load_raw()
v = analysis_view(raw)
v["log_price"] = np.log(v["Car_Price"])
v["is_dup_extra"] = raw.duplicated(keep="first")
views = {"all": v,
         "clean": v[~v.is_dup_extra & ~v.imp_any],
         "clean_nofloor": v[~v.is_dup_extra & ~v.imp_any & ~v.floor_Car_Price]}
for k, d in views.items():
    print(f"view '{k}': n = {len(d):,}")

# ---------------------------------------------------------------- phân phối price vs log(price)
print("\n=== Car_Price vs log(Car_Price) ===")
rows = []
for k, d in views.items():
    for var in ["Car_Price", "log_price"]:
        s = d[var]
        rows.append({"view": k, "variable": var, "n": len(s), "mean": s.mean(), "median": s.median(),
                     "mean/median": s.mean() / s.median(), "std": s.std(), "skewness": s.skew(),
                     "kurtosis_excess": s.kurt()})
dist = pd.DataFrame(rows)
with pd.option_context("display.float_format", lambda x: f"{x:,.3f}", "display.width", 250):
    print(dist.to_string(index=False))
dist.to_csv(TAB / "06a_price_vs_logprice.csv", index=False)
s = v["Car_Price"]
print(f"\nMean = {s.mean():,.0f} > median = {s.median():,.0f}: mean cao hơn median "
      f"{100 * (s.mean() / s.median() - 1):.1f}% -> phân phối lệch phải")
print(f"Tỉ trọng listing có giá > mean: {pct((s > s.mean()).sum(), len(s))}%")

# ---------------------------------------------------------------- price theo biến categorical
print("\n=== Car_Price theo nhóm (view 'all') ===")
group_vars = ["Segment", "Brand", "Fuel_Type", "Transmission", "Owner_Type", "Color", "City",
              "Accidents", "Number_of_Doors", "Seats", "Insurance_Valid", "Service_History", "Tax_Paid", "Model"]
rows = []
for g in group_vars:
    t = v.groupby(g)["Car_Price"].agg(count="count", mean="mean", median="median",
                                      Q1=lambda x: x.quantile(0.25), Q3=lambda x: x.quantile(0.75))
    t["IQR"] = t["Q3"] - t["Q1"]
    t["median_vs_overall_pct"] = 100 * (t["median"] / s.median() - 1)
    t = t.reset_index().rename(columns={g: "group"})
    t.insert(0, "variable", g)
    rows.append(t)
    spread = t["median"].max() / t["median"].min()
    print(f"{g:<16} {len(t):>2} nhóm | median thấp nhất {t.loc[t['median'].idxmin(), 'group']!s:<10} "
          f"{t['median'].min():>12,.0f} | cao nhất {t.loc[t['median'].idxmax(), 'group']!s:<10} "
          f"{t['median'].max():>12,.0f} | max/min = {spread:.2f}")
by_group = pd.concat(rows, ignore_index=True)
by_group.to_csv(TAB / "06b_price_by_group.csv", index=False)

# Có biến categorical nào tạo khác biệt TRONG từng segment không? (median max/min trong segment)
print("\nKhác biệt median trong TỪNG segment (max/min giữa các nhóm):")
rows = []
for g in ["Brand", "Model", "Fuel_Type", "Transmission", "Owner_Type", "Color", "City", "Accidents",
          "Service_History", "Insurance_Valid", "Tax_Paid", "Seats", "Number_of_Doors"]:
    for seg, d in views["clean"].groupby("Segment"):
        m = d.groupby(g)["Car_Price"].median()
        m = m.drop("Unknown", errors="ignore")
        rows.append({"variable": g, "Segment": seg, "n_groups": len(m), "min_median": m.min(),
                     "max_median": m.max(), "max/min": m.max() / m.min(), "argmin": m.idxmin(), "argmax": m.idxmax()})
within = pd.DataFrame(rows)
with pd.option_context("display.float_format", lambda x: f"{x:,.3f}", "display.width", 250):
    print(within.to_string(index=False))
within.to_csv(TAB / "06c_within_segment_group_spread.csv", index=False)

# (bổ sung sau lần chạy đầu: chi tiết Accidents & Service_History x Segment, kèm số dòng mỗi ô)
for g in ["Accidents", "Service_History"]:
    t = views["clean"].groupby([g, "Segment"])["Car_Price"].agg(["size", "median"]).unstack()
    base = t[("median", "Luxury")].iloc[0], t[("median", "Non-luxury")].iloc[0]
    t[("vs_first_pct", "Luxury")] = 100 * (t[("median", "Luxury")] / base[0] - 1)
    t[("vs_first_pct", "Non-luxury")] = 100 * (t[("median", "Non-luxury")] / base[1] - 1)
    t.to_csv(TAB / f"06c_price_by_{g}_segment.csv")
    with pd.option_context("display.float_format", lambda x: f"{x:,.1f}", "display.width", 250):
        print(f"\nMedian Car_Price theo {g} x Segment (view 'clean'; vs_first_pct = % so với nhóm đầu):")
        print(t.to_string())

# ---------------------------------------------------------------- Luxury vs Non-luxury
print("\n=== Luxury vs Non-luxury ===")
rows = []
for k, d in views.items():
    for seg, g in d.groupby("Segment"):
        p = g["Car_Price"]
        rows.append({"view": k, "Segment": seg, "n": len(p), "pct_of_view": pct(len(p), len(d)), "mean": p.mean(),
                     "median": p.median(), "std": p.std(), "CV": p.std() / p.mean(), "min": p.min(),
                     "P10": p.quantile(0.1), "Q1": p.quantile(0.25), "Q3": p.quantile(0.75), "P90": p.quantile(0.9),
                     "max": p.max(), "skewness": p.skew(), "skew_log": np.log(p).skew(),
                     "pct_at_floor": pct(g["floor_Car_Price"].sum(), len(g))})
segtab = pd.DataFrame(rows)
with pd.option_context("display.float_format", lambda x: f"{x:,.2f}", "display.width", 300):
    print(segtab.to_string(index=False))
segtab.to_csv(TAB / "06d_segment_comparison.csv", index=False)
for k in views:
    t = segtab[segtab.view == k].set_index("Segment")
    print(f"  [{k}] Luxury/Non-luxury: median x{t.loc['Luxury', 'median'] / t.loc['Non-luxury', 'median']:.2f}, "
          f"mean x{t.loc['Luxury', 'mean'] / t.loc['Non-luxury', 'mean']:.2f}; "
          f"chênh median = {t.loc['Luxury', 'median'] - t.loc['Non-luxury', 'median']:,.0f}")
c = views["clean"]
lux_p10 = c.loc[c.Segment == "Luxury", "Car_Price"].quantile(0.1)
print(f"  [clean] % Non-luxury có giá > P10 của Luxury ({lux_p10:,.0f}): "
      f"{pct((c.loc[c.Segment == 'Non-luxury', 'Car_Price'] > lux_p10).sum(), (c.Segment == 'Non-luxury').sum())}%")

# ---------------------------------------------------------------- quan hệ theo segment
print("\n=== Quan hệ price với biến numeric THEO SEGMENT (view 'clean') ===")
xs = ["Registration_Age", "Kms_Driven", "Engine_CC", "Horsepower", "Mileage_kmpl", "Accidents", "Service_History"]
rows = []
for k in ["clean", "clean_nofloor"]:
    for seg, g in views[k].groupby("Segment"):
        for x in xs:
            gg = g[[x, "Car_Price", "log_price"]].dropna()
            b_lin = np.polyfit(gg[x], gg["Car_Price"], 1)[0]
            b_log = np.polyfit(gg[x], gg["log_price"], 1)[0]
            rows.append({"view": k, "Segment": seg, "x": x, "n": len(gg),
                         "pearson_price": gg[x].corr(gg["Car_Price"]),
                         "spearman_price": gg[x].corr(gg["Car_Price"], method="spearman"),
                         "pearson_logprice": gg[x].corr(gg["log_price"]),
                         "slope_price_per_unit": b_lin,
                         "slope_logprice_per_unit": b_log,
                         "pct_change_per_unit": 100 * (np.exp(b_log) - 1)})
rel = pd.DataFrame(rows)
rel.to_csv(TAB / "06e_relationships_by_segment.csv", index=False)
with pd.option_context("display.float_format", lambda x: f"{x:,.4f}", "display.width", 300):
    print(rel[rel.view == "clean"].drop(columns="view").to_string(index=False))
print("\nĐộ dốc theo 1 năm tuổi và theo 10,000 km (view 'clean'):")
for seg in ["Luxury", "Non-luxury"]:
    r = rel[(rel.view == "clean") & (rel.Segment == seg)].set_index("x")
    print(f"  {seg:<10}: tuổi +1 năm -> {r.loc['Registration_Age', 'slope_price_per_unit']:>10,.0f} Rs "
          f"({r.loc['Registration_Age', 'pct_change_per_unit']:+.2f}%/năm theo log) | +10,000 km -> "
          f"{1e4 * r.loc['Kms_Driven', 'slope_price_per_unit']:>10,.0f} Rs "
          f"({100 * (np.exp(1e4 * r.loc['Kms_Driven', 'slope_logprice_per_unit']) - 1):+.2f}% theo log)")
print("  (view 'clean_nofloor' — bỏ giá sàn:)")
for seg in ["Luxury", "Non-luxury"]:
    r = rel[(rel.view == "clean_nofloor") & (rel.Segment == seg)].set_index("x")
    print(f"  {seg:<10}: tuổi +1 năm -> {r.loc['Registration_Age', 'slope_price_per_unit']:>10,.0f} Rs "
          f"({r.loc['Registration_Age', 'pct_change_per_unit']:+.2f}%/năm) | +10,000 km -> "
          f"{1e4 * r.loc['Kms_Driven', 'slope_price_per_unit']:>10,.0f} Rs "
          f"({100 * (np.exp(1e4 * r.loc['Kms_Driven', 'slope_logprice_per_unit']) - 1):+.2f}%)")

# Kms có thêm thông tin ngoài tuổi xe không? correlation price–Kms TRONG từng tuổi (view clean)
print("\nSpearman(Car_Price, Kms_Driven) TRONG từng nhóm tuổi (view 'clean'), trung bình qua 25 nhóm tuổi:")
for seg, g in views["clean"].groupby("Segment"):
    r = g.groupby("Registration_Age")[["Car_Price", "Kms_Driven"]].apply(lambda t: t.corr("spearman").iloc[0, 1])
    print(f"  {seg:<10}: mean = {r.mean():.3f}; min = {r.min():.3f} (tuổi {r.idxmin()}); max = {r.max():.3f} (tuổi {r.idxmax()})")

# chỉ số mất giá: median price theo tuổi, tuổi 1 = 100 (view clean)
idx = views["clean"].groupby(["Registration_Age", "Segment"])["Car_Price"].median().unstack()
idx_index = 100 * idx / idx.iloc[0]
idx.join(idx_index, rsuffix="_index_age1_100").to_csv(TAB / "06f_depreciation_index.csv")
print("\nChỉ số median price (tuổi 1 = 100), view 'clean':")
print(idx_index.iloc[[0, 4, 9, 14, 19, 24]].round(1).T.to_string())

# ---------------------------------------------------------------- hình 06a: price vs log(price)
fig, axes = plt.subplots(1, 2, figsize=(13, 4.3))
p = v["Car_Price"]
hi = p.quantile(0.999)
axes[0].hist(p[p <= hi], bins=150, color=C1, linewidth=0)
axes[0].set_title(f"Car_Price (skew = {p.skew():.2f}; trục x cắt ở P99.9)")
thousands(axes[0])
thousands(axes[0], "x")
axes[1].hist(v["log_price"], bins=150, color=C1, linewidth=0)
axes[1].set_title(f"log(Car_Price) (skew = {v['log_price'].skew():.2f})")
thousands(axes[1])
for ax, m, md in [(axes[0], p.mean(), p.median()), (axes[1], v["log_price"].mean(), v["log_price"].median())]:
    ax.axvline(m, color=C2, linewidth=1.5, label="mean")
    ax.axvline(md, color=INK, linewidth=1.5, label="median")
    ax.set_ylabel("Số listing")
axes[0].legend()
axes[1].annotate(f"Giá sàn 50,000\n({v.floor_Car_Price.sum():,} dòng)", (np.log(50_000), 0), xytext=(18, 60),
                 textcoords="offset points", fontsize=8.5, color=INK2, arrowprops=dict(arrowstyle="-", color=INK2))
axes[1].set_xlabel("ln(Car_Price)")
axes[0].set_xlabel("Car_Price (Rupees)")
fig.tight_layout()
fig.savefig(FIG / "fig_06a_price_vs_logprice.png")
plt.close(fig)

# ---------------------------------------------------------------- hình 06b: price theo Brand
order = v.groupby("Brand")["Car_Price"].median().sort_values().index
fig, ax = plt.subplots(figsize=(10, 6))
data = [v.loc[v.Brand == b, "Car_Price"] for b in order]
bp = ax.boxplot(data, orientation="horizontal", tick_labels=list(order), widths=0.55, patch_artist=True,
                showfliers=False, medianprops=dict(color=INK, linewidth=1.5))
for patch, b in zip(bp["boxes"], order):
    col = SEG_COLORS["Luxury" if b in ("Audi", "BMW", "Mercedes") else "Non-luxury"]
    patch.set_facecolor(col + "33")
    patch.set_edgecolor(col)
ax.set_xscale("log")
thousands(ax, "x")
ax.set_xlabel("Car_Price (Rupees, thang log) — không vẽ outlier; whisker 1.5×IQR")
ax.set_title("Car_Price theo Brand (cam = Luxury, xanh = Non-luxury; sắp theo median)")
ax.grid(axis="y", visible=False)
fig.tight_layout()
fig.savefig(FIG / "fig_06b_price_by_brand.png")
plt.close(fig)

# ---------------------------------------------------------------- hình 06c: price theo categorical khác
cats = ["Fuel_Type", "Transmission", "Owner_Type", "City", "Accidents", "Service_History"]
fig, axes = plt.subplots(2, 3, figsize=(14, 8))
for ax, g in zip(axes.flat, cats):
    t = views["clean"].groupby([g, "Segment"])["Car_Price"].median().unstack()
    if g == "Owner_Type":
        t = t.reindex(["First", "Second", "Third", "Fourth+"])
    y = np.arange(len(t))
    ax.barh(y - 0.19, t["Non-luxury"], height=0.36, color=SEG_COLORS["Non-luxury"], label="Non-luxury")
    ax.barh(y + 0.19, t["Luxury"], height=0.36, color=SEG_COLORS["Luxury"], label="Luxury")
    ax.set_yticks(y)
    ax.set_yticklabels([str(i) for i in t.index])
    ax.invert_yaxis()
    ax.set_title(f"Median Car_Price theo {g}")
    thousands(ax, "x")
    ax.grid(axis="y", visible=False)
axes[0, 0].legend(loc="lower right")
fig.suptitle("Median Car_Price theo biến categorical và segment (view 'clean')", x=0.01, ha="left", fontsize=12,
             fontweight="bold")
fig.tight_layout()
fig.savefig(FIG / "fig_06c_price_by_categoricals.png")
plt.close(fig)

# ---------------------------------------------------------------- hình 06d: phân phối theo segment
fig, axes = plt.subplots(1, 2, figsize=(13, 4.3))
bins = np.linspace(np.log(50_000), np.log(v["Car_Price"].quantile(0.999)), 120)
for seg in ["Non-luxury", "Luxury"]:
    g = views["clean"].loc[views["clean"].Segment == seg, "log_price"]
    axes[0].hist(g, bins=bins, density=True, histtype="step", linewidth=2, color=SEG_COLORS[seg], label=seg)
    axes[0].axvline(g.median(), color=SEG_COLORS[seg], linewidth=1)
axes[0].set_xlabel("ln(Car_Price)")
axes[0].set_ylabel("Mật độ")
axes[0].set_title("Phân phối ln(Car_Price) theo segment (view 'clean')")
axes[0].legend()
tick_rs = [50_000, 200_000, 1_000_000, 5_000_000]
# (sửa sau lần chạy đầu: np.log(0) sinh RuntimeWarning khi matplotlib dựng trục phụ -> clip trước khi log)
sec = axes[0].secondary_xaxis("top", functions=(np.exp, lambda x: np.log(np.clip(x, 1e-9, None))))
sec.set_xticks(tick_rs)
sec.set_xticklabels([f"{t:,.0f}" for t in tick_rs], fontsize=7.5)
t = segtab[segtab.view == "clean"].set_index("Segment")
stats_show = ["n", "mean", "median", "std", "Q1", "Q3", "pct_at_floor"]
cell = [[f"{t.loc[s_, c_]:,.0f}" if c_ != "pct_at_floor" else f"{t.loc[s_, c_]:.2f}%" for s_ in ["Non-luxury", "Luxury"]]
        for c_ in stats_show]
axes[1].axis("off")
tb = axes[1].table(cellText=cell, rowLabels=stats_show, colLabels=["Non-luxury", "Luxury"], loc="center",
                   cellLoc="right")
tb.scale(1, 1.6)
tb.set_fontsize(9.5)
axes[1].set_title("Thống kê Car_Price theo segment (view 'clean', Rupees)")
fig.tight_layout()
fig.savefig(FIG / "fig_06d_segment_distribution.png")
plt.close(fig)

# ---------------------------------------------------------------- hình 06e: chỉ số mất giá
fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
for seg in ["Non-luxury", "Luxury"]:
    axes[0].plot(idx.index, idx[seg], color=SEG_COLORS[seg], marker="o", markersize=3.5, label=seg)
    axes[1].plot(idx_index.index, idx_index[seg], color=SEG_COLORS[seg], marker="o", markersize=3.5, label=seg)
    axes[1].annotate(f"{seg}: {idx_index[seg].iloc[-1]:.0f}", (idx_index.index[-1], idx_index[seg].iloc[-1]),
                     fontsize=8.5, color=INK2, xytext=(6, 0), textcoords="offset points", va="center")
axes[0].set_yscale("log")
thousands(axes[0])
axes[0].set_title("Median Car_Price theo tuổi xe (thang log)")
axes[0].set_ylabel("Median Car_Price (Rupees)")
axes[1].set_title("Chỉ số median Car_Price (tuổi 1 = 100)")
axes[1].set_ylabel("Chỉ số")
for ax in axes:
    ax.set_xlabel("Registration_Age (năm)")
axes[0].legend()
axes[1].set_xlim(0, 28.5)
fig.suptitle("Mất giá theo tuổi: Non-luxury giảm nhanh hơn Luxury theo tỉ lệ % (view 'clean')", x=0.01, ha="left",
             fontsize=12, fontweight="bold")
fig.tight_layout()
fig.savefig(FIG / "fig_06e_depreciation_index.png")
plt.close(fig)
print("\nĐã lưu hình: fig_06a..fig_06e")
