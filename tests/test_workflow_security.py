"""AWS identity checks fail closed without logging account identifiers."""
import os
from pathlib import Path
import subprocess

import pytest
import yaml


WORKFLOWS = Path(__file__).resolve().parents[1] / '.github/workflows'
AUTHENTICATIONS = [
    (path.name, job_name, index)
    for path in sorted(WORKFLOWS.glob('*.yml'))
    for job_name, job in yaml.load(path.read_text(), Loader=yaml.BaseLoader)['jobs'].items()
    for index, step in enumerate(job['steps'])
    if step.get('uses', '').startswith('aws-actions/configure-aws-credentials@')
]


@pytest.mark.parametrize('filename,job_name,index', AUTHENTICATIONS)
@pytest.mark.parametrize('actual,sts_error,succeeds', [
    ('123456789012', False, True),
    ('210987654321', False, False),
    ('', True, False),
])
def test_aws_identity_guard_before_privileged_work(filename, job_name, index, actual, sts_error, succeeds):
    workflow = yaml.load((WORKFLOWS / filename).read_text(), Loader=yaml.BaseLoader)
    steps = workflow['jobs'][job_name]['steps']
    settings = steps[index]['with']
    assert settings['role-to-assume'].startswith('${{ secrets.')
    assert settings['mask-aws-account-id'] == 'true'
    assert 'allowed-account-ids' not in settings  # Unsupported by the v4 action.
    guard = steps[index + 1]
    assert guard['env']['EXPECTED_ACCOUNT_ID'] == '${{ secrets.AWS_ACCOUNT_ID }}'
    # Supply a local STS stub so neither success nor failure needs AWS access.
    stub = '''aws() {
      if [[ "$MOCK_STS_ERROR" == 1 ]]; then return 1; fi
      printf '%s\\n' "$MOCK_ACTUAL_ACCOUNT"
    }
    '''
    completed = subprocess.run(
        ['bash', '-e', '-c', stub + guard['run']], capture_output=True, text=True,
        env={**os.environ, 'EXPECTED_ACCOUNT_ID': '123456789012',
             'MOCK_ACTUAL_ACCOUNT': actual, 'MOCK_STS_ERROR': str(int(sts_error))},
        timeout=10,
    )
    assert (completed.returncode == 0) is succeeds
    assert '123456789012' not in completed.stdout + completed.stderr
    assert '210987654321' not in completed.stdout + completed.stderr


@pytest.mark.parametrize('filename,job_name,index', AUTHENTICATIONS)
@pytest.mark.parametrize('configured', [True, False])
def test_role_metadata_is_masked_before_authentication(filename, job_name, index, configured):
    workflow = yaml.load((WORKFLOWS / filename).read_text(), Loader=yaml.BaseLoader)
    steps = workflow['jobs'][job_name]['steps']
    mask = steps[index - 1]
    assert mask['env']['ROLE_ARN'] == steps[index]['with']['role-to-assume']
    assert mask['env']['ROLE_ID'].startswith('${{ secrets.')
    completed = subprocess.run(
        ['bash', '-e', '-c', mask['run']], capture_output=True, text=True,
        env={**os.environ, 'ROLE_ARN': 'arn:aws:iam::123456789012:role/SyntheticRole',
             'ROLE_ID': 'SYNTHETICROLEID' if configured else ''}, timeout=10,
    )
    assert (completed.returncode == 0) is configured
    if configured:
        assert completed.stdout.splitlines() == [
            '::add-mask::SyntheticRole', '::add-mask::SYNTHETICROLEID',
        ]
    else:
        assert '123456789012' not in completed.stdout + completed.stderr
