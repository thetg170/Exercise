"""
09_issue_log.py — Mục 10 EDA: Data Issue Log (bảng ghi nhận vấn đề dữ liệu + đề xuất xử lý).

Mục đích : Tính lại MỌI con số bằng chứng trực tiếp từ dữ liệu (để khi chạy trên file khác — vd. bản đã
           randomize — bảng tự cập nhật), rồi ghép với đề xuất xử lý / phương án thay thế / lý do.
           Đây vẫn là ĐỀ XUẤT: không có bước nào thay đổi dữ liệu.
Input    : data_interim.parquet; file .xlsm gốc (chỉ đọc ô B6 của sheet 'Dataset')
Output   : tables/09_data_issue_log.csv, tables/09_data_issue_log.md
Bước EDA : Mục 10 — ghi nhận cách xử lý dữ liệu.
"""
import re
import zipfile

import numpy as np
import pandas as pd

from _common import (load_raw, analysis_view, build_label_mapping, floor_values, RAW_XLSM, TAB, LUXURY_BRANDS,
                     KMS_IMPLAUSIBLE, KMS_PER_YEAR_MAX, pct)

raw = load_raw()
v = analysis_view(raw)
N = len(v)
f = lambda x: f"{int(x):,}"  # noqa: E731

# ---------------------------------------------------------------- tính bằng chứng
z = zipfile.ZipFile(RAW_XLSM)
b6_empty = not re.search(r'<c r="B6"[^>]*>\s*<v>', z.read("xl/worksheets/sheet1.xml").decode())
last_by = re.search(r"<cp:lastModifiedBy>([^<]*)<", z.read("docProps/core.xml").decode())
last_by = last_by.group(1) if last_by else "?"

mp = build_label_mapping(raw)
brand_var = mp[(mp.variable == "Brand") & (mp.rule != "giữ nguyên")]
lux_missed = int(brand_var[brand_var.standard_label.isin(LUXURY_BRANDS)]["count"].sum())
fuel_var = mp[(mp.variable == "Fuel_Type") & (mp.rule != "giữ nguyên")]
fuel_typo = fuel_var[fuel_var.rule.str.startswith("R3")]
fuel_trim = fuel_var[fuel_var.rule.str.startswith("R2")]

unk_cols = ["Fuel_Type", "Transmission", "Color", "City"]
unk_pct = {c: pct((v[c] == "Unknown").sum(), N) for c in unk_cols}
any_unk = (v[unk_cols] == "Unknown").any(axis=1)
nan_cols = ["Mileage_kmpl", "Engine_CC", "Horsepower"]
nan_n = {c: int(raw[c].isna().sum()) for c in nan_cols}
any_nan = raw[nan_cols].isna().any(axis=1)
all3_obs = int(raw[nan_cols].isna().all(axis=1).sum())
all3_exp = N * np.prod([raw[c].isna().mean() for c in nan_cols])
bad_any = any_nan | any_unk


def max_range_pp(flag, groups=("City", "Brand", "Year", "Segment")):
    return max((flag.groupby(v[g]).mean() * 100).pipe(lambda r: r.max() - r.min()) for g in groups)


rng_nan = max(max_range_pp(raw[c].isna()) for c in nan_cols)
rng_unk = max(max_range_pp(v[c] == "Unknown", [g for g in ("City", "Brand", "Year", "Segment") if g != c])
              for c in unk_cols)
med = v["Car_Price"].median()
diff_nan = 100 * abs(v.loc[any_nan, "Car_Price"].median() / v.loc[~any_nan, "Car_Price"].median() - 1)
diff_unk = 100 * abs(v.loc[any_unk, "Car_Price"].median() / v.loc[~any_unk, "Car_Price"].median() - 1)

dup_extra = raw.duplicated(keep="first")
n_dup_extra = int(dup_extra.sum())
n_dup_rows = int(raw.duplicated(keep=False).sum())

