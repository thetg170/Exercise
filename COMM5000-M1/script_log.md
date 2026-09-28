# Script log — COMM5000 M1 EDA (Used Cars)

- **Dữ liệu:** `[22_9] COMM5000-Used_Car_Price_Prediction.xlsm`. Đây là file **CHƯA randomize**: ô B6 của sheet `Dataset` đang trống. Người dùng đã quyết định làm EDA trên file này.
- **Môi trường:** `.venv/` (Python 3.11). Danh sách thư viện ở `requirements.txt`: pandas 3.0.6, numpy 2.4.6, openpyxl 3.1.5, python-calamine 0.8.2, pyarrow 25.0.1, matplotlib 3.11.2, oletools 0.60.2.
- **Chạy lại toàn bộ:** `bash scripts/run_all.sh`, mất khoảng 66 giây. Log của từng script nằm trong `logs/NN_*.log`.
- **Chạy trên file khác** (ví dụ bản đã randomize): `EDA_XLSM="/đường/dẫn/file.xlsm" bash scripts/run_all.sh`. Script 00 sẽ tạo lại `data_interim.parquet`. Hàm `load_raw()` đối chiếu đường dẫn, kích thước và thời gian sửa đổi của file nguồn, nên không bao giờ dùng nhầm parquet cũ.
- **File gốc không bị sửa:** mã SHA-256 trước và sau khi chạy giống nhau (`3493ae06…c426f1`). Xem `logs/raw_file_sha256_before.txt` và `logs/raw_file_sha256_after.txt`.
- **Seed:** `SEED = 5000` (trong `_common.py`). Chỉ có một chỗ lấy mẫu: scatter ở script 05, n = 5,000. Mọi thống kê và các hình còn lại đều dùng toàn bộ 1,005,000 dòng.
- **Nguyên tắc:** không xóa, không impute, không ghi đè dữ liệu. Việc chuẩn hóa nhãn, tạo Segment và các cờ `imp_*` / `floor_*` chỉ tạo bản copy trong bộ nhớ (hàm `analysis_view()` trong `_common.py`). Các "view" `clean` / `clean_nofloor` chỉ dùng để so sánh độ nhạy.

---

### `_common.py` — module dùng chung (không phải một bước EDA)
- **Mục đích:** chứa đường dẫn, seed, định nghĩa Luxury và hàm `load_raw()`. Ngoài ra có:
  - `build_label_mapping()`: quy tắc R1 unknown-token, R2 trim/case, R3 typo fuzzy (difflib ≥ 0.8 cho nhóm < 1%).
  - `analysis_view()`, `implausible_flags()`, `floor_flags()`.
  - Style biểu đồ, với bảng màu categorical đã chạy validator CVD: blue/orange/aqua PASS.
- **Thay đổi trong quá trình làm:**
  1. Thêm biến môi trường `EDA_XLSM` và file chữ ký nguồn cho parquet.
  2. Thêm các cờ `floor_*` sau khi script 02 phát hiện point mass.
  3. Thêm cờ `imp_kms_per_year_gt_25k` sau khi script 04 phát hiện biên km/năm.
  4. Đổi font weight từ `semibold` sang `bold` vì font hệ thống không có semibold.

### 00_load_and_inspect.py — Bước 0: kiểm tra file
- **Mục đích:** liệt kê các phần trong zip, sheet, kích thước, merged cells; đọc sheet mô tả; liệt kê VBA bằng olevba (chỉ đọc, không chạy); quét XML; đo tốc độ đọc; lưu parquet.
- **Kết quả chính:**
  - Có 2 sheet. `Dataset` (B3:S7, 5 merged cells) là mô tả / data dictionary gốc. `DATA` (A1:T1005001) là dữ liệu: header ở dòng 1, 1,005,000 dòng × 20 cột.
  - Không có công thức, không có dòng ẩn, không có ô lỗi, không có inline string. Có 241,196 ô trống.
  - Có VBA: `ThisWorkbook.Workbook_Open` sẽ chạy `RandomizeData` nếu B6 trống. Macro ghi đè cột D, E, F, L, T (Mileage, Engine, HP, Kms, Price) bằng giá trị mô phỏng, lấy theo một ma trận correlation cố định, rồi ghi thông báo vào B6.
  - **B6 đang trống** và người lưu file cuối cùng là giảng viên, nên file chưa được randomize.
  - Tốc độ đọc: openpyxl mất khoảng 0.9 phút (ước tính), calamine mất 12.7 giây. Parquet 40 MB đọc lại trong khoảng 0.1 giây và khớp 100% với dữ liệu đọc từ xlsm.
