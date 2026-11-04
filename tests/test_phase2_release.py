"""Release receiver regression with synthetic receipts; never touches a cluster."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from legal_gitops import release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.root_patch = patch.object(release, "ROOT", self.root)
        self.root_patch.start()
        self.apps = self.root / "environments/local/apps"
        self.platform = self.root / "environments/local/platform"
        self.apps.mkdir(parents=True)
        self.platform.mkdir(parents=True)
        desired = release.kustomization(
            [
                "../../../workloads/backend",
                "../../../workloads/frontend",
                "../../../workloads/worker",
                "../../../workloads/storage",
                "../../../workloads/edge",
            ]
        )
        desired["configMapGenerator"] = [
            {
                "name": "legal-backend-config",
                "literals": ["ASSESSMENT_QUEUE=celery", "ASSESSMENT_LLM=offline"],
            }
        ]
        (self.apps / "kustomization.yaml").write_text(yaml.safe_dump(desired))
        (self.apps / "release.json").write_text(json.dumps({"phase2_enabled": True}))
        identity = "sha256:" + "a" * 64
        image = {
            "schema_version": "1.0.0",
            "image_id": identity,
            "image": "legal-local/backend:image-" + "a" * 64,
            "imported_context": release.CONTRACT["context"],
            "imported_cluster_id": "test-cluster",
            "source": {
                "git_sha": "b" * 40,
                "snapshot_sha256": "c" * 64,
                "dirty": False,
            },
        }
        seed = {
            "schema_version": "1.0.0",
            "image_id": identity,
            "cluster_id": "test-cluster",
            "distribution": "DEV_VALIDATION",
            "workbook_sha256": "d" * 64,
            "knowledge_snapshot_sha256": "e" * 64,
        }
        self.image = self.root / "image.json"
        self.seed = self.root / "seed.json"
        self.image.write_text(json.dumps(image))
        self.seed.write_text(json.dumps(seed))

    def tearDown(self):
        self.root_patch.stop()
        self.folder.cleanup()

    def test_backend_release_keeps_worker_queue_storage_and_phase2_metadata(self):
        release.backend(
            SimpleNamespace(image_receipt=self.image, seed_receipt=self.seed)
        )
        desired = yaml.safe_load((self.apps / "kustomization.yaml").read_text())
        self.assertIn("../../../workloads/worker", desired["resources"])
        self.assertIn("../../../workloads/storage", desired["resources"])
        self.assertIn(
            "ASSESSMENT_QUEUE=celery", desired["configMapGenerator"][0]["literals"]
        )
        result = release.read(self.apps / "release.json")
        self.assertTrue(result["phase2_enabled"] and result["worker_enabled"])

    def test_platform_release_does_not_retire_existing_policies_or_redis(self):
        resources = [
            "../../../platform/postgres",
            "../../../platform/redis",
            "../../../platform/secrets",
            "../../../platform/policies",
        ]
        (self.platform / "kustomization.yaml").write_text(
            yaml.safe_dump(release.kustomization(resources))
        )
        release.platform(SimpleNamespace(redis=False))
        result = yaml.safe_load((self.platform / "kustomization.yaml").read_text())
        self.assertEqual(result["resources"], resources)

    def test_foreign_cluster_receipt_is_rejected_before_writing_desired_state(self):
        original = (self.apps / "kustomization.yaml").read_bytes()
        seed = release.read(self.seed)
        seed["cluster_id"] = "another-cluster"
        self.seed.write_text(json.dumps(seed))
        with self.assertRaises(ValueError):
            release.backend(
                SimpleNamespace(image_receipt=self.image, seed_receipt=self.seed)
            )
        self.assertEqual((self.apps / "kustomization.yaml").read_bytes(), original)

    def test_legacy_disable_does_not_silently_fail_under_phase2_hpa_ownership(self):
        with self.assertRaisesRegex(ValueError, "HPA"):
            release.disable(None)


if __name__ == "__main__":
    unittest.main()
