# Desired state và ranh giới quản lý

Một ứng dụng backend modular monolith, một PostgreSQL local có các schema knowledge/runtime/qa/dev_meta. GitOps không diễn giải C05/C06/C07, không tự chọn luật và không tạo kết quả pháp lý. App modules và contracts vẫn thuộc repo ứng dụng.

```text
App source → build/import receipt ─┐
                                  ├→ GitOps prepare → review/commit/push → Argo manual sync
App importer → seed receipt ──────┘                                  ├→ platform
                                                                    └→ backend
```

| Thành phần | Owner |
|---|---|
| k3d, kubeconfig, local namespaces, Secrets, Argo install/project/Applications | Infrastructure |
| PostgreSQL/Redis StatefulSet, Service, PVC template | GitOps platform |
| Backend Deployment/Service/ConfigMap/replicas/image selection | GitOps workloads |
| Alembic schema, knowledge reader và importer workbook | Application owner operations |
| PDF/LLM/embedding logic và contracts nghiệp vụ | Application modules |

Handoff contract là `contracts/local-platform.json`, cùng bytes ở hai folder. Infrastructure nhận diện cluster instance bằng private marker; import/seed receipts gắn với instance đó. Receiver GitOps kiểm sự nhất quán trước khi đưa backend vào root. Receipts không tự kiểm tra hoặc sửa một DB đã bị người dùng thay đổi ngoài quy trình.

Metadata backend `release.json` giữ image/source/knowledge/dataset hashes. Image tag local được đặt theo Docker config ID thực và import vào k3d; không thay digest registry bằng một SHA bịa. Nếu triển khai cloud về sau, bổ sung registry digest, release signing và image/runtime policy phù hợp, thay vì dùng nguyên local tags.

PostgreSQL/Redis dùng local-path PVC, single replica, không có HA. Không copy Kafka/MinIO/MLflow hay auth system của MaintAI. Secrets dùng credentials local, không được đưa vào ConfigMap/profiles. Không có Ingress public vì app hiện chưa thực thi auth/tenant policy đầy đủ.

GitOps manual sync giữ việc review nguồn tách khỏi thao tác deploy. Thay local files chưa đổi cluster, publish chưa đồng nghĩa đã sync và Argo Synced chưa chứng minh chất lượng module/E2E.

Future worker có thể dùng cùng app image nhưng command worker riêng. Chỉ thêm sau khi implementation đã tồn tại; Redis hiện không chứng minh queue đã hoạt động. Frontend cần handoff build/port/API riêng, không sinh image UI từ skeleton hoặc giả định tiến độ trong slide.