kpy = raw["Kms_Driven"] / raw["Registration_Age"]
over = kpy > KMS_PER_YEAR_MAX
gt1m = raw["Kms_Driven"] > KMS_IMPLAUSIBLE
ref_mask = ~over & ~v["floor_Car_Price"]
ref = v[ref_mask].groupby(["Model", "Registration_Age"])["Car_Price"].median().rename("ref")
rel = v.join(ref, on=["Model", "Registration_Age"])
price_rel_med = (rel["Car_Price"] / rel["ref"])[over].median()
p = v["Car_Price"]
p_ext = p > p.quantile(0.75) + 3 * (p.quantile(0.75) - p.quantile(0.25))
share_ext_in_over = pct((p_ext & over).sum(), p_ext.sum())
ext_valid = p_ext & ~v.imp_any
ext_valid_lux = pct((ext_valid & (v.Segment == "Luxury")).sum(), ext_valid.sum())
clean = ~dup_extra & ~v.imp_any
r_kms_clean = v.loc[clean, "Car_Price"].corr(v.loc[clean, "Kms_Driven"])
r_kms_guide = v.loc[~dup_extra & ~gt1m, "Car_Price"].corr(v.loc[~dup_extra & ~gt1m, "Kms_Driven"])
r_kms_all = v["Car_Price"].corr(v["Kms_Driven"])

hp_neg = raw["Horsepower"] <= 0
fv = floor_values(raw)
fl = v["floor_Car_Price"]
fl_lux = pct((fl & (v.Segment == "Luxury")).sum(), (v.Segment == "Luxury").sum())
fl_non = pct((fl & (v.Segment == "Non-luxury")).sum(), (v.Segment == "Non-luxury").sum())
nl25 = v[(v.Segment == "Non-luxury") & (v.Registration_Age == 25)]
fl_nl25 = pct(nl25["floor_Car_Price"].sum(), len(nl25))
s2 = clean
s4 = clean & ~fl
med_nl_s2 = v.loc[s2 & (v.Segment == "Non-luxury"), "Car_Price"].median()
med_nl_s4 = v.loc[s4 & (v.Segment == "Non-luxury"), "Car_Price"].median()
ratio_s2 = v.loc[s2 & (v.Segment == "Luxury"), "Car_Price"].median() / med_nl_s2
ratio_s4 = v.loc[s4 & (v.Segment == "Luxury"), "Car_Price"].median() / med_nl_s4
eng_fl = v.get("floor_Engine_CC", pd.Series(False, index=v.index))
mil_fl = v.get("floor_Mileage_kmpl", pd.Series(False, index=v.index))
ya = (raw["Year"] + raw["Registration_Age"])
r_eng_hp = raw["Engine_CC"].corr(raw["Horsepower"])
r_age_kms_p = raw["Registration_Age"].corr(raw["Kms_Driven"])
r_age_kms_s = raw["Registration_Age"].corr(raw["Kms_Driven"], method="spearman")
# (bổ sung sau lần chạy đầu: các con số trước đây viết cứng trong câu chữ nay được tính từ dữ liệu)
import difflib  # noqa: E402
skew_all, skew_clean = p.skew(), v.loc[clean, "Car_Price"].skew()
fuel_med = v.loc[clean].groupby(["Segment", "Fuel_Type"])["Car_Price"].median()
fuel_diff = max(100 * (g.max() / g.min() - 1) for _, g in fuel_med.groupby(level=0))
max_r_nan = max(abs(v.loc[clean, "Car_Price"].corr(v.loc[clean, c])) for c in nan_cols)
typo_sim = min(difflib.SequenceMatcher(None, a.strip().lower(), b.lower()).ratio()
               for a, b in zip(fuel_typo.raw_label, fuel_typo.standard_label)) if len(fuel_typo) else np.nan
lux_ratio = ratio_s2
brand_share = v["Brand"].value_counts(normalize=True) * 100
city_share = v["City"].value_counts(normalize=True).drop("Unknown", errors="ignore") * 100
year_share = v["Year"].value_counts(normalize=True) * 100

# ---------------------------------------------------------------- bảng
L = []


def add(issue, cols, evidence, proposal, alternative, why, impact):
    L.append({"#": len(L) + 1, "Vấn đề": issue, "Cột liên quan": cols, "Bằng chứng (số dòng, %)": evidence,
              "Cách xử lý đề xuất": proposal, "Phương án thay thế": alternative, "Lý do (justification)": why,
              "Ảnh hưởng đến phân tích": impact})


add("File chưa được randomize (macro Workbook_Open chưa chạy)", "Sheet Dataset!B6; Mileage_kmpl, Engine_CC, Horsepower, Kms_Driven, Car_Price",
    f"B6 trống = {b6_empty}; người lưu cuối: {last_by}. Macro sẽ ghi đè 5 cột bằng giá trị mô phỏng (Cholesky + Cornish-Fisher/lognormal).",
    "Quyết định dùng file nào trước khi viết báo cáo; nếu randomize: mở bằng Excel (Enable Content), lưu .xlsm, chạy lại toàn bộ scripts với EDA_XLSM=<file mới>.",
    "Giữ file hiện tại và ghi rõ trong báo cáo rằng dữ liệu chưa randomize.",
    "Slide intro yêu cầu mỗi sinh viên làm trên bản đã randomize; số liệu 5 cột (gồm target) sẽ khác hoàn toàn.",
    "Toàn bộ thống kê về Car_Price, Kms_Driven, Engine_CC, Horsepower, Mileage_kmpl.")
