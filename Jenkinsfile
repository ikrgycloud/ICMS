
pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        timeout(time: 45, unit: 'MINUTES')
        skipDefaultCheckout(true)
    }

    environment {
        AWS_REGION     = 'ap-south-1'
        AWS_ACCOUNT_ID = '310853013925'

        ECR_REGISTRY = '310853013925.dkr.ecr.ap-south-1.amazonaws.com'

        BACKEND_REPO  = 'icms-backend'
        FRONTEND_REPO = 'icms-frontend'

        IMAGE_TAG = "${BUILD_NUMBER}"

        APP_SERVER = 'ubuntu@172.31.5.9'
        APP_DIR    = '/opt/icms'

        SSH_CREDENTIAL_ID = 'icms-app-ssh'
    }

    stages {

        stage('Checkout') {
            steps {
                echo 'Checking out ICMS repository'

                checkout scm

                sh '''
                    echo "Checking repository structure"

                    test -f backend/Dockerfile
                    test -f frontend/Dockerfile
                    test -f docker-compose.prod.yml

                    echo "Repository structure verified"
                '''
            }
        }

        stage('Verify Jenkins Environment') {
            steps {
                sh '''
                    set -eu

                    echo "Checking Docker"
                    docker --version
                    docker compose version

                    echo "Checking AWS identity"
                    aws sts get-caller-identity

                    echo "Checking ECR authentication permission"

                    aws ecr get-login-password \
                        --region "$AWS_REGION" > /dev/null

                    echo "Jenkins environment verified"
                '''
            }
        }

        stage('Build Backend') {
            steps {
                echo 'Building ICMS backend'

                sh '''
                    docker build \
                        --pull \
                        -t "$BACKEND_REPO:$IMAGE_TAG" \
                        ./backend
                '''
            }
        }

        stage('Build Frontend') {
            steps {
                echo 'Building ICMS frontend'

                sh '''
                    docker build \
                        --pull \
                        -t "$FRONTEND_REPO:$IMAGE_TAG" \
                        ./frontend
                '''
            }
        }

        stage('Login to Amazon ECR') {
            steps {
                sh '''
                    set -eu

                    aws ecr get-login-password \
                        --region "$AWS_REGION" |
                    docker login \
                        --username AWS \
                        --password-stdin \
                        "$ECR_REGISTRY"

                    echo "ECR login successful"
                '''
            }
        }

        stage('Tag Docker Images') {
            steps {
                sh '''
                    set -eu

                    docker tag \
                        "$BACKEND_REPO:$IMAGE_TAG" \
                        "$ECR_REGISTRY/$BACKEND_REPO:$IMAGE_TAG"

                    docker tag \
                        "$FRONTEND_REPO:$IMAGE_TAG" \
                        "$ECR_REGISTRY/$FRONTEND_REPO:$IMAGE_TAG"

                    echo "Docker images tagged successfully"
                '''
            }
        }

        stage('Push Images to ECR') {
            steps {
                sh '''
                    set -eu

                    echo "Pushing backend image"

                    docker push \
                        "$ECR_REGISTRY/$BACKEND_REPO:$IMAGE_TAG"

                    echo "Pushing frontend image"

                    docker push \
                        "$ECR_REGISTRY/$FRONTEND_REPO:$IMAGE_TAG"

                    echo "Both images pushed successfully"
                '''
            }
        }

        stage('Deploy to Application EC2') {
            steps {
                sshagent(credentials: ["${SSH_CREDENTIAL_ID}"]) {

                    sh '''
                        set -eu

                        echo "Connecting to application EC2"

                        ssh \
                            -o BatchMode=yes \
                            -o StrictHostKeyChecking=accept-new \
                            -o ConnectTimeout=15 \
                            "$APP_SERVER" \
                            "APP_DIR='$APP_DIR' \
                             IMAGE_TAG='$IMAGE_TAG' \
                             AWS_REGION='$AWS_REGION' \
                             ECR_REGISTRY='$ECR_REGISTRY' \
                             BACKEND_REPO='$BACKEND_REPO' \
                             FRONTEND_REPO='$FRONTEND_REPO' \
                             bash -s" <<'REMOTE'

set -Eeuo pipefail

echo "=================================="
echo "ICMS PRODUCTION DEPLOYMENT"
echo "=================================="

cd "$APP_DIR"

# Verify required production files
test -f .env
test -f docker-compose.prod.yml

# Never deploy with the known placeholder password
if grep -q 'REPLACE_WITH_DB_PASSWORD' .env; then
    echo "ERROR: Replace the database password in .env"
    exit 1
fi

# Verify persistent PostgreSQL directory
test -d /data/postgres

# Verify Docker
docker --version
docker compose version

# Authenticate using Application EC2 IAM role
echo "Logging into Amazon ECR"

aws ecr get-login-password \
    --region "$AWS_REGION" |
docker login \
    --username AWS \
    --password-stdin \
    "$ECR_REGISTRY"

# Set new image references.
# Shell environment overrides the old image tags in .env.
export BACKEND_IMAGE="$ECR_REGISTRY/$BACKEND_REPO:$IMAGE_TAG"
export FRONTEND_IMAGE="$ECR_REGISTRY/$FRONTEND_REPO:$IMAGE_TAG"

# Validate Compose configuration
docker compose \
    --env-file .env \
    -f docker-compose.prod.yml \
    config -q

# Pull only the new application images.
echo "Pulling ICMS images"

docker compose \
    --env-file .env \
    -f docker-compose.prod.yml \
    pull backend frontend

# Start/update application services.
# PostgreSQL retains its existing /data/postgres bind mount.
echo "Starting ICMS services"

docker compose \
    --env-file .env \
    -f docker-compose.prod.yml \
    up -d

echo "Waiting for backend health"

BACKEND_HEALTH=""

for attempt in $(seq 1 36); do

    BACKEND_HEALTH=$(
        docker inspect \
            --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
            icms-backend 2>/dev/null || true
    )

    echo "Backend status: ${BACKEND_HEALTH:-not available}"

    if [ "$BACKEND_HEALTH" = "healthy" ]; then
        break
    fi

    if [ "$BACKEND_HEALTH" = "unhealthy" ] || \
       [ "$BACKEND_HEALTH" = "exited" ]; then

        echo "Backend failed health check"

        docker compose \
            -f docker-compose.prod.yml \
            logs --tail=100 backend

        exit 1
    fi

    sleep 5

done

if [ "$BACKEND_HEALTH" != "healthy" ]; then

    echo "Backend health check timed out"

    docker compose \
        -f docker-compose.prod.yml \
        logs --tail=100 backend

    exit 1
fi

echo "Backend is healthy"

# Verify frontend on the configured host port.
echo "Checking frontend"

for attempt in $(seq 1 12); do

    if curl --fail --silent \
        http://127.0.0.1:8080/ > /dev/null; then

        echo "Frontend is responding"
        break
    fi

    if [ "$attempt" -eq 12 ]; then
        echo "Frontend health check failed"

        docker compose \
            -f docker-compose.prod.yml \
            logs --tail=100 frontend

        exit 1
    fi

    sleep 5

done

echo "=================================="
echo "DEPLOYMENT COMPLETED"
echo "=================================="

docker compose \
    --env-file .env \
    -f docker-compose.prod.yml \
    ps

REMOTE
                    '''
                }
            }
        }

        stage('Final Verification') {
            steps {
                sshagent(credentials: ["${SSH_CREDENTIAL_ID}"]) {

                    sh '''
                        set -eu

                        ssh \
                            -o BatchMode=yes \
                            -o StrictHostKeyChecking=accept-new \
                            "$APP_SERVER" \
                            "docker inspect \
                             --format '{{.State.Health.Status}}' \
                             icms-backend"
                    '''

                    echo 'ICMS deployment verification completed'
                }
            }
        }
    }

    post {

        success {
            echo """
            =====================================
              ICMS DEPLOYMENT SUCCESSFUL
            =====================================

            Build Number: ${BUILD_NUMBER}

            Backend:
            ${ECR_REGISTRY}/${BACKEND_REPO}:${IMAGE_TAG}

            Frontend:
            ${ECR_REGISTRY}/${FRONTEND_REPO}:${IMAGE_TAG}

            Application EC2:
            ${APP_SERVER}

            Frontend:
            http://65.2.6.2:8080

            =====================================
            """
        }

        failure {
            echo """
            =====================================
              ICMS DEPLOYMENT FAILED
            =====================================

            Build Number: ${BUILD_NUMBER}

            Check Jenkins Console Output
            for the failed stage.

            =====================================
            """
        }
    }
}
