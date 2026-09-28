"""
08_representativeness.py — Mục 9 EDA: tính đại diện và thiên lệch (bias).

Mục đích :
  - Phân bố số listing theo City, Brand, Model, Year, Segment: mức mất cân bằng (max/min, CV).
  - Missing/Unknown có ngẫu nhiên không: so sánh Car_Price của dòng thiếu/Unknown vs đầy đủ, TRONG từng segment.
  - So sánh cơ cấu mẫu TRƯỚC/SAU theo các kịch bản loại dòng (chỉ mô phỏng trong bộ nhớ, không ghi dữ liệu):
      S0 dữ liệu gốc
      S1 = S0 − bản sao thừa của exact duplicates
      S2 = S1 − implausible (km/năm > 25,000 hoặc Horsepower <= 0)          <- đề xuất chính
      S2b= S1 − chỉ Kms_Driven > 1,000,000 (quy tắc ví dụ trong Guide)       <- phương án thay thế
      S3 = S2 − mọi dòng có NaN hoặc 'Unknown' (listwise deletion)           <- KHÔNG khuyến nghị, để so sánh
      S4 = S2 − dòng Car_Price = giá sàn                                      <- KHÔNG khuyến nghị, để so sánh
Input    : data_interim.parquet
Output   : tables/08*.csv; figures/fig_08a_scenarios_age_mix.png, fig_08b_scenarios_price.png
Bước EDA : Mục 9 — representativeness & bias.
"""
import numpy as np
import pandas as pd

from _common import (load_raw, analysis_view, TAB, FIG, SEG_COLORS, setup_plot, thousands, C1, C2, C3, INK, INK2,
                     pct)

plt = setup_plot()
raw = load_raw()
v = analysis_view(raw)
N = len(v)
v["is_dup_extra"] = raw.duplicated(keep="first")
unk_cols = ["Fuel_Type", "Transmission", "Color", "City"]
nan_cols = ["Mileage_kmpl", "Engine_CC", "Horsepower"]
v["has_nan"] = v[nan_cols].isna().any(axis=1)
v["has_unknown"] = (v[unk_cols] == "Unknown").any(axis=1)

# ---------------------------------------------------------------- phân bố listing
print("=== Phân bố số listing (view all) ===")
rows = []
for g in ["Segment", "Brand", "Model", "City", "Year", "Fuel_Type", "Transmission", "Owner_Type", "Color"]:
    vc = v[g].value_counts()
    vc_known = vc.drop("Unknown", errors="ignore")
    rows.append({"variable": g, "n_groups": len(vc), "largest": vc.index[0], "largest_pct": pct(vc.iloc[0], N),
                 "smallest": vc.index[-1], "smallest_pct": pct(vc.iloc[-1], N),
                 "max/min_excl_Unknown": round(vc_known.max() / vc_known.min(), 3),
                 "CV_counts_excl_Unknown": round(vc_known.std() / vc_known.mean(), 4)})
dist = pd.DataFrame(rows)
print(dist.to_string(index=False))
dist.to_csv(TAB / "08a_listing_distribution.csv", index=False)

# ---------------------------------------------------------------- missing/unknown vs giá
print("\n=== Missing / Unknown có liên quan tới giá không? (median Car_Price, view all) ===")
rows = []
for flag in ["has_nan", "has_unknown"]:
    for seg, g in v.groupby("Segment"):
        m = g.groupby(flag)["Car_Price"].agg(["size", "median", "mean"])
        rows.append({"flag": flag, "Segment": seg, "n_flagged": int(m.loc[True, "size"]),
                     "pct_flagged": pct(m.loc[True, "size"], len(g)),
                     "median_flagged": m.loc[True, "median"], "median_complete": m.loc[False, "median"],
                     "diff_pct": 100 * (m.loc[True, "median"] / m.loc[False, "median"] - 1),
                     "mean_age_flagged": g.loc[g[flag], "Registration_Age"].mean(),
                     "mean_age_complete": g.loc[~g[flag], "Registration_Age"].mean()})
mu = pd.DataFrame(rows)
with pd.option_context("display.float_format", lambda x: f"{x:,.3f}", "display.width", 250):
    print(mu.to_string(index=False))
mu.to_csv(TAB / "08b_missing_unknown_vs_price.csv", index=False)

