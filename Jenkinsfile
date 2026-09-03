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
        // Example: Build #5 -> image tag 5
        // =========================================================

        IMAGE_TAG = "${BUILD_NUMBER}"


        // =========================================================
        // APPLICATION EC2
        // =========================================================

        APP_SERVER = "ubuntu@16.16.216.155"

        APP_DIR = "/opt/erp-gold"


        // =========================================================
        // FRONTEND API URLS
        // These are compiled into React during Docker build
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

                    pwd

                    echo ""
                    echo "Repository contents:"
                    ls -la

                    echo ""
                    echo "Checking ERP Backend..."
                    test -d ERP-Backend
                    test -f ERP-Backend/Dockerfile

                    echo "Checking ERP Frontend..."
                    test -d ERP-Frontend
                    test -f ERP-Frontend/Dockerfile

                    echo "Checking POS Backend..."
                    test -d POS-Backend
                    test -f POS-Backend/Dockerfile

                    echo "Checking POS Frontend..."
                    test -d POS-Frontend
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
                    echo "ERP Backend build completed."
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
                    echo "POS Backend build completed."
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
                    echo "ERP Frontend build completed."
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
                    echo "POS Frontend build completed."
                '''
            }
        }


        // =========================================================
        // 7. LOGIN TO AMAZON ECR
        //
        // IMPORTANT:
        // This intentionally follows your previous working
        // Jenkinsfile.
        //
        // Jenkins credential:
        // aws-ecr
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

                        echo "AWS CLI:"
                        aws --version

                        echo ""
                        echo "Logging into Amazon ECR..."

                        aws ecr get-login-password \
                            --region ${AWS_REGION} |
                        docker login \
                            --username AWS \
                            --password-stdin \
                            ${ECR_REGISTRY}

                        echo ""
                        echo "=============================================="
                        echo "ECR LOGIN SUCCESSFUL"
                        echo "=============================================="
                    '''
                }
            }
        }


        // =========================================================
        // 8. PUSH ERP BACKEND
        // =========================================================

        stage('Push ERP Backend') {

            steps {

                echo "=============================================="
                echo "Pushing ERP Backend Image"
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

                        echo ""
                        echo "ERP Backend pushed successfully."
                    '''
                }
            }
        }


        // =========================================================
        // 9. PUSH ERP FRONTEND
        // =========================================================

        stage('Push ERP Frontend') {

            steps {

                echo "=============================================="
                echo "Pushing ERP Frontend Image"
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

                        echo ""
                        echo "ERP Frontend pushed successfully."
                    '''
                }
            }
        }


        // =========================================================
        // 10. PUSH POS BACKEND
        // =========================================================

        stage('Push POS Backend') {

            steps {

                echo "=============================================="
                echo "Pushing POS Backend Image"
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

                        echo ""
                        echo "POS Backend pushed successfully."
                    '''
                }
            }
        }


        // =========================================================
        // 11. PUSH POS FRONTEND
        // =========================================================

        stage('Push POS Frontend') {

            steps {

                echo "=============================================="
                echo "Pushing POS Frontend Image"
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

                        echo ""
                        echo "POS Frontend pushed successfully."
                    '''
                }
            }
        }


        // =========================================================
        // 12. DEPLOY TO APPLICATION EC2
        //
        // Jenkins:
        //   SSH -> Application EC2
        //
        // Application EC2:
        //   ECR login
        //   Pull images
        //   Start PostgreSQL
        //   Run migration
        //   Start applications
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


                            echo ""
                            echo "=============================================="
                            echo "Docker Version"
                            echo "=============================================="

                            docker --version


                            echo ""
                            echo "=============================================="
                            echo "Docker Compose Version"
                            echo "=============================================="

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
                            echo "Setting Image Variables"
                            echo "=============================================="

                            export IMAGE_TAG=${IMAGE_TAG}

                            export ERP_BACKEND_IMAGE=${ECR_REGISTRY}/${ERP_BACKEND_REPO}

                            export ERP_FRONTEND_IMAGE=${ECR_REGISTRY}/${ERP_FRONTEND_REPO}

                            export POS_BACKEND_IMAGE=${ECR_REGISTRY}/${POS_BACKEND_REPO}

                            export POS_FRONTEND_IMAGE=${ECR_REGISTRY}/${POS_FRONTEND_REPO}

                            echo "IMAGE_TAG = ${IMAGE_TAG}"

                            echo "ERP_BACKEND_IMAGE = ${ECR_REGISTRY}/${ERP_BACKEND_REPO}"

                            echo "ERP_FRONTEND_IMAGE = ${ECR_REGISTRY}/${ERP_FRONTEND_REPO}"

                            echo "POS_BACKEND_IMAGE = ${ECR_REGISTRY}/${POS_BACKEND_REPO}"

                            echo "POS_FRONTEND_IMAGE = ${ECR_REGISTRY}/${POS_FRONTEND_REPO}"


                            echo ""
                            echo "=============================================="
                            echo "Pulling New Images"
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
                            echo "Starting ERP Backend"
                            echo "=============================================="

                            docker compose \
                                -f docker-compose.prod.yml \
                                up -d erp-backend


                            echo ""
                            echo "=============================================="
                            echo "Starting ERP Mail Worker"
                            echo "=============================================="

                            docker compose \
                                -f docker-compose.prod.yml \
                                up -d erp-mail-worker


                            echo ""
                            echo "=============================================="
                            echo "Starting POS Backend"
                            echo "=============================================="

                            docker compose \
                                -f docker-compose.prod.yml \
                                up -d pos-backend


                            echo ""
                            echo "=============================================="
                            echo "Starting ERP Frontend"
                            echo "=============================================="

                            docker compose \
                                -f docker-compose.prod.yml \
                                up -d erp-frontend


                            echo ""
                            echo "=============================================="
                            echo "Starting POS Frontend"
                            echo "=============================================="

                            docker compose \
                                -f docker-compose.prod.yml \
                                up -d pos-frontend


                            echo ""
                            echo "=============================================="
                            echo "Current Container Status"
                            echo "=============================================="

                            docker compose \
                                -f docker-compose.prod.yml \
                                ps


                            echo ""
                            echo "=============================================="
                            echo "Application Deployment Completed"
                            echo "=============================================="
                            '
                    """
                }
            }
        }


        // =========================================================
        // 13. VERIFY DEPLOYMENT
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
                            echo "Waiting for Backends"
                            echo "=============================================="

                            sleep 10


                            echo ""
                            echo "=============================================="
                            echo "ERP Backend Health Check"
                            echo "=============================================="

                            for i in 1 2 3 4 5 6; do

                                if curl \
                                    --fail \
                                    --silent \
                                    --show-error \
                                    http://127.0.0.1:8001/health \
                                    > /dev/null
                                then

                                    echo "ERP Backend: HEALTHY"
                                    break

                                fi

                                echo "ERP Backend not ready. Attempt \$i/6..."

                                sleep 5

                                if [ \$i -eq 6 ]; then
                                    echo "ERP Backend health check FAILED"
                                    exit 1
                                fi

                            done


                            echo ""
                            echo "=============================================="
                            echo "POS Backend Health Check"
                            echo "=============================================="

                            for i in 1 2 3 4 5 6; do

                                if curl \
                                    --fail \
                                    --silent \
                                    --show-error \
                                    http://127.0.0.1:8000/health \
                                    > /dev/null
                                then

                                    echo "POS Backend: HEALTHY"
                                    break

                                fi

                                echo "POS Backend not ready. Attempt \$i/6..."

                                sleep 5

                                if [ \$i -eq 6 ]; then
                                    echo "POS Backend health check FAILED"
                                    exit 1
                                fi

                            done


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
        // 14. DOCKER CLEANUP
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
            ======================================================
                    ERP-GOLD DEPLOYMENT SUCCESSFUL
            ======================================================

            Build Number:
            ${BUILD_NUMBER}

            ------------------------------------------------------

            ERP Backend:
            ${ECR_REGISTRY}/${ERP_BACKEND_REPO}:${IMAGE_TAG}

            ERP Frontend:
            ${ECR_REGISTRY}/${ERP_FRONTEND_REPO}:${IMAGE_TAG}

            POS Backend:
            ${ECR_REGISTRY}/${POS_BACKEND_REPO}:${IMAGE_TAG}

            POS Frontend:
            ${ECR_REGISTRY}/${POS_FRONTEND_REPO}:${IMAGE_TAG}

            ------------------------------------------------------

            ERP Application:
            http://16.16.216.155:5174

            ERP API:
            http://16.16.216.155:8001

            POS Application:
            http://16.16.216.155:5173

            POS API:
            http://16.16.216.155:8000

            ======================================================
            """
        }


        failure {

            echo """
            ======================================================
                    ERP-GOLD DEPLOYMENT FAILED
            ======================================================

            Build Number:
            ${BUILD_NUMBER}

            Please check the Jenkins Console Output.

            ======================================================
            """
        }


        always {

            echo "Cleaning Jenkins workspace..."

            cleanWs()
        }
    }
}
