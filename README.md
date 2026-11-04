# Legal Checker — GitOps local

Desired state của cluster **k3d `legal-checker-local`**, namespace `legal-checker`. API và Celery worker dùng cùng backend image; scheduler Beat dùng image đó, chạy riêng một replica.

| Root/package | Sở hữu |
|---|---|
| `environments/local/platform` | PostgreSQL/PVC, Redis/PVC, ExternalSecrets, default-deny và các NetworkPolicies cho app |
| `environments/local/apps` | Shared PVC, backend/frontend, worker/Beat, HPA/PDB, ingress, ServiceMonitor/PrometheusRule |
| `platform/secrets` | ESO resources; không chứa Secret payload |
| `workloads/storage` | PVC upload/cache/export được dùng chung trên node k3d |
| `operations/migrations` | Template Job gọi Alembic của app, ngoài auto-sync roots |
| `legal_gitops/release.py` | Chuẩn bị file từ receipts; không tự deploy/commit/push |

Infrastructure bootstrap LocalStack, ESO, Traefik và monitoring trước khi apply roots giai đoạn 2. Secret names/ports/context được thống nhất ở `contracts/local-platform.json`. Không đưa API key, kubeconfig, workbook, PDF, DB hoặc receipts private vào Git.

## Worker + Redis

`ASSESSMENT_QUEUE=celery`, Redis URL lấy từ Secret `legal-redis/REDIS_URL`. `legal-worker` không có HTTP Service. Beat giữ một replica/Recreate; không dùng `worker --beat` khi có thể tăng worker. API/worker cùng mount `/cache` trên PVC. Kết quả và tiến độ được lưu PostgreSQL để trình duyệt có thể đọc lại sau F5.

Root images override cùng tên backend cho API, worker và scheduler, nên release pipeline chỉ cần build backend image một lần. Frontend tiếp tục có image/Dockerfile hiện có. Không thêm Dockerfile worker.

## Triển khai

[Runbook giai đoạn 2](../Legal-Ai-Compliance-Checker-infrastructure/docs/PHASE2_LOCAL.md) hướng dẫn install, build/import và apply source local. Source chưa publish được thử với Argo auto-sync tạm ngừng ở đúng hai Legal apps. Review/publish rồi kiểm remote HEAD trước khi resume. File `release.json` là desired state/provenance, không thay bằng chứng chạy thật.

Các replica API/frontend do HPA quản lý (2–4, CPU70%); Argo cần ignore `/spec/replicas` + RespectIgnoreDifferences. Worker một replica/concurrency1; PVC RWO chỉ chia sẻ được trên cùng node. Default-deny cho phép đúng DNS, DB, Redis, edge, scrape và public HTTPS. Đây là local development, không chứng minh HA, E2E provider thật hoặc kết quả pháp lý đã được con người duyệt.
