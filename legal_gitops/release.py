"""Local release handoff. Writes GitOps files only; never syncs, commits or pushes."""

import argparse
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "contracts/local-platform.json").read_text())


def read(path):
    return json.loads(Path(path).read_text())


def write(name, value):
    path = ROOT / name
    if not path.resolve().is_relative_to((ROOT / "environments/local").resolve()):
        raise ValueError("Only the local desired-state roots may be prepared")
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        (json.dumps(value, indent=2, ensure_ascii=False) + "\n")
        if path.suffix == ".json"
        else yaml.safe_dump(value, sort_keys=False)
    )
    path.write_text(content, encoding="utf-8")


def kustomization(resources):
    return {
        "apiVersion": "kustomize.config.k8s.io/v1beta1",
        "kind": "Kustomization",
        "namespace": CONTRACT["namespace"],
        "resources": resources,
    }


def platform(args):
    current = yaml.safe_load(
        (ROOT / "environments/local/platform/kustomization.yaml").read_text()
    )
    # Omission of --redis is not a request to retire an already-enabled datastore.
    redis = args.redis or "../../../platform/redis" in current.get("resources", [])
    resources = list(current.get("resources", []))
    for resource in ["../../../platform/postgres"] + (
        ["../../../platform/redis"] if redis else []
    ):
        if resource not in resources:
            resources.append(resource)
    write("environments/local/platform/kustomization.yaml", kustomization(resources))
    write(
        "environments/local/platform/release.json",
        {"schema_version": "1.0.0", "postgres_enabled": True, "redis_enabled": redis},
    )


def backend(args):
    image = read(args.image_receipt)
    seed = read(args.seed_receipt)
    if image.get("schema_version") != "1.0.0" or seed.get("schema_version") != "1.0.0":
        raise ValueError("Unsupported receipt schema")
    identity = image.get("image_id", "")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", identity):
        raise ValueError("A real Docker image-ID receipt is required")
    alias = "legal-local/backend:image-" + identity[7:]
    if (
        image.get("image") != alias
        or image.get("imported_context") != CONTRACT["context"]
    ):
        raise ValueError(
            "Image alias/context differs from the actual local import receipt"
        )
    if not image.get("imported_cluster_id") or image["imported_cluster_id"] != seed.get(
        "cluster_id"
    ):
        raise ValueError("Image and seed must belong to the same cluster instance")
    if seed.get("image_id") != identity or seed.get("distribution") != "DEV_VALIDATION":
        raise ValueError(
            "Seed must use this image source and the DEV_VALIDATION dataset"
        )
    for name in ("workbook_sha256", "knowledge_snapshot_sha256"):
        if not re.fullmatch(r"[a-f0-9]{64}", seed.get(name, "")):
            raise ValueError("Seed receipt is missing " + name)
    source = image.get("source", {})
    if (
        not re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", source.get("git_sha", ""))
        or not re.fullmatch(r"[a-f0-9]{64}", source.get("snapshot_sha256", ""))
        or type(source.get("dirty")) is not bool
    ):
        raise ValueError("Missing application source identity")
    repository, tag = alias.rsplit(":", 1)
    desired = yaml.safe_load(
        (ROOT / "environments/local/apps/kustomization.yaml").read_text()
    )
    if "../../../workloads/backend" not in desired.setdefault("resources", []):
        desired["resources"].append("../../../workloads/backend")
    desired["images"] = [
        entry
        for entry in desired.get("images", [])
        if entry.get("name")
        not in {
            "registry.invalid/legal-checker/backend",
            "ghcr.io/chiendz11/legal-ai-compliance-checker-backend",
        }
    ]
    desired["images"].append(
        {
            "name": "ghcr.io/chiendz11/legal-ai-compliance-checker-backend",
            "newName": repository,
            "newTag": tag,
        }
    )
    config = next(
        (
            item
            for item in desired.setdefault("configMapGenerator", [])
            if item["name"] == "legal-backend-config"
        ),
        None,
    )
    if config is None:
        config = {"name": "legal-backend-config", "literals": []}
        desired["configMapGenerator"].append(config)
    config["literals"] = [
        value
        for value in config.get("literals", [])
        if not value.startswith("KNOWLEDGE_SNAPSHOT_SHA256=")
    ]
    config["literals"].append(
        "KNOWLEDGE_SNAPSHOT_SHA256=" + seed["knowledge_snapshot_sha256"]
    )
    write("environments/local/apps/kustomization.yaml", desired)
    # Keep public provenance small: no DSNs, passwords, workbook rows or local file paths.
    release_path = ROOT / "environments/local/apps/release.json"
    release = read(release_path) if release_path.exists() else {}
    release.update(
        {
            "schema_version": "1.0.0",
            "backend_enabled": True,
            "worker_enabled": "../../../workloads/worker" in desired["resources"],
            "scheduler_enabled": "../../../workloads/worker" in desired["resources"],
            "frontend_enabled": "../../../workloads/frontend" in desired["resources"],
            "image": alias,
            "image_id": identity,
            "source": source,
            "cluster_id": seed["cluster_id"],
            "workbook_sha256": seed["workbook_sha256"],
            "knowledge_snapshot_sha256": seed["knowledge_snapshot_sha256"],
            "evidence_kind": "LOCAL_OPERATOR_RECEIPTS_NOT_PRODUCTION_ATTESTATION",
        }
    )
    write("environments/local/apps/release.json", release)


def disable(_):
    path = ROOT / "environments/local/apps/release.json"
    release = read(path)
    if release.get("phase2_enabled"):
        raise ValueError(
            "Phase 2 uses HPA/Argo replica ownership; follow the explicit drain/scale runbook in docs/PHASE2_LOCAL.md"
        )
    if not release.get("image"):
        print("Backend is already absent from the initial desired state")
        return
    desired = yaml.safe_load(
        (ROOT / "environments/local/apps/kustomization.yaml").read_text()
    )
    # Scaling to zero works without destructive Argo pruning and preserves data.
    desired["replicas"] = [
        {"name": name, "count": 0}
        for name in ("legal-backend", "legal-worker", "legal-scheduler")
    ]
    release["worker_enabled"] = False
    release["scheduler_enabled"] = False
    release["backend_enabled"] = False
    write("environments/local/apps/kustomization.yaml", desired)
    write("environments/local/apps/release.json", release)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    child = commands.add_parser("platform")
    child.add_argument("--redis", action="store_true")
    child.set_defaults(function=platform)
    child = commands.add_parser("backend")
    child.add_argument("--image-receipt", type=Path, required=True)
    child.add_argument("--seed-receipt", type=Path, required=True)
    child.set_defaults(function=backend)
    commands.add_parser("disable-backend").set_defaults(function=disable)
    args = parser.parse_args()
    try:
        args.function(args)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(2, str(error) + "\n")
    print(
        "Local desired state prepared only; review Git diff, publish and sync explicitly"
    )


if __name__ == "__main__":
    main()