- **Quyết định / nhận xét:** dùng calamine và parquet trung gian. Đã hỏi người dùng về vấn đề randomize, và họ chọn làm trên file hiện tại.
- **Sửa lỗi:**
  - Bản đầu dùng regex bỏ sót `t="s"` nên in ra số index thay vì nội dung chữ. Đã sửa.
  - Xóa một dòng `load_workbook(...) if False` và biến `mixed` không dùng tới.

### 01_structure.py — Mục 1–2: cấu trúc dữ liệu
- **Mục đích:** kích thước, kiểu dữ liệu thực tế vs kiểu nên có, phân loại biến, data dictionary, toàn bộ nhãn gốc (dùng `repr` để thấy khoảng trắng).
- **Kết quả chính:**
  - Không có cột ID. GIẢ ĐỊNH: 1 dòng = 1 listing.
  - Có 7 biến categorical. Brand có 26 nhãn gốc (tức 13 hãng × 2 kiểu viết), Fuel_Type có 12 nhãn gốc.
  - 'Unknown' xuất hiện ở Fuel/Transmission/Color/City. NaN chỉ có ở Mileage, Engine, Horsepower (khoảng 8% mỗi cột).
  - Horsepower có giá trị min âm. Kms_Driven 100% là số nguyên.
- **Quyết định:** Registration_Age và Year là biến số rời rạc. Ba biến 0/1 là biến nhị phân.
- **Sửa lỗi:** bản đầu tìm cột ID bằng chuỗi con "id", nên báo nhầm Insurance_Valid, Accidents và Tax_Paid. Đã chuyển sang regex khớp nguyên từ.

### 02_data_quality.py — Mục 3: chất lượng dữ liệu
- **Mục đích:** kiểm tra missing, Unknown, nhãn không thống nhất (kèm bảng mapping), quan hệ Model–Brand, duplicates, kiểu dữ liệu, tính nhất quán nội tại, point mass.
- **Kết quả chính:**
  - **Missing:** 7.999–8.000% mỗi cột. Mẫu hình khớp với giả định độc lập: thiếu cả 3 cột là 515 dòng, kỳ vọng 514. Chênh lệch giữa các nhóm ≤ 0.67 điểm %.
  - **Unknown:** khoảng 8% mỗi cột; 28.2% số dòng có ít nhất một Unknown. Không có biến thể nào khác ('N/A', '-', '').
  - **Nhãn:** Brand có 10,040 dòng bị khoảng trắng (0.999%); 2,334 dòng Luxury sẽ bị xếp nhầm nếu không TRIM. Fuel có 20,123 dòng lỗi (2.0%), trong đó 6,692 là typo.
  - **Model–Brand:** 39 Model thuộc 13 Brand (3 Model mỗi Brand), không có Model nào gắn với hai Brand.
  - **Duplicates:** 5,000 cặp trùng hoàn toàn; bỏ bản sao thì còn đúng 1,000,000 dòng. Không có near-duplicate.
  - **Nhất quán nội tại:** Year + Registration_Age = 2025 ở 100% dòng.
  - **Point mass:** Car_Price = 50,000 ở 116,375 dòng (11.58%), Engine_CC = 800 ở 37,028 dòng, Mileage = 5 ở 516 dòng.
- **Quyết định:** giá trị min lặp lại nhiều như vậy được coi là "giá sàn" (censoring) và gắn cờ trong `_common.py`.

