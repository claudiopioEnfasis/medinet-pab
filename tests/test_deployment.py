"""Control de recuperación ensayado con Docker/HTTP simulados; nunca toca EC2."""
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
OLD, NEW = '1' * 40, '2' * 40


@pytest.fixture
def deployment(tmp_path):
    root = tmp_path / 'server'
    state = root / '.deployment'
    state.mkdir(parents=True)
    (root / 'scripts').mkdir()
    (root / '.env').write_text('fixture=true\n')
    (root / '.env.runtime').write_text('fixture=true\n')
    (root / 'compose.prod.yaml').write_text('services: {}\n')
    release = f'IMAGE_PREFIX=ghcr.io/fixture/project\nIMAGE_TAG=sha-{OLD}\nPOSTGRES_IMAGE_TAG=sha-{OLD}\n'
    (state / 'current.env').write_text(release)
    for file in (root / '.env', root / '.env.runtime', state / 'current.env'):
        file.chmod(0o600)
    (root / 'scripts' / 'backup.sh').write_text('#!/bin/bash\nset -eu\necho backup >> "$EVENTS"\n[[ $COMPOSE_FILE == */compose.prod.yaml ]]\n[[ ${FAIL_PHASE:-} != backup ]]\n')
    fake = tmp_path / 'commands'
    fake.mkdir()
    (fake / 'docker').write_text('''#!/usr/bin/env python3
import os,sys,pathlib
args=sys.argv[1:]
with open(os.environ['EVENTS'],'a') as f: f.write('docker '+ ' '.join(args)+'\\n')
if args[0]=='inspect': print('ghcr.io/fixture/project-'+args[-1].removeprefix('fixture-')+':sha-'+ ('3'*40 if os.getenv('FAIL_PHASE')=='release' and args[-1]=='fixture-api' else '1'*40))
elif args[0]=='run': print('0002' if os.getenv('FAIL_PHASE')=='schema' else '0001')
elif 'compose' in args:
 if 'exec' in args: print('0002' if os.getenv('FAIL_PHASE')=='schema_changed' and (pathlib.Path(os.environ['FIXTURE_STATE'])/'migrated').exists() else '0001')
 elif 'ps' in args: print('fixture-'+args[-1])
 elif 'pull' in args and os.getenv('FAIL_PHASE')=='pull': sys.exit(7)
 elif 'run' in args:
  if os.getenv('FAIL_PHASE')=='migration': sys.exit(8)
  if os.getenv('FAIL_PHASE')=='grants' and 'scripts.db_privileges' in args: sys.exit(9)
  if os.getenv('FAIL_PHASE')=='schema_changed': (pathlib.Path(os.environ['FIXTURE_STATE'])/'migrated').touch()
 elif 'up' in args:
  state=pathlib.Path(os.environ['FIXTURE_STATE'])
  release=pathlib.Path(args[args.index('--env-file',args.index('--env-file')+1)+1]).read_text()
  (state/'active').write_text('new' if 'sha-'+ '2'*40 in release else 'old')
''')
    (fake / 'curl').write_text('''#!/usr/bin/env python3
import os,pathlib,sys
state=pathlib.Path(os.environ['FIXTURE_STATE'])
with open(os.environ['EVENTS'],'a') as f: f.write('readiness\\n')
if os.getenv('FAIL_PHASE')=='health' and (state/'active').exists() and (state/'active').read_text()=='new': sys.exit(22)
''')
    for file in fake.iterdir(): file.chmod(0o755)
    events = tmp_path / 'events'
    env = {**os.environ, 'PATH': str(fake)+os.pathsep+os.environ['PATH'], 'EVENTS': str(events), 'FIXTURE_STATE': str(state)}
    return root, state, events, env, release


@pytest.mark.parametrize('phase', ['pull', 'schema', 'backup', 'migration', 'grants', 'health', 'release'])
def test_deployment_failure_preserves_release_and_recovers_when_needed(deployment, phase):
    root, state, events, env, release = deployment
    result = subprocess.run(['bash', str(ROOT/'deploy/deploy.sh'), NEW, str(root)], env={**env, 'FAIL_PHASE': phase}, capture_output=True, text=True)
    assert result.returncode != 0
    assert (state/'current.env').read_text() == release
    calls = events.read_text()
    assert ' down ' not in calls and 'volume rm' not in calls
    if phase in ('backup', 'migration', 'grants', 'health'):
        assert (state/'active').read_text() == 'old'
        assert 'Release anterior recuperado' in result.stderr
    else:
        assert ' stop ' not in calls


def test_deployment_success_commits_only_healthy_release(deployment):
    root, state, events, env, release = deployment
    result = subprocess.run(['bash', str(ROOT/'deploy/deploy.sh'), NEW, str(root)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert f'IMAGE_TAG=sha-{NEW}' in (state/'current.env').read_text()
    assert f'POSTGRES_IMAGE_TAG=sha-{OLD}' in (state/'current.env').read_text()
    assert (state/'previous.env').read_text() == release
    calls = events.read_text().splitlines()
    compose_calls = [c for c in calls if c.startswith('docker compose')]
    assert all('compose.prod.yaml' in c and 'compose.yaml ' not in c for c in compose_calls)
    assert all(not (' up ' in c and c.endswith(' db')) for c in compose_calls)
    assert sum(c == 'readiness' for c in calls) >= 2
    assert calls.index('backup') < next(i for i,c in enumerate(calls) if ' run ' in c and 'maintenance' in c)
    assert (root/'.env').read_text() == 'fixture=true\n'
    assert (root/'.env.runtime').read_text() == 'fixture=true\n'


def test_dispatcher_rejects_arbitrary_remote_command(tmp_path):
    result = subprocess.run(['bash', str(ROOT/'deploy/dispatch.sh')], env={**os.environ,'SSH_ORIGINAL_COMMAND':'deploy invalid; echo injected'}, capture_output=True,text=True)
    assert result.returncode == 2
    assert 'Comando SSH no admitido' in result.stderr


def test_changed_schema_blocks_automatic_rollback(deployment):
    root, state, events, env, release = deployment
    result = subprocess.run(['bash', str(ROOT/'deploy/deploy.sh'), NEW, str(root)], env={**env, 'FAIL_PHASE': 'schema_changed'}, capture_output=True, text=True)
    assert result.returncode != 0
    assert (state/'current.env').read_text() == release
    assert 'recuperación automática bloqueada' in result.stderr
    assert ' up ' not in events.read_text()
