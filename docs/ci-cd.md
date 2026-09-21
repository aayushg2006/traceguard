# Phase 8 Jenkins CI/CD integration

Phase 8 adds repository-side Jenkins orchestration for TraceGuard. The
Jenkinsfile invokes the existing Phase 4, Phase 2, Phase 3, and Phase 7 CLIs;
security decisions remain in `scripts/evaluate_policy.py`, not Groovy.

## Pipeline stages

The declarative pipeline performs checkout, environment checks, isolated
`.jenkins-venv` installation from `requirements.txt`, `pip check`, pytest with
JUnit XML, Phase 4 change analysis, Phase 2 security execution, optional Phase
3 comparison, Phase 7 policy evaluation, sanitized artifact publication, and a
final policy decision stage.

`NONE` skips security execution. `TARGETED` runs only Phase 4-selected
categories. `FULL` runs the complete suite. A first build or checkout without a
valid first parent uses `FULL` and does not compare unrelated commits. Targeted
reports are not compared with a full baseline because their test populations
differ. Without a baseline, regression comparison is unavailable and policy
evaluates the available evidence.

## Environment requirements

The Jenkins agent needs Python 3.12-compatible tooling, `python3-venv`, Git,
`curl`, network access for `requirements.txt`, and access to Ollama and its
configured models. The audited host has Python 3.12.3, Java 21, Docker 29.7.2,
Ollama 0.32.9, and both required models, but no Jenkins installation or
service. Docker is not used for deployment in Phase 8.

The agent must reach `TRACEGUARD_OLLAMA_URL`. `127.0.0.1` means the Jenkins
agent itself, not necessarily the developer session. Set the Pipeline
parameter to an internal reachable URL when Jenkins runs elsewhere. Do not
expose Ollama publicly.

## Jenkins setup and plugins

Jenkins installation, startup, plugin installation, agent provisioning, and
permissions are manual because no Jenkins runtime is installed in this
workspace. On Ubuntu 24.04, an administrator can install Java and Jenkins LTS:

```bash
sudo apt update
sudo apt install -y fontconfig openjdk-21-jre
java -version
sudo wget -O /etc/apt/keyrings/jenkins-keyring.asc \
  https://pkg.jenkins.io/debian-stable/jenkins.io-2026.key
echo "deb [signed-by=/etc/apt/keyrings/jenkins-keyring.asc] https://pkg.jenkins.io/debian-stable binary/" \
  | sudo tee /etc/apt/sources.list.d/jenkins.list > /dev/null
sudo apt update
sudo apt install -y jenkins
sudo systemctl enable --now jenkins
sudo systemctl status jenkins
```

Verify these commands against the installed Jenkins release before execution.
Open the Jenkins URL, unlock it with the setup token, and complete the setup
wizard. In `Manage Jenkins > Plugins`, verify/install only Pipeline/Declarative
Pipeline, Git/Pipeline SCM, and JUnit. No Docker Pipeline plugin is required.

Create a Pipeline or Multibranch Pipeline from `New Item`, configure the
repository SCM, and select `Pipeline script from SCM` with script path
`Jenkinsfile`. The Git plugin is required by `checkout scm`.

## Credentials and webhooks

For a private repository, configure credentials at `Manage Jenkins >
Credentials > (global) > Add Credentials`, then select the credential in job
SCM settings. Never place credentials in this repository or Jenkinsfile.

For automatic builds, an administrator can configure GitHub at `Settings >
Webhooks > Add webhook`, using the administrator-provided Jenkins endpoint,
`application/json`, and the push/pull-request events appropriate to the job.
The Jenkins host must be reachable from GitHub and protected by suitable
authentication and network controls.

## Policy, baselines, and artifacts

Phase 7 exit codes are preserved: `0` means `ALLOW`, `10` means `BLOCK`, and
`20` means `ERROR`. BLOCK and ERROR fail the final Jenkins stage with an
explicit security message; neither is converted to success.

The pipeline archives only selected change-impact, security, regression,
mutation, replay, policy, sanitized failure-bundle, and JUnit artifacts. It
does not archive `.env`, `.jenkins-venv`, caches, credentials, or the workspace.

The default baseline is `reports/baseline.json`. Because generated baselines
are ignored locally, Jenkins must provide one through an approved artifact or
stash, or set `TRACEGUARD_BASELINE` to a workspace path. No baseline service is
created in Phase 8.

## Manual work status and limitations

CODEX AUTOMATION: The Jenkinsfile, repository-side orchestration, exit-code
handling, artifact allowlist, tests, and documentation are implemented.

USER MANUAL ACTION: Install/start Jenkins, complete setup, verify the listed
plugins, configure the SCM job and any private-repository credential, provision
an agent with Python/Git/curl/venv access, make Ollama reachable to that agent,
and optionally configure a webhook and baseline artifact. These require system
or Jenkins administrator access and were not performed automatically.

Jenkins is not installed or running in the audited environment, so live
Jenkins execution, plugin verification, artifact publication, and Jenkins
ALLOW/BLOCK/ERROR build results could not be validated. The Jenkinsfile was
statically checked and its referenced TraceGuard CLIs were validated locally.
