pipeline {

    agent any

    environment {

        AWS_REGION     = "eu-north-1"
        AWS_ACCOUNT_ID = "032844082845"

        BACKEND_REPO  = "icms-backend"
        FRONTEND_REPO = "icms-frontend"

        IMAGE_TAG = "${BUILD_NUMBER}"

        ECR_REGISTRY =
            "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

        // IMPORTANT:
        // Replace this with the REAL PUBLIC IP or reachable private IP
        // of your ICMS Application EC2.
        APP_SERVER = "ubuntu@16.16.216.155"

        APP_DIR = "/opt/icms"
    }


    stages {

        /*
         * ============================================================
         * 1. CHECKOUT
         * ============================================================
         */

        stage('Checkout') {

            steps {

                echo "======================================="
                echo "Checking out ICMS source code"
                echo "======================================="

                checkout scm
            }
        }


        /*
         * ============================================================
         * 2. BUILD BACKEND
         * ============================================================
         */

        stage('Build Backend') {

            steps {

                echo "======================================="
                echo "Building ICMS Backend"
                echo "======================================="

                sh """
                    docker build \
                        -t ${BACKEND_REPO}:${IMAGE_TAG} \
                        ./backend
                """
            }
        }


        /*
         * ============================================================
         * 3. BUILD FRONTEND
         * ============================================================
         */

        stage('Build Frontend') {

            steps {

                echo "======================================="
                echo "Building ICMS Frontend"
                echo "======================================="

                sh """
                    docker build \
                        -t ${FRONTEND_REPO}:${IMAGE_TAG} \
                        ./frontend
                """
            }
        }


        /*
         * ============================================================
         * 4. LOGIN TO ECR
         * ============================================================
         */

        stage('Login to Amazon ECR') {

            steps {

                echo "======================================="
                echo "Logging into Amazon ECR"
                echo "======================================="

                withCredentials([
                    [
                        $class: 'AmazonWebServicesCredentialsBinding',
                        credentialsId: 'aws-ecr'
                    ]
                ]) {

                    sh """
                        aws ecr get-login-password \
                            --region ${AWS_REGION} |
                        docker login \
                            --username AWS \
                            --password-stdin \
                            ${ECR_REGISTRY}
                    """
                }
            }
        }


        /*
         * ============================================================
         * 5. TAG IMAGES
         * ============================================================
         */

        stage('Tag Images') {

            steps {

                echo "======================================="
                echo "Tagging Docker Images"
                echo "======================================="

                sh """
                    docker tag \
                        ${BACKEND_REPO}:${IMAGE_TAG} \
                        ${ECR_REGISTRY}/${BACKEND_REPO}:${IMAGE_TAG}

                    docker tag \
                        ${FRONTEND_REPO}:${IMAGE_TAG} \
                        ${ECR_REGISTRY}/${FRONTEND_REPO}:${IMAGE_TAG}
                """
            }
        }


        /*
         * ============================================================
         * 6. PUSH BACKEND
         * ============================================================
         */

        stage('Push Backend') {

            steps {

                echo "======================================="
                echo "Pushing Backend Image"
                echo "======================================="

                withCredentials([
                    [
                        $class: 'AmazonWebServicesCredentialsBinding',
                        credentialsId: 'aws-ecr'
                    ]
                ]) {

                    sh """
                        docker push \
                            ${ECR_REGISTRY}/${BACKEND_REPO}:${IMAGE_TAG}
                    """
                }
            }
        }


        /*
         * ============================================================
         * 7. PUSH FRONTEND
         * ============================================================
         */

        stage('Push Frontend') {

            steps {

                echo "======================================="
                echo "Pushing Frontend Image"
                echo "======================================="

                withCredentials([
                    [
                        $class: 'AmazonWebServicesCredentialsBinding',
                        credentialsId: 'aws-ecr'
                    ]
                ]) {

                    sh """
                        docker push \
                            ${ECR_REGISTRY}/${FRONTEND_REPO}:${IMAGE_TAG}
                    """
                }
            }
        }


        /*
         * ============================================================
         * 8. DEPLOY TO APPLICATION EC2
         * ============================================================
         */

        stage('Deploy to Application EC2') {

            steps {

                echo "======================================="
                echo "Deploying ICMS to Application EC2"
                echo "======================================="

                sshagent(credentials: ['app-server-ssh']) {

                    sh """
                        ssh \
                            -o StrictHostKeyChecking=no \
                            ${APP_SERVER} \
                            '
                            set -e

                            echo "Connected to Application EC2"

                            echo "Changing directory..."

                            cd ${APP_DIR}

                            echo "Checking Docker..."

                            docker --version

                            echo "Checking Docker Compose..."

                            docker compose version

                            echo "Logging Application EC2 into ECR..."

                            aws ecr get-login-password \
                                --region ${AWS_REGION} |
                            docker login \
                                --username AWS \
                                --password-stdin \
                                ${ECR_REGISTRY}

                            echo "Pulling new ICMS images..."

                            export BACKEND_IMAGE=${ECR_REGISTRY}/${BACKEND_REPO}:${IMAGE_TAG}
                            export FRONTEND_IMAGE=${ECR_REGISTRY}/${FRONTEND_REPO}:${IMAGE_TAG}

                            docker compose \
                                -f docker-compose.prod.yml \
                                pull backend frontend

                            echo "Starting / updating ICMS services..."

                            docker compose \
                                -f docker-compose.prod.yml \
                                up -d

                            echo "Deployment completed."

                            echo "Current container status:"

                            docker compose \
                                -f docker-compose.prod.yml \
                                ps
                            '
                    """
                }
            }
        }


        /*
         * ============================================================
         * 9. VERIFY DEPLOYMENT
         * ============================================================
         */

        stage('Verify Deployment') {

            steps {

                echo "======================================="
                echo "Verifying ICMS Deployment"
                echo "======================================="

                sshagent(credentials: ['app-server-ssh']) {

                    sh """
                        ssh \
                            -o StrictHostKeyChecking=no \
                            ${APP_SERVER} \
                            '
                            set -e

                            cd ${APP_DIR}

                            echo "======================================="
                            echo "Container Status"
                            echo "======================================="

                            docker compose \
                                -f docker-compose.prod.yml \
                                ps

                            echo "======================================="
                            echo "Frontend Health Check"
                            echo "======================================="

                            curl \
                                --fail \
                                --silent \
                                --show-error \
                                http://localhost:84/ \
                                > /dev/null

                            echo "Frontend is UP"

                            echo "======================================="
                            echo "ICMS Deployment Verified"
                            echo "======================================="
                            '
                    """
                }
            }
        }
    }


    /*
     * ================================================================
     * POST ACTIONS
     * ================================================================
     */

    post {

        success {

            echo """
            =======================================
              ICMS DEPLOYMENT SUCCESSFUL
            =======================================

            Build Number:
            ${BUILD_NUMBER}

            Backend Image:
            ${ECR_REGISTRY}/${BACKEND_REPO}:${IMAGE_TAG}

            Frontend Image:
            ${ECR_REGISTRY}/${FRONTEND_REPO}:${IMAGE_TAG}

            Application Server:
            ${APP_SERVER}

            =======================================
            """
        }


        failure {

            echo """
            =======================================
              ICMS DEPLOYMENT FAILED
            =======================================

            Build Number:
            ${BUILD_NUMBER}

            Check Jenkins Console Output.

            =======================================
            """
        }


        always {

            cleanWs()
        }
    }
}
