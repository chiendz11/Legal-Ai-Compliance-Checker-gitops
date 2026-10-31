# Trình tự local

Các bước sau là hướng dẫn chưa thực thi khi tạo source:

1. Chuẩn bị hai checkout app/GitOps và Python dependencies của cả app/infrastructure.
2. Infrastructure `init` → `up` → `install-argocd`; giữ kubeconfig/context tách MaintAI.
3. Tạo/publish repo GitOps thật, cấu hình URL/branch trong private settings, `attach-gitops`.
4. Sync platform bằng Argo UI; chờ PostgreSQL/PVC Ready. Redis mặc định chưa dùng.
5. Infrastructure `build-image` → `import-image` → `migrate`.
6. Tải DEV_VALIDATION bằng script repo app; infrastructure `seed --workbook ...` gọi importer app qua port-forward tạm.
7. Infrastructure `prepare backend` viết overlay từ receipts. Review/publish GitOps.
8. Sync backend bằng Argo UI, kiểm image/source/knowledge pin. Mở backend qua forward loopback18100.
9. Sau khi module owners hoàn thiện, mới kiểm pipeline 1–9, review/report/UI và provider thật.

Không đưa secret values, kubeconfig, DB hoặc dataset lên Git khi publish. `versions/reference-lock.json` chỉ là nguồn tham khảo code; source đã thay đổi sau commit đó cần build receipt mới.

Nếu chưa có remote: có thể đọc/chỉnh/render source local nhưng Argo chưa đọc được folder này. Không cần bịa URL hoặc tự publish ứng dụng chỉ để bootstrap cluster.

Backend mới chưa bật trong root mặc định. Muốn dừng bản đã bật, dùng `legal_gitops.release disable-backend`, review/publish/sync để scale0. Không kỳ vọng việc xóa files nguồn sẽ dừng resource khi prune tắt.

Nâng knowledge/dataset phải giữ case/run/snapshot lineage theo contracts app. Không overwrite outputs tham chiếu hoặc human review để làm demo trông đầy đủ. DB local trong cluster không thay DB local mỗi dev; các dev có thể tiếp tục native/Compose riêng.
