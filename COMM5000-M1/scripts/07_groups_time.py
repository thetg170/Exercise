"""
07_groups_time.py — Mục 8 EDA: phân tích theo nhóm và theo thời gian / tuổi xe.

Mục đích :
  - Theo City, Brand, Model, Segment: số listing, % , median/mean Car_Price, % Luxury.
  - Thời gian: Year (năm sản xuất) và Registration_Age (= 2025 − Year): số listing theo năm, median price
    theo năm/tuổi cho TỪNG segment; tốc độ giảm median price mỗi năm (đường thẳng mô tả fit trên các median,
    tuổi 1–20 để tránh vùng bị giá sàn chặn); Kms_Driven theo tuổi; Owner_Type theo tuổi.
Input    : data_interim.parquet
Output   : tables/07*.csv; figures/fig_07a_city.png, fig_07b_model_price.png, fig_07c_price_by_year.png,
           fig_07d_kms_by_age.png
Bước EDA : Mục 8 — nhóm & thời gian. View 'clean' = bỏ exact duplicates + implausible (chỉ để mô tả).
"""
import numpy as np
import pandas as pd

from _common import (load_raw, analysis_view, TAB, FIG, SEG_COLORS, LUXURY_BRANDS, setup_plot, thousands, C1,
                     INK, INK2, HIGHLIGHT_GREY, pct)

plt = setup_plot()
raw = load_raw()
v = analysis_view(raw)
v["is_dup_extra"] = raw.duplicated(keep="first")
c = v[~v.is_dup_extra & ~v.imp_any].copy()
N, NC = len(v), len(c)
print(f"view 'all' n = {N:,}; view 'clean' n = {NC:,}")


def summarise(d, g):
    t = d.groupby(g).agg(n=("Car_Price", "size"), mean_price=("Car_Price", "mean"),
                         median_price=("Car_Price", "median"),
                         pct_luxury=("Segment", lambda x: 100 * (x == "Luxury").mean()))
    t.insert(1, "pct_of_total", 100 * t["n"] / len(d))
    seg_med = d.groupby([g, "Segment"])["Car_Price"].median().unstack().add_prefix("median_")
    return t.join(seg_med)


# ---------------------------------------------------------------- City
city = summarise(c, "City")
city.to_csv(TAB / "07a_city_summary.csv")
with pd.option_context("display.float_format", lambda x: f"{x:,.2f}", "display.width", 250):
    print("\n=== City (view 'clean') ===")
    print(city.to_string())
known = city.drop("Unknown", errors="ignore")
print(f"Median price giữa các city (không tính Unknown): {known.median_price.min():,.0f} – {known.median_price.max():,.0f} "
      f"(chênh {100 * (known.median_price.max() / known.median_price.min() - 1):.2f}%); "
      f"% luxury: {known.pct_luxury.min():.2f}% – {known.pct_luxury.max():.2f}%")

# ---------------------------------------------------------------- Brand & Model
brand = summarise(c, "Brand").sort_values("median_price", ascending=False)
brand.to_csv(TAB / "07b_brand_summary.csv")
with pd.option_context("display.float_format", lambda x: f"{x:,.2f}", "display.width", 250):
    print("\n=== Brand (view 'clean') ===")
    print(brand[["n", "pct_of_total", "mean_price", "median_price"]].to_string())
model = c.groupby(["Segment", "Brand", "Model"])["Car_Price"].agg(n="size", median="median", mean="mean")
model.to_csv(TAB / "07c_model_summary.csv")
bm = model.reset_index().groupby("Brand")["median"].agg(["min", "max"])
bm["max/min"] = bm["max"] / bm["min"]
print("\nChênh lệch median giữa các Model TRONG cùng Brand (max/min):")
print(bm.round(3).sort_values("max/min", ascending=False).to_string())
lux_min = model.loc["Luxury", "median"].min()
nonlux_max = model.loc["Non-luxury", "median"].max()
print(f"Model Luxury có median thấp nhất = {lux_min:,.0f}; Model Non-luxury có median cao nhất = {nonlux_max:,.0f} "
      f"-> {'hai segment KHÔNG chồng lấn ở cấp Model' if lux_min > nonlux_max else 'có chồng lấn'}")

