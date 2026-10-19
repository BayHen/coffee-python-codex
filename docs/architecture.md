# Kiến trúc khởi đầu

Hệ thống bắt đầu như một **modular monolith**: một backend FastAPI, một frontend React (sẽ tạo ở task sau) và một PostgreSQL đã có schema ở Task 2. Một tiến trình backend triển khai các chức năng cùng nhau; ranh giới module nằm trong code, chưa cần microservice.

Hiện tại `backend/app/main.py` khai báo ứng dụng và `/health`; `backend/app/db/` giữ
schema cùng cấu hình session; `backend/app/auth/` giữ đăng nhập và phân quyền;
`backend/app/catalog/` quản lý menu; `backend/app/orders/` quản lý vòng đời đơn và
thanh toán mô phỏng; `backend/app/inventory/` sở hữu nguyên liệu, recipe và stock
ledger. Mỗi module sở hữu route, logic nghiệp vụ và truy cập dữ liệu cần
thiết của nó. Chỉ trích xuất phần dùng chung khi có ít nhất hai nơi cần dùng và tên gọi
đã rõ. Xem [database-design.md](database-design.md), [authentication.md](authentication.md)
và [order-management.md](order-management.md),
[inventory-management.md](inventory-management.md) cho các quyết định chi tiết.

Không tạo sẵn `BaseRepository`, service interface, dependency container hay các lớp trừu tượng khác trước khi có nhu cầu cụ thể. Route `/health` chỉ cho biết tiến trình API đáp ứng; nó chưa kiểm tra kết nối database.

