# Legal AI Compliance Checker — GitOps local

Desired state cho cluster **k3d `legal-checker-local`**, tham khảo ranh giới Infrastructure/Argo/GitOps của MaintAI. Đây là folder source mới, chưa chạy tests/render/build/sync/deploy và chưa có GitHub remote được tạo.

## Phần được quản lý

| Root | Nội dung |
|---|---|
| `environments/local/platform` | PostgreSQL 17.10/PVC; Redis tùy chọn, ban đầu tắt |
| `environments/local/apps` | Ban đầu rỗng; backend chỉ được thêm sau khi có image và seed receipts |
| `platform/postgres`, `platform/redis` | Kustomize packages của datastores local |
| `workloads/backend` | Một Deployment FastAPI + ClusterIP Service; không có Ingress public |
| `operations/migrations` | Template Job owner operation; **không được include vào Argo roots** |
| `config/local/runtime-catalog.json` | Trạng thái build/entrypoint đã đối chiếu với checkout app |
| `legal_gitops/release.py` | Chuẩn bị local desired state từ receipts; không gọi cluster/Git push |
| `contracts`, `versions` | Handoff contract, schema receipts, pins và nguồn tham khảo |

Infrastructure ở `../Legal-Ai-Compliance-Checker-infrastructure/` sở hữu cluster, kubeconfig, namespaces, Secrets và Argo bootstrap. Folder này không tạo các resources đó lần thứ hai. App sở hữu Dockerfile, SQL/Alembic và seed logic.

## 1. Mặc định không kích hoạt app

`environments/local/apps/kustomization.yaml` có `resources: []`; không có Deployment backend, worker hay frontend trong root đang chọn. PostgreSQL có cấu hình nhưng cũng chưa chạy nếu chưa có cluster/Argo sync.

Không deploy business modules thành nhiều services. Backend hiện chỉ có health/GET knowledge/GET run; worker còn placeholder, frontend checkout chưa có build interface. Metadata/speaker slides tiến độ giả định không được dùng như bằng chứng runtime.

PDF giữ nguồn HTTP(S) hiện có; không tự tạo MinIO hoặc đưa workbook/PDF vào Git. Redis chỉ là broker hạ tầng dự kiến, không tự thêm Celery/task vào app.

## 2. Công cụ chuẩn bị source

Từ root GitOps:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Các lệnh sau chỉ viết files, không apply cluster:

```bash
.venv/bin/python -m legal_gitops.release platform
# Chỉ khi cần broker cho implementation queue/worker về sau:
.venv/bin/python -m legal_gitops.release platform --redis
```

Không truyền `--redis` sẽ giữ nguyên Redis đã được bật; không âm thầm loại datastore khỏi desired state. Việc retire Redis/PVC cần review vận hành riêng.

Thường nên dùng CLI infrastructure để prepare backend, vì CLI đó kiểm cluster/import và tìm đúng private receipts:

```bash
# Chạy từ folder infrastructure:
.venv/bin/python -m legal_infra prepare backend
```

Có thể gọi receiver trực tiếp với các file receipt do infrastructure tạo:

```bash
.venv/bin/python -m legal_gitops.release backend \
  --image-receipt ../Legal-Ai-Compliance-Checker-infrastructure/.local/backend-image.json \
  --seed-receipt ../Legal-Ai-Compliance-Checker-infrastructure/.local/seed.json
```

Receiver yêu cầu:

- Image ID thật và alias local khớp, đã import vào đúng context.
- Image và seed cùng cluster instance/image ID.
- Source SHA/hash/dirty state, workbook hash và knowledge snapshot hash rõ ràng.
- Seed thuộc DEV_VALIDATION, không phải MASTER/TEST answers.

Receipts là bản ghi của operator local, không phải chữ ký production hoặc bằng chứng đã chạy kiểm thử. Dữ liệu public release chỉ gồm IDs/hashes/source metadata; không ghi credentials, rows workbook hoặc paths private vào Git.

## 3. Thay đổi sau prepare backend

Generator sửa:

```text
environments/local/apps/
├── kustomization.yaml   # include backend, image alias thật, ConfigMap có knowledge pin
└── release.json         # image/source/dataset metadata; không có secret
```

ConfigMap được Kustomize gắn content hash; thay snapshot/config tạo PodTemplate reference mới. DATABASE_URL chỉ lấy từ Secret `legal-database` do infrastructure tạo. Backend dùng UID không phải root, filesystem chỉ đọc, cache/tmp là emptyDir có giới hạn. Image local dùng `imagePullPolicy: Never`; phải import vào cluster trước.

`/health` dùng cho startup/liveness. Readiness `/api/v1/knowledge` xác nhận app phục vụ snapshot đã nạp; endpoint này hiện không query lại DB mỗi lần, nên không phải kiểm tra DB sống liên tục. Quan sát PostgreSQL/DB errors riêng; không gọi đây là full E2E.

## 4. Review, publish và Argo

Folder này chưa tự khởi tạo Git/remote. Khi đã tạo repo và publish branch thật, điền URL đó vào private settings của infrastructure và gọi `attach-gitops`. Không có URL repo giả được auto-apply.

Review diff trước khi commit/push. Argo có hai Applications manual sync:

1. `legal-checker-platform`: sync trước để tạo DB/PVC.
2. Chạy migration và seed qua infrastructure/app owner.
3. Prepare/publish backend desired state.
4. `legal-checker-backend`: sync sau, rồi kiểm đúng image/knowledge hash.

Không tự auto-sync/prune. AppProject chặn child app tạo Secrets/cluster resources. Private remote cần cấp repository credentials ngoài Git.

## 5. Tạm dừng backend

```bash
.venv/bin/python -m legal_gitops.release disable-backend
```

Generator giữ resources/image/pin và thêm replicas=0. Review/publish và sync để pod thực sự dừng. Tránh chỉ xóa Deployment khỏi root khi Argo prune đang tắt, vì pod cũ sẽ vẫn chạy. PostgreSQL/PVC không bị thay đổi.

## 6. Kiểm tra được thực hiện về sau

Khi được yêu cầu kiểm chứng, render hai roots bằng `make render-platform` và `make render-apps`, rồi kiểm receipts/context, migrations, dataset hashes, image startup và API. Đợt tạo source này chưa thực hiện các bước đó.

Job migration phải luôn ở ngoài Argo roots. Không thêm seed tự động vào startup pod; không dùng datasets/reference để giả output nghiệp vụ. Thay schema trong repo app bằng Alembic revision mới. Worker/frontend chỉ bổ sung khi có Dockerfile/entrypoint, cấu hình, dependencies và probe thật.

Xem [kiến trúc](docs/ARCHITECTURE.md), [trình tự local](docs/LOCAL_DEVELOPMENT.md) và [infrastructure runbook](../Legal-Ai-Compliance-Checker-infrastructure/README.md).
