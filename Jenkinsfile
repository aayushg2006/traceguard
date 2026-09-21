pipeline {
    agent any

    options {
        timestamps()
        skipDefaultCheckout(true)
    }

    parameters {
        string(name: 'TRACEGUARD_POLICY', defaultValue: 'config/policy.yaml', description: 'TraceGuard policy YAML path inside the workspace')
        string(name: 'TRACEGUARD_BASELINE', defaultValue: 'reports/baseline.json', description: 'Optional Phase 3 baseline available to this workspace')
        string(name: 'TRACEGUARD_OLLAMA_URL', defaultValue: 'http://127.0.0.1:11434', description: 'Ollama URL reachable from the Jenkins agent')
    }

    environment {
        TRACEGUARD_VENV = "${WORKSPACE}/.jenkins-venv"
        TRACEGUARD_PYTHON = "${WORKSPACE}/.jenkins-venv/bin/python"
        // The first SCM-discovered build may run before parameters are injected.
        // Keep explicit defaults so set -u cannot fail before the parameters exist.
        TRACEGUARD_POLICY_VALUE = "${params.TRACEGUARD_POLICY ?: 'config/policy.yaml'}"
        TRACEGUARD_BASELINE_VALUE = "${params.TRACEGUARD_BASELINE ?: 'reports/baseline.json'}"
        TRACEGUARD_OLLAMA_URL_VALUE = "${params.TRACEGUARD_OLLAMA_URL ?: 'http://127.0.0.1:11434'}"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                sh '''
                    set -eu
                    git rev-parse --show-toplevel
                    git rev-parse HEAD
                    git branch --show-current || true
                '''
            }
        }

        stage('Environment Audit') {
            steps {
                sh '''
                    set -eu
                    command -v python3
                    python3 --version
                    python3 -m venv --help >/dev/null
                    command -v git
                    git --version
                    command -v curl
                    curl --fail --silent --show-error "$TRACEGUARD_OLLAMA_URL_VALUE/api/tags" >/dev/null
                '''
            }
        }

        stage('Python Environment') {
            steps {
                sh '''
                    set -eu
                    python3 -m venv "$TRACEGUARD_VENV"
                    "$TRACEGUARD_PYTHON" -m pip install --disable-pip-version-check -r requirements.txt
                    "$TRACEGUARD_PYTHON" -m pip check
                '''
            }
        }

        stage('Dependency Validation') {
            steps {
                sh '''
                    set -eu
                    mkdir -p reports
                    "$TRACEGUARD_PYTHON" -m pytest -q --junitxml=reports/pytest.xml
                '''
            }
        }

        stage('Change Analysis') {
            steps {
                script {
                    sh '''
                        set -eu
                        mkdir -p reports
                        current=$(git rev-parse HEAD)
                        base=$(git rev-parse HEAD^1 2>/dev/null || true)
                        if [ -n "$base" ] && git cat-file -e "$base^{commit}" 2>/dev/null; then
                            "$TRACEGUARD_PYTHON" scripts/analyze_changes.py --base "$base" --current "$current" --output reports/change-impact.json
                        else
                            echo "No valid parent commit; first-build behavior requires a FULL security scan."
                        fi
                        if [ -f reports/change-impact.json ]; then
                            "$TRACEGUARD_PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["selection"]["mode"])' reports/change-impact.json > reports/traceguard-mode.txt
                            "$TRACEGUARD_PYTHON" -c 'import json,sys; print(",".join(json.load(open(sys.argv[1], encoding="utf-8"))["selection"]["tests"]))' reports/change-impact.json > reports/traceguard-categories.txt
                        else
                            echo FULL > reports/traceguard-mode.txt
                            echo NONE > reports/traceguard-categories.txt
                        fi
                    '''
                    def mode = readFile('reports/traceguard-mode.txt').trim()
                    def categories = readFile('reports/traceguard-categories.txt').trim()
                    echo "TraceGuard selection mode: ${mode}"
                    echo "TraceGuard selected categories: ${categories ?: 'none'}"
                }
            }
        }

        stage('Security Test Execution') {
            steps {
                script {
                    def mode = readFile('reports/traceguard-mode.txt').trim()
                    if (mode == 'NONE') {
                        echo 'No security-impacting change selected by Phase 4; security execution is skipped.'
                    } else {
                        sh '''
                            set -eu
                            mode=$(cat reports/traceguard-mode.txt)
                            categories=$(cat reports/traceguard-categories.txt)
                            mkdir -p reports
                            "$TRACEGUARD_PYTHON" -m scripts.index_knowledge
                            nohup "$TRACEGUARD_PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > .traceguard-uvicorn.log 2>&1 &
                            echo $! > .traceguard-app.pid
                            for attempt in $(seq 1 30); do
                                if curl --fail --silent http://127.0.0.1:8000/health >/dev/null; then break; fi
                                sleep 1
                            done
                            curl --fail --silent http://127.0.0.1:8000/health >/dev/null
                            if [ "$mode" = "TARGETED" ]; then
                                "$TRACEGUARD_PYTHON" scripts/run_security_tests.py --categories "$categories" --output reports/security-report.json --failures-dir reports/failures
                            else
                                "$TRACEGUARD_PYTHON" scripts/run_security_tests.py --output reports/security-report.json --failures-dir reports/failures
                            fi
                        '''
                    }
                }
            }
        }

        stage('Regression Evaluation') {
            steps {
                script {
                    def mode = readFile('reports/traceguard-mode.txt').trim()
                    if (mode == 'FULL' && fileExists(env.TRACEGUARD_BASELINE_VALUE)) {
                        sh '''
                            set -eu
                            "$TRACEGUARD_PYTHON" scripts/compare_regression.py \
                                --baseline "$TRACEGUARD_BASELINE_VALUE" \
                                --current reports/security-report.json \
                                --output reports/regression-report.json
                        '''
                    } else if (mode == 'TARGETED') {
                        echo 'Regression comparison is skipped for targeted results because Phase 3 scores must not mix test populations.'
                    } else {
                        echo 'No valid baseline is available; policy evaluation will proceed without a regression report.'
                    }
                }
            }
        }

        stage('Policy Evaluation') {
            steps {
                script {
                    def policyExit = sh(returnStatus: true, script: '''
                        set +e
                        mode=$(cat reports/traceguard-mode.txt)
                        set -- --policy "$TRACEGUARD_POLICY_VALUE" --output reports/policy-result.json
                        if [ "$mode" = "NONE" ]; then
                            set -- "$@" --impact-report reports/change-impact.json
                        else
                            set -- "$@" --security-report reports/security-report.json
                        fi
                        if [ -f reports/regression-report.json ]; then set -- "$@" --regression-report reports/regression-report.json; fi
                        if [ -f reports/mutation-report.json ]; then set -- "$@" --mutation-report reports/mutation-report.json; fi
                        if [ -f reports/replay-report.json ]; then set -- "$@" --replay-report reports/replay-report.json; fi
                        if [ -f reports/change-impact.json ] && [ "$mode" != "NONE" ]; then set -- "$@" --impact-report reports/change-impact.json; fi
                        "$TRACEGUARD_PYTHON" scripts/evaluate_policy.py "$@"
                        status=$?
                        echo "TraceGuard policy exit code: $status"
                        exit "$status"
                    ''')
                    writeFile file: 'reports/policy-exit-code.txt', text: "${policyExit}\n"
                    echo "TraceGuard policy exit code: ${policyExit}"
                }
            }
        }

        stage('Artifact Publication') {
            steps {
                archiveArtifacts artifacts: 'reports/change-impact.json,reports/security-report.json,reports/regression-report.json,reports/mutation-report.json,reports/policy-result.json,reports/replay-report.json,reports/failures/**/bundle.json,reports/failures/**/metadata.json', allowEmptyArchive: true, fingerprint: false
                junit testResults: 'reports/pytest.xml', allowEmptyResults: true
            }
        }

        stage('Final Security Decision') {
            steps {
                script {
                    def policyExit = readFile('reports/policy-exit-code.txt').trim()
                    if (policyExit == '0') {
                        echo 'TraceGuard policy decision: ALLOW. Pipeline may continue.'
                    } else if (policyExit == '10') {
                        error('TraceGuard policy decision: BLOCK. Build stopped by security policy.')
                    } else {
                        error('TraceGuard policy decision: ERROR. Security verification did not complete safely.')
                    }
                }
            }
        }
    }

    post {
        always {
            sh '''
                if [ -f .traceguard-app.pid ]; then
                    kill "$(cat .traceguard-app.pid)" 2>/dev/null || true
                    rm -f .traceguard-app.pid
                fi
            '''
        }
    }
}
