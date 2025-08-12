# Tài liệu Test cho YOLO Inference Service

## 1. Mục đích của các file test

### `tests/test_api_basic.py`
- **Mục tiêu**: Kiểm tra các endpoint chính của API (`/predict` và `/predict/annotated`).
- **Nội dung test**:
  - Gửi **ảnh giả** (mock image) để kiểm tra API hoạt động.
    - Ảnh này không lấy từ ổ đĩa mà được tạo trực tiếp trong code bằng Pillow (PIL) thông qua hàm `make_img()`.
    - `make_img()` tạo một ảnh RGB trắng/đen nhỏ và lưu vào bộ nhớ (`BytesIO`), giúp test nhanh và không phụ thuộc vào dữ liệu ngoài.
  - Sử dụng `monkeypatch` để mock YOLO model, giúp test nhanh hơn mà không cần load model thật.
  - Đảm bảo API trả về kết quả đúng định dạng JSON hoặc ảnh annotated.

### `tests/test_predict_annotated_saves.py`
- **Mục tiêu**: Kiểm tra chức năng lưu ảnh annotated.
- **Nội dung test**:
  - Mock YOLO model để giả lập kết quả predict.
  - Gọi endpoint `/predict/annotated`.
  - Xác minh ảnh annotated được lưu đúng thư mục `results/`.

### `tests/conftest.py`
- **Mục tiêu**: Chứa các fixture và hàm hỗ trợ test.
- **Nội dung**:
  - `client`: Tạo FastAPI test client để gửi request tới API.
  - `make_img()`: Tạo ảnh giả để gửi lên API trong khi test (như mô tả ở trên).

💡 **Nếu muốn test với ảnh thật**:  
Bạn có thể tạo thư mục `tests/data/` chứa ảnh `.jpg` hoặc `.png`, rồi chỉnh test như sau:
```python
with open("tests/data/sample.jpg", "rb") as f:
    r = client.post("/predict", files={"file": ("sample.jpg", f, "image/jpeg")})
```
Cách này giúp kiểm tra pipeline YOLO thực tế, nhưng test sẽ chạy chậm hơn.

---

## 2. Hướng dẫn chạy test

### 2.1. Cài đặt môi trường test
```bash
# Kích hoạt môi trường ảo nếu dùng conda
conda activate IEE

# Cài pytest và các thư viện cần thiết
pip install pytest requests numpy
```

### 2.2. Tắt tracing (để tránh lỗi khi chưa chạy Jaeger)
```bash
export TRACING=off
```

### 2.3. Chạy toàn bộ test
```bash
pytest -v
```

### 2.4. Chạy 1 file test cụ thể
```bash
pytest -v tests/test_api_basic.py
```

### 2.5. Chạy 1 test cụ thể trong file
```bash
pytest -v tests/test_api_basic.py::test_predict_with_mock
```

---

## 3. Lưu ý
- Khi chạy test, các file ảnh kết quả sẽ được lưu trong thư mục `results/`.
- Nên sử dụng mock model để test nhanh và không tốn tài nguyên.
- Các test chỉ nhằm kiểm tra tính đúng đắn của API, không thay thế cho kiểm thử hiệu năng.