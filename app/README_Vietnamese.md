
# YOLO Inference Service - Tài Liệu Mô Tả

## 1. Tính Năng Chính
Dịch vụ này cung cấp API dựa trên **FastAPI** để chạy mô hình **YOLO (Ultralytics)** cho nhận diện đối tượng trong ảnh.

Các tính năng chính:
- Nhận ảnh qua API `/predict` hoặc `/predict/annotated`.
- Chạy YOLO để phát hiện đối tượng và trả kết quả:
  - `/predict`: Trả JSON chứa thông tin các bounding box, class, và confidence.
  - `/predict/annotated`: Trả ảnh PNG đã vẽ bounding box và lưu vào thư mục `./results`.
- **Lazy-load model**: Chỉ load YOLO model khi lần đầu cần dự đoán.
- Ghi **metrics** (Prometheus) để giám sát hiệu suất.
- Hỗ trợ **tracing** (Jaeger) để theo dõi luồng xử lý.
- Cấu hình qua biến môi trường (.env).

## 2. Công Nghệ Sử Dụng
| Công nghệ / Thư viện          | Mục đích |
|-------------------------------|----------|
| **FastAPI**                   | Xây dựng API RESTful nhanh chóng |
| **Ultralytics YOLO**          | Mô hình phát hiện đối tượng |
| **OpenTelemetry** (`opentelemetry`) | Thu thập và gửi trace tới hệ thống quan sát |
| **Jaeger**                    | Thu thập và hiển thị trace |
| **Prometheus** (`prometheus_client`) | Thu thập và lưu trữ metrics |
| **loguru**                    | Ghi log tiện lợi |
| **PIL (Pillow)**              | Xử lý ảnh |
| **PyTorch**                   | Chạy YOLO model |
| **dotenv**                    | Đọc biến môi trường từ file `.env` |

## 3. Các Endpoint
| Endpoint                | Mô tả |
|-------------------------|-------|
| `GET /`                 | Kiểm tra API có hoạt động |
| `GET /healthz`          | Kiểm tra tình trạng model |
| `GET /model/info`       | Trả thông tin model |
| `POST /predict`         | Nhận ảnh, chạy YOLO, trả kết quả JSON |
| `POST /predict/annotated` | Nhận ảnh, chạy YOLO, trả ảnh annotated PNG + lưu file vào `./results` |

## 4. Cấu Hình Qua Biến Môi Trường
- `MODEL_PATH`: Đường dẫn tới file `.pt` của YOLO (mặc định `./models/best.pt`)
- `CONF`: Ngưỡng confidence (mặc định `0.25`)
- `IOU`: Ngưỡng NMS (mặc định `0.45`)
- `IMG_SIZE`: Kích thước ảnh đầu vào (mặc định `640`)
- `PROM_PORT`: Cổng Prometheus (mặc định `8097`)
- `JAEGER_HOST`: Host của Jaeger (mặc định `jaeger-tracing-jaeger-all-in-one.tracing.svc.cluster.local`)
- `JAEGER_PORT`: Port của Jaeger (mặc định `6831`)

## 5. Dặn Dò Khi Test Nếu Không Chạy Jaeger
Nếu bạn **chưa khởi động Jaeger** hoặc không muốn gửi trace:
1. Có thể **bỏ qua phần Jaeger Exporter** trong code hoặc
2. Đặt biến môi trường `JAEGER_HOST` thành một giá trị giả như `localhost` và comment phần `JaegerExporter` trong file `main.py`.
3. Khi không bật Jaeger, các log cảnh báo về `Temporary failure in name resolution` có thể xuất hiện — có thể bỏ qua nếu chỉ test model.

---
**Tóm lại**: File `main.py` này là một dịch vụ YOLO đầy đủ với API, metrics và tracing, phù hợp để triển khai trong môi trường có giám sát Prometheus + Jaeger, nhưng cũng có thể chạy độc lập để test inference.