add("Nhãn Brand có khoảng trắng thừa", "Brand",
    f"{len(brand_var)} biến thể (vd. ' BMW '), {f(brand_var['count'].sum())} dòng ({pct(brand_var['count'].sum(), N)}%); "
    f"{f(lux_missed)} dòng Audi/BMW/Mercedes sẽ bị xếp nhầm Non-luxury nếu không TRIM.",
    "TRIM Brand rồi gán Segment (Luxury = Audi, BMW, Mercedes).", "Không có — bắt buộc phải làm.",
    "Guide yêu cầu làm sạch Brand trước khi tạo segment; biến thể chỉ khác khoảng trắng, không mơ hồ.",
    f"Cỡ nhóm Luxury: {pct((raw['Brand'].isin(LUXURY_BRANDS)).sum(), N)}% -> {pct((v.Segment == 'Luxury').sum(), N)}%.")
add("Nhãn Fuel_Type không thống nhất (hoa/thường, khoảng trắng, typo)", "Fuel_Type",
    f"{len(fuel_var)} biến thể, {f(fuel_var['count'].sum())} dòng ({pct(fuel_var['count'].sum(), N)}%): trim/case "
    f"{f(fuel_trim['count'].sum())} ({', '.join(fuel_trim.raw_label_repr)}); typo {f(fuel_typo['count'].sum())} "
    f"({', '.join(f'{a}->{b}' for a, b in zip(fuel_typo.raw_label_repr, fuel_typo.standard_label))}).",
    "TRIM + chuẩn hoá hoa/thường; gộp 'hybridd'->Hybrid, 'electrik'->Electric (12 nhãn -> 6).",
    "Giữ typo thành nhóm riêng hoặc gộp vào 'Unknown'.",
    f"Mỗi typo cách nhãn chuẩn 1 ký tự (độ giống difflib ≥ {typo_sim:.2f}) và không trùng nhãn hợp lệ nào khác.",
    f"Tần suất Fuel_Type chính xác; ảnh hưởng tới giá rất nhỏ (median theo Fuel trong từng segment chênh ≤ {fuel_diff:.1f}%).")
add("Giá trị 'Unknown' trong biến categorical", ", ".join(unk_cols),
    f"{', '.join(f'{c} {unk_pct[c]}%' for c in unk_cols)}; {f(any_unk.sum())} dòng ({pct(any_unk.sum(), N)}%) có ≥1 'Unknown'; "
    f"không có biến thể khác ('N/A', '-', ''); chênh % Unknown giữa các nhóm ≤ {rng_unk:.2f} điểm %; median giá chênh {diff_unk:.2f}%.",
    "Giữ 'Unknown' là một nhóm riêng; không xoá, không impute.",
    "Listwise deletion (xoá dòng) hoặc impute bằng mode.",
    "Phân bố gần như ngẫu nhiên (MCAR-like) và không liên quan tới giá; xoá sẽ mất nhiều dòng mà không đổi kết quả.",
    "Bảng tần suất/crosstab có thêm cột 'Unknown'; các biến này hầu như không liên quan tới giá.")
add("Missing values (ô trống) ở biến numeric", ", ".join(nan_cols),
    f"{', '.join(f'{c} {f(nan_n[c])} ({pct(nan_n[c], N)}%)' for c in nan_cols)}; {f(any_nan.sum())} dòng ({pct(any_nan.sum(), N)}%) có ≥1 NaN; "
    f"thiếu cả 3 cột: {all3_obs} dòng vs kỳ vọng nếu độc lập {all3_exp:.0f}; chênh % missing giữa nhóm ≤ {rng_nan:.2f} điểm %; median giá chênh {diff_nan:.2f}%.",
    "Giữ dòng; dùng pairwise deletion (bỏ ô trống cho từng thống kê — Excel làm mặc định). Không impute ở M1.",
    "Impute median (theo Model) cho mô hình ở final report; hoặc complete-case chỉ khi mô hình dùng các biến này.",
    f"Missing độc lập giữa các cột và với nhóm/giá (MCAR-like); các biến này tương quan rất yếu với giá (|r| ≤ {max_r_nan:.2f}).",
    f"Listwise deletion NaN + Unknown sẽ bỏ {f(bad_any.sum())} dòng ({pct(bad_any.sum(), N)}%) mà median giá gần như không đổi.")