# ---------------------------------------------------------------- kịch bản trước/sau
scen = {
    "S0 gốc": pd.Series(True, index=v.index),
    "S1 −duplicates": ~v.is_dup_extra,
    "S2 −dup −implausible (đề xuất)": ~v.is_dup_extra & ~v.imp_any,
    "S2b −dup −Kms>1M (Guide)": ~v.is_dup_extra & ~v.imp_kms_gt_1m,
    "S3 = S2 −NaN/Unknown (listwise)": ~v.is_dup_extra & ~v.imp_any & ~v.has_nan & ~v.has_unknown,
    "S4 = S2 −giá sàn": ~v.is_dup_extra & ~v.imp_any & ~v.floor_Car_Price,
}
rows = []
for name, m in scen.items():
    d = v[m]
    lux = d[d.Segment == "Luxury"]["Car_Price"]
    non = d[d.Segment == "Non-luxury"]["Car_Price"]
    city_share = d["City"].value_counts(normalize=True) * 100
    rows.append({
        "scenario": name, "n": len(d), "pct_retained": pct(len(d), N),
        "pct_luxury": pct((d.Segment == "Luxury").sum(), len(d)),
        "mean_age": d["Registration_Age"].mean(), "pct_age_ge_20": pct((d.Registration_Age >= 20).sum(), len(d)),
        "pct_non_luxury_age_ge_20": pct(((d.Segment == "Non-luxury") & (d.Registration_Age >= 20)).sum(),
                                        (d.Segment == "Non-luxury").sum()),
        "mean_price": d["Car_Price"].mean(), "median_price": d["Car_Price"].median(),
        "skew_price": d["Car_Price"].skew(),
        "median_luxury": lux.median(), "median_non_luxury": non.median(),
        "ratio_median_lux_non": lux.median() / non.median(),
        "spearman_price_age": d["Car_Price"].corr(d["Registration_Age"], method="spearman"),
        "pearson_price_kms": d["Car_Price"].corr(d["Kms_Driven"]),
        "spearman_price_kms": d["Car_Price"].corr(d["Kms_Driven"], method="spearman"),
        "max_city_share_pct": city_share.drop("Unknown", errors="ignore").max(),
        "pct_floor_price": pct(d["floor_Car_Price"].sum(), len(d)),
    })
sc = pd.DataFrame(rows)
with pd.option_context("display.float_format", lambda x: f"{x:,.3f}", "display.width", 400, "display.max_columns", 30):
    print("\n=== So sánh kịch bản (trước/sau) ===")
    print(sc.set_index("scenario").T.to_string())
sc.to_csv(TAB / "08c_scenarios_before_after.csv", index=False)

# cơ cấu tuổi xe theo kịch bản (để thấy S4 làm lệch cơ cấu)
age_mix = pd.DataFrame({name: v[m].groupby("Registration_Age").size() / m.sum() * 100 for name, m in scen.items()})
age_mix.to_csv(TAB / "08d_age_mix_by_scenario.csv")
nonlux_age_mix = pd.DataFrame({name: v[m & (v.Segment == "Non-luxury")].groupby("Registration_Age").size()
                               / (m & (v.Segment == "Non-luxury")).sum() * 100 for name, m in scen.items()})
print("\n% Non-luxury ở tuổi 25 theo kịch bản:", nonlux_age_mix.loc[25].round(2).to_dict())

# ---------------------------------------------------------------- hình 08a: cơ cấu tuổi Non-luxury
fig, ax = plt.subplots(figsize=(10, 4.5))
for name, col in [("S2 −dup −implausible (đề xuất)", C1), ("S3 = S2 −NaN/Unknown (listwise)", C3),
                  ("S4 = S2 −giá sàn", C2)]:
    ax.plot(nonlux_age_mix.index, nonlux_age_mix[name], color=col, marker="o", markersize=3.5, label=name)
ax.set_xlabel("Registration_Age (năm)")
ax.set_ylabel("% listing Non-luxury")
ax.set_ylim(0, None)
ax.set_title("Cơ cấu tuổi xe Non-luxury: loại dòng giá sàn (S4) làm mất xe cũ; listwise (S3) giữ nguyên cơ cấu")
ax.legend(loc="lower left")
fig.tight_layout()
fig.savefig(FIG / "fig_08a_scenarios_age_mix.png")
plt.close(fig)

# ---------------------------------------------------------------- hình 08b: median price theo kịch bản
fig, ax = plt.subplots(figsize=(10, 4.5))
y = np.arange(len(sc))
ax.barh(y - 0.19, sc["median_non_luxury"], height=0.36, color=SEG_COLORS["Non-luxury"], label="Non-luxury")
ax.barh(y + 0.19, sc["median_luxury"], height=0.36, color=SEG_COLORS["Luxury"], label="Luxury")
for yi, (a, b, n) in enumerate(zip(sc["median_non_luxury"], sc["median_luxury"], sc["n"])):
    ax.annotate(f"{a:,.0f}", (a, yi - 0.19), xytext=(3, 0), textcoords="offset points", va="center", fontsize=7.5,
                color=INK2)
    ax.annotate(f"{b:,.0f}   (n = {n:,})", (b, yi + 0.19), xytext=(3, 0), textcoords="offset points", va="center",
                fontsize=7.5, color=INK2)
ax.set_yticks(y)
ax.set_yticklabels(sc["scenario"], fontsize=8.5)
ax.invert_yaxis()
thousands(ax, "x")
ax.set_xlim(0, sc["median_luxury"].max() * 1.45)
ax.set_xlabel("Median Car_Price (Rupees)")
ax.set_title("Median Car_Price theo segment dưới từng kịch bản loại dòng")
ax.grid(axis="y", visible=False)
ax.legend(loc="lower right")
fig.tight_layout()
fig.savefig(FIG / "fig_08b_scenarios_price.png")
plt.close(fig)
print("\nĐã lưu hình: fig_08a, fig_08b")
