
pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        timeout(time: 30, unit: 'MINUTES')
    }

    parameters {
        booleanParam(
            name: 'SEED_DEMO_DATA',
            defaultValue: false,
            description: 'Enable ICMS demo accounts and demo records during deployment. Select true for the initial demo deployment.'
        )
    }

    environment {
        AWS_REGION = 'ap-south-1'
        AWS_ACCOUNT_ID = '310853013925'

        ECR_REGISTRY = '310853013925.dkr.ecr.ap-south-1.amazonaws.com'
        BACKEND_REPO = 'icms-backend'
        FRONTEND_REPO = 'icms-frontend'

        APP_HOST = '172.31.5.9'
        APP_DIRECTORY = '/opt/icms'

        SSH_CREDENTIAL = 'icms-app-ssh'
        COMPOSE_FILE = 'docker-compose.prod.yml'
    }

    stages {

        stage('Checkout Source') {
            steps {
                echo 'Checking out ICMS repository...'

                git branch: 'main',
                    url: 'https://github.com/ikrgycloud/ICMS.git'
            }
        }

        stage('Verify Build Environment') {
            steps {
                sh '''
                    set -e

                    echo "===== JENKINS IDENTITY ====="
                    aws sts get-caller-identity

                    echo "===== DOCKER ====="
                    docker --version
                    docker compose version

                    echo "===== SOURCE FILES ====="
                    test -d backend
                    test -d frontend
                    test -f backend/Dockerfile
                    test -f frontend/Dockerfile

                    echo "Environment verification successful"
                '''
            }
        }

        stage('Build Backend') {
            steps {
                sh '''
                    set -e

                    docker build \
                      -t ${ECR_REGISTRY}/${BACKEND_REPO}:${BUILD_NUMBER} \
                      ./backend
                '''
            }
        }

        stage('Build Frontend') {
            steps {
                sh '''
                    set -e

                    docker build \
                      -t ${ECR_REGISTRY}/${FRONTEND_REPO}:${BUILD_NUMBER} \
                      ./frontend
                '''
            }
        }

        stage('Login to Amazon ECR') {
            steps {
                sh '''
                    set -e

                    aws ecr get-login-password \
                      --region ${AWS_REGION} \
                    | docker login \
                      --username AWS \
                      --password-stdin ${ECR_REGISTRY}
                '''
            }
        }

        stage('Push Images to ECR') {
            steps {
                sh '''
                    set -e

                    docker push \
                      ${ECR_REGISTRY}/${BACKEND_REPO}:${BUILD_NUMBER}

                    docker push \
                      ${ECR_REGISTRY}/${FRONTEND_REPO}:${BUILD_NUMBER}
                '''
            }
        }

        stage('Deploy to Application EC2') {
            steps {
                withCredentials([
                    sshUserPrivateKey(
                        credentialsId: 'icms-app-ssh',
                        keyFileVariable: 'SSH_KEY',
                        usernameVariable: 'SSH_USER'
                    )
                ]) {
                    sh '''
                        set -e

                        chmod 600 "$SSH_KEY"

                        ssh -i "$SSH_KEY" \
                          -o StrictHostKeyChecking=accept-new \
                          "$SSH_USER@$APP_HOST" \
                          "BUILD_NUMBER='$BUILD_NUMBER' SEED_DEMO_DATA='$SEED_DEMO_DATA' bash -s" <<'REMOTE'

set -e

echo "===== APPLICATION EC2 DEPLOYMENT ====="

cd /opt/icms

echo "===== ECR LOGIN ====="

aws ecr get-login-password \
  --region ap-south-1 \
  | docker login \
    --username AWS \
    --password-stdin \
    310853013925.dkr.ecr.ap-south-1.amazonaws.com

echo "===== SET IMAGE TAGS ====="

export BACKEND_IMAGE="310853013925.dkr.ecr.ap-south-1.amazonaws.com/icms-backend:${BUILD_NUMBER}"

export FRONTEND_IMAGE="310853013925.dkr.ecr.ap-south-1.amazonaws.com/icms-frontend:${BUILD_NUMBER}"

export DEMO_DATA_ENABLED="${SEED_DEMO_DATA}"

echo "Backend image: $BACKEND_IMAGE"
echo "Frontend image: $FRONTEND_IMAGE"
echo "Demo data enabled: $DEMO_DATA_ENABLED"

echo "===== VALIDATE COMPOSE CONFIGURATION ====="

docker compose \
  -f docker-compose.prod.yml \
  config --quiet

echo "===== PULL NEW IMAGES ====="

docker compose \
  -f docker-compose.prod.yml \
  pull backend frontend

echo "===== START DATABASE AND APPLICATION ====="

docker compose \
  -f docker-compose.prod.yml \
  up -d db backend frontend

echo "===== WAIT FOR BACKEND HEALTH ====="

for i in $(seq 1 40); do

    STATUS=$(docker inspect \
      --format='{{.State.Health.Status}}' \
      icms-backend 2>/dev/null || echo "starting")

    echo "Backend status: $STATUS"

    if [ "$STATUS" = "healthy" ]; then
        break
    fi

    if [ "$i" -eq 40 ]; then
        echo "Backend health check failed"
        docker logs --tail 100 icms-backend
        exit 1
    fi

    sleep 5

done

echo "===== VERIFY FRONTEND ====="

for i in $(seq 1 20); do

    if curl -fsS http://127.0.0.1:8080/ >/dev/null; then
        echo "Frontend is responding"
        break
    fi

    if [ "$i" -eq 20 ]; then
        echo "Frontend health check failed"
        docker logs --tail 100 icms-frontend
        exit 1
    fi

    sleep 3

done

echo "===== RUNNING CONTAINERS ====="

docker compose -f docker-compose.prod.yml ps

echo "===== DEPLOYMENT COMPLETED ====="

REMOTE
                    '''
                }
            }
        }

        stage('Final Deployment Verification') {
            steps {
                withCredentials([
                    sshUserPrivateKey(
                        credentialsId: 'icms-app-ssh',
                        keyFileVariable: 'SSH_KEY',
                        usernameVariable: 'SSH_USER'
                    )
                ]) {
                    sh '''
                        set -e

                        ssh -i "$SSH_KEY" \
                          -o StrictHostKeyChecking=accept-new \
                          "$SSH_USER@$APP_HOST" '
                            set -e

                            echo "===== DATABASE ====="
                            docker inspect \
                              --format="{{.State.Health.Status}}" \
                              icms-db

                            echo "===== BACKEND ====="
                            docker inspect \
                              --format="{{.State.Health.Status}}" \
                              icms-backend

                            echo "===== FRONTEND ====="
                            curl -fsS http://127.0.0.1:8080/ >/dev/null

                            echo "Frontend HTTP check successful"

                            echo "===== FINAL STATUS ====="
                            docker compose \
                              -f /opt/icms/docker-compose.prod.yml ps
                        '
                    '''
                }
            }
        }
    }

    post {
        success {
            echo '''
            =====================================
                 ICMS DEPLOYMENT SUCCESSFUL
            =====================================
            '''
            echo "Build: ${BUILD_NUMBER}"
            echo "Demo data requested: ${params.SEED_DEMO_DATA}"
            echo "Application: http://65.2.6.2:8080"
        }

        failure {
            echo '''
            =====================================
                 ICMS DEPLOYMENT FAILED
            =====================================
            Check the failed stage and console logs.
            '''
        }

        always {
            echo "Pipeline execution finished."
        }
    }
}