### 03_univariate.py — Mục 4: phân tích từng biến
- **Mục đích:** thống kê mô tả đầy đủ; bảng theo mẫu Guide (Mean/Mode/Median/SD/Min/Max) cho 3 nhóm Entire/Luxury/Non-luxury; tần suất categorical; biểu đồ.
- **Kết quả chính:**
  - **Car_Price:** mean 1,012,897, median 758,908, skew 6.99, kurtosis 116.5.
  - **Theo segment:** median Luxury 2,155,953 vs Non-luxury 581,505. Mọi biến khác có phân phối gần như giống hệt nhau giữa hai segment.
  - **Mode:** mode của Car_Price, Engine_CC và Mileage bằng đúng giá trị sàn. Mode của Kms và Horsepower không có ý nghĩa (chỉ lặp lại 2–38 lần).
  - **Categorical:** sau khi chuẩn hóa không còn nhóm hiếm (< 1%). Trong nhãn gốc có 19 nhãn hiếm, đều là biến thể lỗi.
- **Quyết định:** báo cáo median cho giá. Mode chỉ có ý nghĩa với biến rời rạc.
- **Chỉnh sửa:**
  - Histogram của biến có skew > 1 được cắt trục x ở P99.9; boxplot vẫn giữ toàn bộ dữ liệu.
  - Dùng `MaxNLocator(4)` để tránh nhãn trục bị chồng.
  - Bỏ `import numpy` không dùng tới.

### 04_outliers.py — Mục 5: outliers
- **Mục đích:** so sánh IQR (1.5×, 3×) với z-score; tách 3 loại: (a) implausible, (b) extreme nhưng có thể hợp lệ, (c) giá trị sàn; kiểm tra outlier có tập trung theo segment không.
- **Kết quả chính:**
  - **Car_Price:** 7.01% vượt 1.5×IQR, 0.58% vượt 3×IQR, 0.48% có |z| > 3. Trong số outlier theo 1.5×IQR, 94% là Luxury. Nếu tính fence riêng trong từng segment thì chỉ còn 0.91% (Luxury) và 0.66% (Non-luxury).
  - **Km/năm:** 99.04% dòng có km/năm trong [5,000; 25,000). 9,623 dòng vượt biên này, bao gồm toàn bộ 3,908 dòng Kms > 1M. Giá của các dòng này cao gấp 4.76 lần (median) xe cùng Model và tuổi, và chúng chiếm 81.5% outlier giá > 3×IQR.
  - **Horsepower ≤ 0:** 32 dòng, đều nằm ở Engine_CC = 800.
  - **Giá sàn:** chiếm 15.04% Non-luxury nhưng chỉ 0.05% Luxury; tăng theo tuổi xe, tới 55.2% ở xe Non-luxury 25 tuổi.
- **Quyết định:** đưa quy tắc km/năm > 25,000 vào `implausible_flags`. Quy tắc Kms > 1M giữ lại để so sánh.
- **Bổ sung sau lần chạy đầu:** fig_04c cho thấy điểm gãy ở khoảng 620k km, nên thêm phân tích km/năm, giá tương đối và fig_04d.

### 05_bivariate.py — Mục 6: quan hệ giữa các biến
- **Mục đích:** correlation Pearson/Spearman kèm heatmap; độ nhạy correlation với price; scatter trên sample (n = 5,000, seed = 5000); đường mean/median theo nhóm (toàn bộ dữ liệu); crosstab; multicollinearity.
- **Kết quả chính:**
  - **Multicollinearity:** Age–Year r = −1.000; Engine–HP 0.839; Age–Kms 0.642 (Spearman 0.813). 62 cặp còn lại có |r| ≤ 0.003.
  - **Price–Age:** Spearman −0.490.
  - **Price–Kms:** Pearson −0.074 trên toàn bộ, nhưng −0.335 sau khi bỏ implausible.
  - **Crosstab:** cơ cấu Fuel/Transmission/Owner/City/Color theo segment chênh nhau ≤ 0.13 điểm %.
- **Sửa lỗi:** `MergeError` do ghép bảng cột 2 tầng với bảng 1 tầng. Đã chuyển `kms_edges` sang MultiIndex.