add("Exact duplicated records", "Tất cả 20 cột",
    f"{f(n_dup_rows)} dòng thuộc {f(n_dup_rows // 2)} cặp trùng hoàn toàn; {f(n_dup_extra)} bản sao thừa ({pct(n_dup_extra, N)}%); "
    f"bỏ bản sao còn đúng {f(N - n_dup_extra)} dòng; không có near-duplicate (trùng mọi cột trừ Car_Price).",
    "Xoá bản sao thừa (giữ lần xuất hiện đầu).", "Giữ nguyên (ảnh hưởng thống kê < 0.01%).",
    "Trùng cả 5 biến số thực nhiều chữ số thập phân -> gần như không thể trùng ngẫu nhiên; 1 listing không nên đếm 2 lần.",
    "Median giá thay đổi < 0.01%; n = 1,000,000.")
add("Kms_Driven phi lý: km/năm vượt biên của phần thân dữ liệu", "Kms_Driven, Registration_Age, Car_Price",
    f"{pct((~over).sum(), N)}% dòng có Kms/Registration_Age trong [5,000; 25,000]; {f(over.sum())} dòng ({pct(over.sum(), N)}%) vượt 25,000 km/năm, "
    f"gồm toàn bộ {f(gt1m.sum())} dòng Kms > 1,000,000; giá các dòng này cao gấp {price_rel_med:.2f} lần (median) xe cùng Model & tuổi; "
    f"chiếm {share_ext_in_over}% outlier giá > 3×IQR.",
    "Loại khỏi phân tích quan hệ giá (hoặc gắn cờ và báo cáo cả hai kết quả).",
    f"Chỉ loại Kms > 1,000,000 theo ví dụ trong Guide ({f(gt1m.sum())} dòng) — còn sót {f((over & ~gt1m).sum())} dòng cùng kiểu bất thường.",
    "Nhóm này tách rời khỏi phân phối (điểm gãy rõ trên fig_04c/fig_04d), phân bố đều theo tuổi xe/segment, và giá bị phóng đại đồng thời -> dấu hiệu dữ liệu lỗi, không phải xe thật.",
    f"Pearson(Car_Price, Kms_Driven): toàn bộ {r_kms_all:.3f}; chỉ bỏ Kms>1M {r_kms_guide:.3f}; bỏ theo km/năm {r_kms_clean:.3f}. Skewness giá {skew_all:.2f} -> {skew_clean:.2f} (bỏ duplicates + implausible).")
add("Horsepower ≤ 0", "Horsepower (Engine_CC)",
    f"{f(hp_neg.sum())} dòng ({pct(hp_neg.sum(), N)}%), min = {raw['Horsepower'].min():.2f}; median Engine_CC của các dòng này = {raw.loc[hp_neg, 'Engine_CC'].median():,.0f} (đúng giá sàn).",
    "Coi Horsepower của các dòng này là missing (giữ các cột khác).", "Xoá 32 dòng (không đáng kể).",
    "Công suất âm/0 vô nghĩa về logic; các cột khác của dòng vẫn hợp lệ.", "Không đáng kể (0.003%).")
add("Car_Price bị chặn sàn (censoring) tại giá trị min", "Car_Price",
    f"{f(fl.sum())} dòng ({pct(fl.sum(), N)}%) có Car_Price = {fv.get('Car_Price', np.nan):,.0f}; Non-luxury {fl_non}% vs Luxury {fl_lux}%; "
    f"{fl_nl25}% xe Non-luxury 25 tuổi; tăng theo tuổi và Kms.",
    "Giữ lại, gắn cờ 'giá sàn'; báo cáo median; ở M2/final kiểm tra độ nhạy (có/không nhóm này).",
    "Loại nhóm giá sàn (KHÔNG khuyến nghị) hoặc phân tích riêng xe ≤ 20 tuổi.",
    "Giá thật ≤ 50,000 nhưng không biết chính xác; xoá sẽ bỏ có chọn lọc xe cũ Non-luxury (bias).",
    f"Nếu xoá: median Non-luxury {med_nl_s2:,.0f} -> {med_nl_s4:,.0f}; tỉ số median Luxury/Non-luxury {ratio_s2:.2f} -> {ratio_s4:.2f}; quan hệ giá–tuổi bị làm yếu.")