# ---------------------------------------------------------------- Segment
seg = summarise(c, "Segment")
seg.to_csv(TAB / "07d_segment_summary.csv")

# ---------------------------------------------------------------- thời gian / tuổi
print("\n=== Thời gian: Year & Registration_Age ===")
yr = c.groupby(["Year", "Segment"])["Car_Price"].agg(["size", "median", "mean"]).unstack()
yr.to_csv(TAB / "07e_price_by_year_segment.csv")
cnt = v["Year"].value_counts().sort_index()
print(f"Số listing / năm sản xuất (view all): min {cnt.min():,} ({cnt.idxmin()}) – max {cnt.max():,} ({cnt.idxmax()}); "
      f"CV = {cnt.std() / cnt.mean():.4f} -> phân bố gần như đều")
age_med = c.groupby(["Registration_Age", "Segment"])["Car_Price"].median().unstack()
rows = []
for s in ["Luxury", "Non-luxury"]:
    for lo, hi in [(1, 20), (1, 25)]:
        a = age_med.loc[lo:hi, s]
        # (sửa lỗi lần chạy đầu: phép tính với a.index trả về pandas Index, không có .var() -> dùng numpy array)
        x = a.index.to_numpy(dtype=float)
        b1, b0 = np.polyfit(x, a.values, 1)
        resid = a.values - (b0 + b1 * x)
        bl = np.polyfit(x, np.log(a.values), 1)[0]
        rows.append({"Segment": s, "ages": f"{lo}-{hi}", "slope_median_Rs_per_year": b1,
                     "R2_linear_on_medians": 1 - resid.var() / a.values.var(),
                     "slope_log_median_pct_per_year": 100 * (np.exp(bl) - 1),
                     "median_age1": a.iloc[0], f"median_age{hi}": a.iloc[-1]})
slopes = pd.DataFrame(rows)
with pd.option_context("display.float_format", lambda x: f"{x:,.3f}", "display.width", 250):
    print("Đường thẳng mô tả fit trên median price theo tuổi (mỗi tuổi 1 điểm):")
    print(slopes.to_string(index=False))
slopes.to_csv(TAB / "07f_median_price_age_slopes.csv", index=False)
print("Chênh lệch median Luxury − Non-luxury theo tuổi (Rupees):",
      {a: f"{(age_med.loc[a, 'Luxury'] - age_med.loc[a, 'Non-luxury']):,.0f}" for a in [1, 5, 10, 15, 20, 25]})

kms_age = c.groupby("Registration_Age")["Kms_Driven"].describe(percentiles=[0.1, 0.5, 0.9])
kms_age.to_csv(TAB / "07g_kms_by_age.csv")
print("\nKms_Driven theo tuổi (view clean): median / tuổi =",
      {a: f"{kms_age.loc[a, '50%'] / a:,.0f}" for a in [1, 5, 10, 20, 25]})
own = c.groupby("Owner_Type")["Registration_Age"].mean()
print("Tuổi xe trung bình theo Owner_Type:", own.round(2).to_dict())
acc = c.groupby("Accidents")["Registration_Age"].mean()
print("Tuổi xe trung bình theo Accidents:", acc.round(2).to_dict())
kms_seg = c.groupby("Segment")["Kms_Driven"].median()
print("Median Kms_Driven theo segment:", kms_seg.round(0).to_dict())

