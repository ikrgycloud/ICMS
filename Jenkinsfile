pipeline {

    agent any

    environment {

        // =========================================================
        // AWS CONFIGURATION
        // =========================================================

        AWS_REGION = "eu-north-1"

        AWS_ACCOUNT_ID = "032844082845"

        ECR_REGISTRY =
            "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"


        // =========================================================
        // ECR REPOSITORIES
        // =========================================================

        ERP_BACKEND_REPO = "erpgold-backend"

        ERP_FRONTEND_REPO = "erpgold-frontend"

        POS_BACKEND_REPO = "posgold-backend"

        POS_FRONTEND_REPO = "posgold-frontend"


        // =========================================================
        // IMAGE TAG
        // Every Jenkins build gets a unique image tag
        // =========================================================

        IMAGE_TAG = "${BUILD_NUMBER}"


        // =========================================================
        // APPLICATION EC2
        // =========================================================

        APP_SERVER = "ubuntu@16.16.216.155"

        APP_DIR = "/opt/erp-gold"


        // =========================================================
        // PUBLIC API URLS
        // These are compiled into the frontend during Docker build
        // =========================================================

        ERP_API_URL = "http://16.16.216.155:8001"

        POS_API_URL = "http://16.16.216.155:8000"
    }


    stages {


        // =========================================================
        // 1. CHECKOUT
        // =========================================================

        stage('Checkout') {

            steps {

                echo "=============================================="
                echo "Checking out ERP-GOLD source code"
                echo "=============================================="

                checkout scm
            }
        }


        // =========================================================
        // 2. VERIFY SOURCE
        // =========================================================

        stage('Verify Source') {

            steps {

                sh '''
                    set -e

                    echo "=============================================="
                    echo "Verifying ERP-GOLD source"
                    echo "=============================================="

                    echo "Current directory:"
                    pwd

                    echo ""
                    echo "Repository contents:"
                    ls -la

                    echo ""
                    echo "Checking required directories..."

                    test -d ERP-Backend
                    test -d ERP-Frontend
                    test -d POS-Backend
                    test -d POS-Frontend

                    echo ""
                    echo "Checking required Dockerfiles..."

                    test -f ERP-Backend/Dockerfile
                    test -f ERP-Frontend/Dockerfile
                    test -f POS-Backend/Dockerfile
                    test -f POS-Frontend/Dockerfile

                    echo ""
                    echo "ERP-GOLD source verification successful."
                '''
            }
        }


        // =========================================================
        // 3. BUILD ERP BACKEND
        // =========================================================

        stage('Build ERP Backend') {

            steps {

                echo "=============================================="
                echo "Building ERP Backend"
                echo "=============================================="

                sh '''
                    set -e

                    docker build \
                        -t ${ECR_REGISTRY}/${ERP_BACKEND_REPO}:${IMAGE_TAG} \
                        -f ERP-Backend/Dockerfile \
                        .

                    echo ""
                    echo "ERP Backend image built successfully."

                    docker images \
                        ${ECR_REGISTRY}/${ERP_BACKEND_REPO}:${IMAGE_TAG}
                '''
            }
        }


        // =========================================================
        // 4. BUILD POS BACKEND
        // =========================================================

        stage('Build POS Backend') {

            steps {

                echo "=============================================="
                echo "Building POS Backend"
                echo "=============================================="

                sh '''
                    set -e

                    docker build \
                        -t ${ECR_REGISTRY}/${POS_BACKEND_REPO}:${IMAGE_TAG} \
                        -f POS-Backend/Dockerfile \
                        .

                    echo ""
                    echo "POS Backend image built successfully."

                    docker images \
                        ${ECR_REGISTRY}/${POS_BACKEND_REPO}:${IMAGE_TAG}
                '''
            }
        }


        // =========================================================
        // 5. BUILD ERP FRONTEND
        // =========================================================

        stage('Build ERP Frontend') {

            steps {

                echo "=============================================="
                echo "Building ERP Frontend"
                echo "=============================================="

                sh '''
                    set -e

                    docker build \
                        --build-arg VITE_API_URL=${ERP_API_URL} \
                        -t ${ECR_REGISTRY}/${ERP_FRONTEND_REPO}:${IMAGE_TAG} \
                        ./ERP-Frontend

                    echo ""
                    echo "ERP Frontend image built successfully."

                    docker images \
                        ${ECR_REGISTRY}/${ERP_FRONTEND_REPO}:${IMAGE_TAG}
                '''
            }
        }


        // =========================================================
        // 6. BUILD POS FRONTEND
        // =========================================================

        stage('Build POS Frontend') {

            steps {

                echo "=============================================="
                echo "Building POS Frontend"
                echo "=============================================="

                sh '''
                    set -e

                    docker build \
                        --build-arg VITE_API_URL=${POS_API_URL} \
                        -t ${ECR_REGISTRY}/${POS_FRONTEND_REPO}:${IMAGE_TAG} \
                        ./POS-Frontend

                    echo ""
                    echo "POS Frontend image built successfully."

                    docker images \
                        ${ECR_REGISTRY}/${POS_FRONTEND_REPO}:${IMAGE_TAG}
                '''
            }
        }


        // =========================================================
        // 7. TEST DOCKER IMAGES
        // =========================================================

        stage('Test Docker Images') {

            steps {

                echo "=============================================="
                echo "Testing Docker Images"
                echo "=============================================="

                sh '''
                    set -e

                    echo "Testing ERP Backend image..."

                    docker run --rm \
                        ${ECR_REGISTRY}/${ERP_BACKEND_REPO}:${IMAGE_TAG} \
                        python -c "import app.main; print('ERP Backend import: OK')"


                    echo ""
                    echo "Testing POS Backend image..."

                    docker run --rm \
                        ${ECR_REGISTRY}/${POS_BACKEND_REPO}:${IMAGE_TAG} \
                        python -c "import app.main; print('POS Backend import: OK')"


                    echo ""
                    echo "Testing ERP Frontend image..."

                    docker run --rm \
                        ${ECR_REGISTRY}/${ERP_FRONTEND_REPO}:${IMAGE_TAG} \
                        nginx -t


                    echo ""
                    echo "Testing POS Frontend image..."

                    docker run --rm \
                        ${ECR_REGISTRY}/${POS_FRONTEND_REPO}:${IMAGE_TAG} \
                        nginx -t


                    echo ""
                    echo "All Docker image tests passed."
                '''
            }
        }


        // =========================================================
        // 8. LOGIN TO ECR
        // =========================================================

        stage('Login to Amazon ECR') {

            steps {

                echo "=============================================="
                echo "Logging into Amazon ECR"
                echo "=============================================="

                withCredentials([
                    [
                        $class: 'AmazonWebServicesCredentialsBinding',
                        credentialsId: 'aws-ecr'
                    ]
                ]) {

                    sh '''
                        set -e

                        aws sts get-caller-identity

                        aws ecr get-login-password \
                            --region ${AWS_REGION} |
                        docker login \
                            --username AWS \
                            --password-stdin \
                            ${ECR_REGISTRY}

                        echo ""
                        echo "ECR login successful."
                    '''
                }
            }
        }


        // =========================================================
        // 9. PUSH ERP BACKEND
        // =========================================================

        stage('Push ERP Backend') {

            steps {

                echo "=============================================="
                echo "Pushing ERP Backend"
                echo "=============================================="

                withCredentials([
                    [
                        $class: 'AmazonWebServicesCredentialsBinding',
                        credentialsId: 'aws-ecr'
                    ]
                ]) {

                    sh '''
                        set -e

                        docker push \
                            ${ECR_REGISTRY}/${ERP_BACKEND_REPO}:${IMAGE_TAG}

                        echo "ERP Backend pushed successfully."
                    '''
                }
            }
        }


        // =========================================================
        // 10. PUSH ERP FRONTEND
        // =========================================================

        stage('Push ERP Frontend') {

            steps {

                echo "=============================================="
                echo "Pushing ERP Frontend"
                echo "=============================================="

                withCredentials([
                    [
                        $class: 'AmazonWebServicesCredentialsBinding',
                        credentialsId: 'aws-ecr'
                    ]
                ]) {

                    sh '''
                        set -e

                        docker push \
                            ${ECR_REGISTRY}/${ERP_FRONTEND_REPO}:${IMAGE_TAG}

                        echo "ERP Frontend pushed successfully."
                    '''
                }
            }
        }


        // =========================================================
        // 11. PUSH POS BACKEND
        // =========================================================

        stage('Push POS Backend') {

            steps {

                echo "=============================================="
                echo "Pushing POS Backend"
                echo "=============================================="

                withCredentials([
                    [
                        $class: 'AmazonWebServicesCredentialsBinding',
                        credentialsId: 'aws-ecr'
                    ]
                ]) {

                    sh '''
                        set -e

                        docker push \
                            ${ECR_REGISTRY}/${POS_BACKEND_REPO}:${IMAGE_TAG}

                        echo "POS Backend pushed successfully."
                    '''
                }
            }
        }


        // =========================================================
        // 12. PUSH POS FRONTEND
        // =========================================================

        stage('Push POS Frontend') {

            steps {

                echo "=============================================="
                echo "Pushing POS Frontend"
                echo "=============================================="

                withCredentials([
                    [
                        $class: 'AmazonWebServicesCredentialsBinding',
                        credentialsId: 'aws-ecr'
                    ]
                ]) {

                    sh '''
                        set -e

                        docker push \
                            ${ECR_REGISTRY}/${POS_FRONTEND_REPO}:${IMAGE_TAG}

                        echo "POS Frontend pushed successfully."
                    '''
                }
            }
        }


        // =========================================================
        // 13. DEPLOY TO APPLICATION EC2
        // =========================================================

        stage('Deploy to Application EC2') {

            steps {

                echo "=============================================="
                echo "Deploying ERP-GOLD to Application EC2"
                echo "=============================================="

                sshagent(credentials: ['app-server-ssh']) {

                    sh """
                        ssh \
                            -o StrictHostKeyChecking=no \
                            ${APP_SERVER} \
                            '
                            set -e

                            echo "=============================================="
                            echo "Connected to Application EC2"
                            echo "=============================================="

                            cd ${APP_DIR}

                            echo "Current directory:"
                            pwd

                            echo ""
                            echo "Checking Docker..."
                            docker --version

                            echo ""
                            echo "Checking Docker Compose..."
                            docker compose version


                            echo ""
                            echo "=============================================="
                            echo "Logging into Amazon ECR"
                            echo "=============================================="

                            aws ecr get-login-password \
                                --region ${AWS_REGION} |
                            docker login \
                                --username AWS \
                                --password-stdin \
                                ${ECR_REGISTRY}


                            echo ""
                            echo "=============================================="
                            echo "Setting image variables"
                            echo "=============================================="

                            export IMAGE_TAG=${IMAGE_TAG}

                            export ERP_BACKEND_IMAGE=${ECR_REGISTRY}/${ERP_BACKEND_REPO}

                            export ERP_FRONTEND_IMAGE=${ECR_REGISTRY}/${ERP_FRONTEND_REPO}

                            export POS_BACKEND_IMAGE=${ECR_REGISTRY}/${POS_BACKEND_REPO}

                            export POS_FRONTEND_IMAGE=${ECR_REGISTRY}/${POS_FRONTEND_REPO}


                            echo "IMAGE_TAG=${IMAGE_TAG}"


                            echo ""
                            echo "=============================================="
                            echo "Pulling new Docker images"
                            echo "=============================================="

                            docker compose \
                                -f docker-compose.prod.yml \
                                pull


                            echo ""
                            echo "=============================================="
                            echo "Starting PostgreSQL"
                            echo "=============================================="

                            docker compose \
                                -f docker-compose.prod.yml \
                                up -d postgres


                            echo ""
                            echo "Waiting for PostgreSQL..."

                            sleep 10


                            echo ""
                            echo "=============================================="
                            echo "Running Database Migration"
                            echo "=============================================="

                            docker compose \
                                -f docker-compose.prod.yml \
                                run --rm migrate


                            echo ""
                            echo "Database migration completed successfully."


                            echo ""
                            echo "=============================================="
                            echo "Starting Application Services"
                            echo "=============================================="

                            docker compose \
                                -f docker-compose.prod.yml \
                                up -d \
                                erp-backend \
                                erp-mail-worker \
                                pos-backend \
                                erp-frontend \
                                pos-frontend


                            echo ""
                            echo "=============================================="
                            echo "Current Container Status"
                            echo "=============================================="

                            docker compose \
                                -f docker-compose.prod.yml \
                                ps


                            echo ""
                            echo "Application deployment completed."
                            '
                    """
                }
            }
        }


        // =========================================================
        // 14. VERIFY DEPLOYMENT
        // =========================================================

        stage('Verify Deployment') {

            steps {

                echo "=============================================="
                echo "Verifying ERP-GOLD Deployment"
                echo "=============================================="

                sshagent(credentials: ['app-server-ssh']) {

                    sh """
                        ssh \
                            -o StrictHostKeyChecking=no \
                            ${APP_SERVER} \
                            '
                            set -e

                            cd ${APP_DIR}


                            echo "=============================================="
                            echo "Container Status"
                            echo "=============================================="

                            docker compose \
                                -f docker-compose.prod.yml \
                                ps


                            echo ""
                            echo "=============================================="
                            echo "ERP Backend Health Check"
                            echo "=============================================="

                            curl \
                                --fail \
                                --silent \
                                --show-error \
                                http://127.0.0.1:8001/health \
                                > /dev/null

                            echo "ERP Backend: HEALTHY"


                            echo ""
                            echo "=============================================="
                            echo "POS Backend Health Check"
                            echo "=============================================="

                            curl \
                                --fail \
                                --silent \
                                --show-error \
                                http://127.0.0.1:8000/health \
                                > /dev/null

                            echo "POS Backend: HEALTHY"


                            echo ""
                            echo "=============================================="
                            echo "ERP Frontend Health Check"
                            echo "=============================================="

                            curl \
                                --fail \
                                --silent \
                                --show-error \
                                http://127.0.0.1:5174/ \
                                > /dev/null

                            echo "ERP Frontend: HEALTHY"


                            echo ""
                            echo "=============================================="
                            echo "POS Frontend Health Check"
                            echo "=============================================="

                            curl \
                                --fail \
                                --silent \
                                --show-error \
                                http://127.0.0.1:5173/ \
                                > /dev/null

                            echo "POS Frontend: HEALTHY"


                            echo ""
                            echo "=============================================="
                            echo "ERP-GOLD DEPLOYMENT VERIFIED"
                            echo "=============================================="
                            '
                    """
                }
            }
        }


        // =========================================================
        // 15. DOCKER CLEANUP
        // =========================================================

        stage('Docker Cleanup') {

            steps {

                echo "=============================================="
                echo "Cleaning unused Docker images"
                echo "=============================================="

                sshagent(credentials: ['app-server-ssh']) {

                    sh """
                        ssh \
                            -o StrictHostKeyChecking=no \
                            ${APP_SERVER} \
                            '
                            docker image prune -f
                            '
                    """
                }
            }
        }
    }


    // =============================================================
    // POST ACTIONS
    // =============================================================

    post {

        success {

            echo """
            ==================================================
                    ERP-GOLD DEPLOYMENT SUCCESSFUL
            ==================================================

            Build Number:
            ${BUILD_NUMBER}

            ERP Backend:
            ${ECR_REGISTRY}/${ERP_BACKEND_REPO}:${IMAGE_TAG}

            ERP Frontend:
            ${ECR_REGISTRY}/${ERP_FRONTEND_REPO}:${IMAGE_TAG}

            POS Backend:
            ${ECR_REGISTRY}/${POS_BACKEND_REPO}:${IMAGE_TAG}

            POS Frontend:
            ${ECR_REGISTRY}/${POS_FRONTEND_REPO}:${IMAGE_TAG}

            --------------------------------------------------

            ERP Application:
            http://16.16.216.155:5174

            ERP API:
            http://16.16.216.155:8001

            POS Application:
            http://16.16.216.155:5173

            POS API:
            http://16.16.216.155:8000

            ==================================================
            """
        }


        failure {

            echo """
            ==================================================
                    ERP-GOLD DEPLOYMENT FAILED
            ==================================================

            Build Number:
            ${BUILD_NUMBER}

            Check the Jenkins Console Output.

            ==================================================
            """
        }


        always {

            echo "Cleaning Jenkins workspace..."

            cleanWs()
        }
    }
}