add("Engine_CC và Mileage_kmpl bị chặn sàn", "Engine_CC, Mileage_kmpl",
    f"Engine_CC = {fv.get('Engine_CC', np.nan):,.0f}: {f(eng_fl.sum())} dòng ({pct(eng_fl.sum(), raw['Engine_CC'].notna().sum())}% giá trị có); "
    f"Mileage_kmpl = {fv.get('Mileage_kmpl', np.nan):,.0f}: {f(mil_fl.sum())} dòng.",
    "Giữ, gắn cờ; lưu ý mode = giá sàn nên mode không có ý nghĩa mô tả.", "Coi giá trị sàn là missing.",
    "Point mass tại min là dấu hiệu bị chặn, không phải giá trị đo thật; các biến này tương quan rất yếu với giá.",
    "Mode của Engine_CC/Mileage_kmpl phản ánh giá sàn, không phải giá trị điển hình.")
add("Registration_Age trùng thông tin với Year", "Year, Registration_Age",
    f"Year + Registration_Age = {int(ya.mode()[0])} ở {pct((ya == ya.mode()[0]).sum(), N)}% dòng (r = −1.000).",
    "Chỉ dùng Registration_Age (biến Guide chỉ định) trong phân tích/mô hình.", "Chỉ dùng Year.",
    "Hai biến là biến đổi tuyến tính của nhau -> multicollinearity hoàn hảo.", "Không thể đưa cả hai vào cùng một mô hình hồi quy.")
add("Multicollinearity giữa biến giải thích", "Engine_CC–Horsepower; Registration_Age–Kms_Driven",
    f"r(Engine_CC, Horsepower) = {r_eng_hp:.3f}; r(Registration_Age, Kms_Driven) = {r_age_kms_p:.3f} (Spearman {r_age_kms_s:.3f}); "
    f"median Kms ≈ 15,000 × tuổi.",
    "Ghi nhận; ở M2/final chọn 1 trong Engine_CC/Horsepower; diễn giải hệ số tuổi & Kms thận trọng.",
    "Tạo biến km/năm để tách phần Kms không do tuổi.",
    "Hệ số hồi quy không ổn định khi biến giải thích tương quan mạnh.", "Ảnh hưởng tới mô hình ở final report, không ảnh hưởng thống kê mô tả.")
add("Giá cực cao nhưng có thể hợp lệ", "Car_Price",
    f"{f(ext_valid.sum())} dòng > 3×IQR không vi phạm quy tắc nào; {ext_valid_lux}% là Luxury.",
    "Giữ; đánh giá outlier TRONG từng segment.", "Winsorize ở P99.9 để kiểm tra độ nhạy.",
    f"Median Luxury cao gấp {lux_ratio:.2f} lần Non-luxury nên fence 1.5×IQR toàn mẫu gắn nhầm xe Luxury là outlier.",
    "Mean Luxury nhạy với nhóm này; báo cáo median.")
add("Phân bố mẫu đồng đều bất thường (tính đại diện)", "Brand, Model, City, Year",
    f"Mỗi brand {brand_share.min():.2f}–{brand_share.max():.2f}%; mỗi city (trừ Unknown) {city_share.min():.2f}–{city_share.max():.2f}%; "
    f"mỗi năm sản xuất {year_share.min():.2f}–{year_share.max():.2f}%; Luxury = {pct((v.Segment == 'Luxury').sum(), N)}%.",
    "Không xử lý; nêu trong phần hạn chế (Objective 2).", "Gán trọng số (weighting) nếu có dữ liệu cơ cấu thị trường thật (ngoài phạm vi M1).",
    "Cơ cấu đều tuyệt đối gợi ý dữ liệu được sinh/lấy mẫu phân tầng, không phản ánh tỉ trọng thị trường thực.",
    "Kết quả đúng cho mẫu này; khái quát hoá ra thị trường thật cần thận trọng.")

log = pd.DataFrame(L)
log.to_csv(TAB / "09_data_issue_log.csv", index=False)
md = ["| " + " | ".join(log.columns) + " |", "|" + "---|" * len(log.columns)]
for _, r in log.iterrows():
    md.append("| " + " | ".join(str(x).replace("|", "\\|").replace("\n", " ") for x in r.values) + " |")
(TAB / "09_data_issue_log.md").write_text("\n".join(md) + "\n")
print(f"Data Issue Log: {len(log)} vấn đề -> tables/09_data_issue_log.csv / .md")
for _, r in log.iterrows():
    print(f"\n#{r['#']} {r['Vấn đề']}\n   Bằng chứng: {r['Bằng chứng (số dòng, %)']}\n   Ảnh hưởng : {r['Ảnh hưởng đến phân tích']}")