### 06_target_price.py — Mục 7: biến mục tiêu
- **Mục đích:** so sánh price và log(price); price theo nhóm; so sánh Luxury vs Non-luxury trên 3 view; quan hệ theo từng segment (correlation, trendline mô tả); chỉ số mất giá.
- **Kết quả chính:**
  - **Skewness:** 6.99 (raw) → −0.73 (log). Ở view clean: 2.06 → −0.79.
  - **Tỉ số median Luxury/Non-luxury:** 3.71 lần.
  - **Biến categorical:** chỉ Brand/Model, Accidents và Service_History làm median giá khác biệt đáng kể. Các biến khác có tỉ số max/min ≤ 1.02.
  - **Độ dốc theo tuổi:** theo Rupees gần bằng nhau (Luxury −47,986, Non-luxury −42,037 mỗi năm), nhưng theo log thì khác nhiều (−2.7% vs −9.8%/năm).
  - **Accidents:** khoảng −23–24k Rs mỗi vụ ở cả hai segment. **Service_History:** khoảng +47–49k Rs ở cả hai segment.
- **Sửa lỗi / bổ sung:**
  - Clip giá trị trước khi lấy log ở trục phụ, để hết RuntimeWarning.
  - Thêm bảng Accidents/Service_History × Segment.

### 07_groups_time.py — Mục 8: theo nhóm và thời gian
- **Mục đích:** phân tích theo City/Brand/Model; median price theo năm và tuổi xe cho từng segment; đường thẳng mô tả fit trên các median; Kms theo tuổi.
- **Kết quả chính:**
  - **City:** median giá giữa các city chỉ chênh 0.83%.
  - **Brand:** median từ Tata 447k đến Mercedes 2.39M. Trong cùng Brand, các Model gần như không khác nhau (max/min ≤ 1.03). Hai segment không chồng lấn ở cấp Model.
  - **Tuổi xe:** median giá giảm khoảng −48,050 Rs mỗi năm ở cả hai segment (R² ≥ 0.997). Khoảng cách Luxury − Non-luxury ổn định ở khoảng 1.53–1.59M.
  - **Kms:** median Kms/tuổi ≈ 15,000 ở mọi độ tuổi. Owner_Type không liên quan tới tuổi xe.
- **Sửa lỗi / chỉnh sửa:**
  - Phép tính trên `a.index` trả về pandas Index nên không có `.var()`; đã chuyển sang numpy array.
  - Dời nhãn chú thích của fig_07c sang đầu mút bên phải.

### 08_representativeness.py — Mục 9: tính đại diện và bias
- **Mục đích:** phân bố số listing; kiểm tra Missing/Unknown có liên quan tới giá không; so sánh 6 kịch bản làm sạch (trước/sau).
- **Kết quả chính:**
  - **Phân bố:** Brand, Model, City, Year, Color gần như đều tuyệt đối (CV số dòng ≤ 0.006). Luxury chiếm 23.1%.
  - **NaN/Unknown:** median giá chênh ≤ 0.7% so với dòng đầy đủ.
  - **S3 (listwise deletion):** mất 45% dữ liệu mà kết quả gần như không đổi.
  - **S4 (bỏ giá sàn):** tỉ trọng xe Non-luxury ≥ 20 tuổi giảm từ 24.0% xuống 15.8%; median Non-luxury tăng 17%; tỉ số median Lux/Non giảm từ 3.71 xuống 3.18.
- **Quyết định:** không khuyến nghị S3 và S4. Khuyến nghị S2 (bỏ duplicates và implausible).

### 09_issue_log.py — Mục 10: Data Issue Log
- **Mục đích:** tạo Data Issue Log gồm 14 vấn đề, mọi con số bằng chứng được tính trực tiếp từ dữ liệu.
- **Output:** `tables/09_data_issue_log.csv` và `.md`.
- **Sửa lỗi:**
  - Một số con số ban đầu viết cứng trong câu chữ (skewness, % chênh median theo Fuel, |r|, độ giống typo, tỉ số Lux/Non) nay được tính từ dữ liệu.
  - Dấu `|` trong ô bảng markdown đổi từ `/` sang `\|`.

### run_all.sh
- Chạy lần lượt 00 → 09 và ghi log vào `logs/`. Lần chạy cuối cùng: không có lỗi, không có cảnh báo.
