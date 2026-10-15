# Reflection

**Những loại lỗi nào khó phát hiện nhất và tại sao?**

Em thấy khó nhất là các lỗi lệch nhẹ và lỗi thiếu một phần upstream. Các chỉ số lệch nhẹ có thể vẫn nằm trong ngưỡng bình thường nên dễ bị bỏ sót. Nếu hạ ngưỡng quá thấp thì lại báo nhầm dữ liệu sạch. Ví dụ, khi thử ngưỡng khoảng cách tổng hợp 1.30 cho data batch, Practice xuất hiện 9 báo động giả. Em đổi sang khoảng 3.72 dựa trên giả định thống kê, giữ kiểm tra từng chiều và nâng ngưỡng feature drift lên 0.65 để giảm báo nhầm.

Với lineage, kiểm tra upstream rỗng chưa đủ vì lỗi có thể chỉ làm mất một nguồn đầu vào. Em bổ sung đối chiếu topology đã xuất hiện lặp lại trong `ctx.state` và kiểm tra hai nguồn bắt buộc của model `dbt:stg_orders`. Tuy vậy, cách học lịch sử vẫn có thể báo nhầm khi pipeline thay đổi nguồn hợp lệ.

Bản cuối đạt 50 điểm trên Practice và 46.90 điểm trên Public. Private đạt 32.41 điểm, TPR 64.81%, FPR 0%. Kết quả Private thấp hơn cho thấy cách kiểm tra hiện tại vẫn bỏ sót lỗi trên dữ liệu mới, dù không có báo động giả. Em chưa thể kết luận cụ thể lỗi nào bị bỏ sót vì báo cáo Private không cung cấp chi tiết từng sự kiện.

**Nếu có cơ hội thứ hai, bạn sẽ thay đổi điều gì về sự cân bằng giữa chi phí và phạm vi bảo hiểm?**

Bản hiện tại đã bỏ budget guard ở cả năm handler, mỗi sự kiện gọi đúng một công cụ và không dừng kiểm tra khi hết credit. Trên Public, chi phí tăng từ 220 lên 240 credit, nhưng điểm phạt vượt ngân sách khoảng 1.82 thấp hơn lợi ích bắt thêm lỗi trong lượt thử này. Sau các thay đổi, số lỗi bắt được tăng từ 33/39 lên 38/39, báo nhầm giảm từ 2 xuống 0. Private có cost_overage bằng 0.

Nếu làm lại, em sẽ đánh giá lợi ích phát hiện lỗi so với chi phí của từng nhóm sự kiện, thay vì mặc định luôn kiểm tra tất cả hoặc dừng ngay khi hết ngân sách. Em cũng muốn kiểm chứng các ngưỡng trên nhiều luồng sạch và có lỗi hơn, kết hợp tín hiệu và lịch sử để tăng độ bao phủ mà không làm FPR tăng nhiều. Em sẽ so sánh cả TPR, FPR, chi phí và điểm tổng, tránh chọn ngưỡng chỉ vì đạt điểm cao trên Practice hoặc Public.
