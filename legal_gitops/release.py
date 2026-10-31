"""Local release handoff. Writes GitOps files only; never syncs, commits or pushes."""

import argparse
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / 'contracts/local-platform.json').read_text())


def read(path):
    return json.loads(Path(path).read_text())


def write(name, value):
    path = ROOT / name
    if not path.resolve().is_relative_to((ROOT / 'environments/local').resolve()):
        raise ValueError('Only the local desired-state roots may be prepared')
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (json.dumps(value, indent=2, ensure_ascii=False) + '\n') if path.suffix == '.json' else yaml.safe_dump(value, sort_keys=False)
    path.write_text(content, encoding='utf-8')


def kustomization(resources):
    return {'apiVersion': 'kustomize.config.k8s.io/v1beta1', 'kind': 'Kustomization',
            'namespace': CONTRACT['namespace'], 'resources': resources}


def platform(args):
    current = yaml.safe_load((ROOT / 'environments/local/platform/kustomization.yaml').read_text())
    # Omission of --redis is not a request to retire an already-enabled datastore.
    redis = args.redis or '../../../platform/redis' in current.get('resources', [])
    resources = ['../../../platform/postgres'] + (['../../../platform/redis'] if redis else [])
    write('environments/local/platform/kustomization.yaml', kustomization(resources))
    write('environments/local/platform/release.json', {'schema_version': '1.0.0',
          'postgres_enabled': True, 'redis_enabled': redis})


def backend(args):
    image = read(args.image_receipt)
    seed = read(args.seed_receipt)
    if image.get('schema_version') != '1.0.0' or seed.get('schema_version') != '1.0.0':
        raise ValueError('Unsupported receipt schema')
    identity = image.get('image_id', '')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', identity):
        raise ValueError('A real Docker image-ID receipt is required')
    alias = 'legal-local/backend:image-' + identity[7:]
    if image.get('image') != alias or image.get('imported_context') != CONTRACT['context']:
        raise ValueError('Image alias/context differs from the actual local import receipt')
    if not image.get('imported_cluster_id') or image['imported_cluster_id'] != seed.get('cluster_id'):
        raise ValueError('Image and seed must belong to the same cluster instance')
    if seed.get('image_id') != identity or seed.get('distribution') != 'DEV_VALIDATION':
        raise ValueError('Seed must use this image source and the DEV_VALIDATION dataset')
    for name in ('workbook_sha256', 'knowledge_snapshot_sha256'):
        if not re.fullmatch(r'[a-f0-9]{64}', seed.get(name, '')):
            raise ValueError('Seed receipt is missing ' + name)
    source = image.get('source', {})
    if (not re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}', source.get('git_sha', ''))
            or not re.fullmatch(r'[a-f0-9]{64}', source.get('snapshot_sha256', ''))
            or type(source.get('dirty')) is not bool):
        raise ValueError('Missing application source identity')
    repository, tag = alias.rsplit(':', 1)
    desired = kustomization(['../../../workloads/backend'])
    desired.update({
        'images': [{'name': 'registry.invalid/legal-checker/backend', 'newName': repository, 'newTag': tag}],
        'configMapGenerator': [{'name': 'legal-backend-config', 'literals': [
            'KNOWLEDGE_SNAPSHOT_SHA256=' + seed['knowledge_snapshot_sha256'],
            'SOURCE_CACHE_DIR=/cache/source', 'SOURCE_DOWNLOAD_TIMEOUT_SECONDS=30',
            'SOURCE_MAX_BYTES=104857600', 'PYTHONDONTWRITEBYTECODE=1']}],
    })
    write('environments/local/apps/kustomization.yaml', desired)
    # Keep public provenance small: no DSNs, passwords, workbook rows or local file paths.
    write('environments/local/apps/release.json', {
        'schema_version': '1.0.0', 'backend_enabled': True, 'worker_enabled': False,
        'frontend_enabled': False, 'image': alias, 'image_id': identity,
        'source': source, 'cluster_id': seed['cluster_id'],
        'workbook_sha256': seed['workbook_sha256'],
        'knowledge_snapshot_sha256': seed['knowledge_snapshot_sha256'],
        'evidence_kind': 'LOCAL_OPERATOR_RECEIPTS_NOT_PRODUCTION_ATTESTATION'})


def disable(_):
    path = ROOT / 'environments/local/apps/release.json'
    release = read(path)
    if not release.get('image'):
        print('Backend is already absent from the initial desired state')
        return
    desired = yaml.safe_load((ROOT / 'environments/local/apps/kustomization.yaml').read_text())
    # Scaling to zero works without destructive Argo pruning and preserves data.
    desired['replicas'] = [{'name': 'legal-backend', 'count': 0}]
    release['backend_enabled'] = False
    write('environments/local/apps/kustomization.yaml', desired)
    write('environments/local/apps/release.json', release)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    child = commands.add_parser('platform')
    child.add_argument('--redis', action='store_true')
    child.set_defaults(function=platform)
    child = commands.add_parser('backend')
    child.add_argument('--image-receipt', type=Path, required=True)
    child.add_argument('--seed-receipt', type=Path, required=True)
    child.set_defaults(function=backend)
    commands.add_parser('disable-backend').set_defaults(function=disable)
    args = parser.parse_args()
    try:
        args.function(args)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(2, str(error) + '\n')
    print('Local desired state prepared only; review Git diff, publish and sync explicitly')


if __name__ == '__main__':
    main()