# ---------------------------------------------------------------- hình 07a: city
t = city.copy()
fig, ax = plt.subplots(figsize=(10, 4.8))
y = np.arange(len(t))
ax.barh(y - 0.19, t["median_Non-luxury"], height=0.36, color=SEG_COLORS["Non-luxury"], label="Non-luxury")
ax.barh(y + 0.19, t["median_Luxury"], height=0.36, color=SEG_COLORS["Luxury"], label="Luxury")
ax.set_yticks(y)
ax.set_yticklabels([f"{i}  (n={n:,})" for i, n in zip(t.index, t["n"])])
ax.invert_yaxis()
thousands(ax, "x")
ax.set_xlabel("Median Car_Price (Rupees)")
ax.set_title("Median Car_Price theo City và segment (view 'clean')")
ax.grid(axis="y", visible=False)
ax.legend(loc="lower right")
fig.tight_layout()
fig.savefig(FIG / "fig_07a_city.png")
plt.close(fig)

# ---------------------------------------------------------------- hình 07b: model
m = model.reset_index().sort_values(["Segment", "median"], ascending=[True, True])
fig, ax = plt.subplots(figsize=(9, 10))
ax.barh([f"{b} {mm}" for b, mm in zip(m.Brand, m.Model)], m["median"],
        color=[SEG_COLORS[s] for s in m.Segment], height=0.6)
thousands(ax, "x")
ax.set_xlabel("Median Car_Price (Rupees)")
ax.set_title("Median Car_Price theo Model (cam = Luxury, xanh = Non-luxury; view 'clean')")
ax.grid(axis="y", visible=False)
ax.tick_params(axis="y", labelsize=8)
fig.tight_layout()
fig.savefig(FIG / "fig_07b_model_price.png")
plt.close(fig)

# ---------------------------------------------------------------- hình 07c: price theo Year
fig, ax = plt.subplots(figsize=(10, 4.8))
for s in ["Non-luxury", "Luxury"]:
    ax.plot(yr.index, yr[("median", s)], color=SEG_COLORS[s], marker="o", markersize=3.5, label=f"{s} — median")
    r = slopes[(slopes.Segment == s) & (slopes.ages == "1-20")].iloc[0]
    # (chỉnh sau lần xem đầu: nhãn đặt ở đầu trái đè lên đường -> chuyển sang đầu mút bên phải)
    ax.annotate(f"{s}\n{r.slope_median_Rs_per_year:,.0f} Rs / năm tuổi\n(fit tuổi 1–20)",
                (yr.index[-1], yr[("median", s)].iloc[-1]), fontsize=8.5, color=INK2, xytext=(8, 0),
                textcoords="offset points", va="center")
thousands(ax)
ax.set_ylim(0, None)
ax.set_xlim(1999, 2030)
ax.set_xlabel("Year (năm sản xuất); Registration_Age = 2025 − Year")
ax.set_ylabel("Median Car_Price (Rupees)")
ax.set_title("Median Car_Price theo năm sản xuất — hai đường gần song song theo Rupees (view 'clean')")
ax.legend(loc="upper left", bbox_to_anchor=(0, 0.88))
fig.tight_layout()
fig.savefig(FIG / "fig_07c_price_by_year.png")
plt.close(fig)

# ---------------------------------------------------------------- hình 07d: Kms theo tuổi
fig, ax = plt.subplots(figsize=(10, 4.5))
ax.fill_between(kms_age.index, kms_age["10%"], kms_age["90%"], color=C1, alpha=0.12, linewidth=0, label="P10–P90")
ax.plot(kms_age.index, kms_age["50%"], color=C1, marker="o", markersize=3.5, label="median")
thousands(ax)
ax.set_xlabel("Registration_Age (năm)")
ax.set_ylabel("Kms_Driven")
ax.set_title("Kms_Driven tăng tuyến tính theo tuổi xe (view 'clean')")
ax.legend(loc="upper left")
fig.tight_layout()
fig.savefig(FIG / "fig_07d_kms_by_age.png")
plt.close(fig)
print("\nĐã lưu hình: fig_07a..fig_07d")
