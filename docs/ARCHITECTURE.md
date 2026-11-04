# Desired state giai đoạn 2

Một backend modular monolith được chạy bằng API và Celery worker riêng. Không tách business modules thành các microservices.

```text
Traefik → Frontend → FastAPI → Redis → Worker → PostgreSQL
                           ↘ shared files ↗
Beat (một replica) → Redis
LocalStack → ESO → Secrets → API/Worker/PostgreSQL/Redis
Prometheus ← API metrics; Alloy ← logs → Loki; Grafana ← Prometheus/Loki
```

Infrastructure sở hữu cluster/kubeconfig, controllers, bootstrap secrets và ClusterSecretStore. GitOps sở hữu app/datastore workloads, ExternalSecret mappings, network policies, HPA/PDB và monitoring resources của backend. App sở hữu contracts, nghiệp vụ, migration/importer và cơ chế idempotency/lease.

Redis dùng password, AOF/PVC, không phải result store. API/worker/Beat trỏ cùng image override backend. API và worker chung PVC uploads/source-cache/report exports; RWO local-path phù hợp một node, chưa phải storage multi-node/cloud.

Argo source là Git đã publish. Khi kiểm source chưa publish, infrastructure `phase2 apply-local` suspend auto-sync riêng hai Legal apps rồi apply desired state cục bộ. Chỉ resume sau khi review/publish đúng HEAD. Việc này không tạo commit hay CI run.

`legal_gitops.release` giữ lại các resources/config đã có khi nâng image, tránh xóa worker/edge/policies. Helper dừng backend kiểu cũ từ chối phase2 vì HPA/Argo có ownership replicas riêng; dùng runbook drain trước khi scale0. Không xóa Redis/PVC khi còn job.

C07/C13 vẫn draft, source chưa xác minh giữ UNKNOWN; monitoring không tự nâng cấp mức xác minh pháp lý.

ConfigMaps sinh bởi Kustomize được giữ cho rollback khi prune tắt. `generatorOptions` gắn `IgnoreExtraneous` theo cơ chế Argo dành cho generated resources; nó chỉ bỏ các bản generated dư khỏi tổng sync status, không bỏ so sánh Deployment/image hoặc bỏ kiểm tra health. Các bản cũ chỉ được gắn annotation sau khi kiểm tra không có pod đang dùng.
