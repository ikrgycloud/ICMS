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

        APP_SERVER = "ubuntu@YOUR_APPLICATION_EC2_IP"

        APP_DIR = "/opt/icms"
    }


    stages {

        stage('Checkout') {

            steps {

                echo "======================================="
                echo "Checking out ICMS source code"
                echo "======================================="

                checkout scm
            }
        }


        stage('Build Backend') {

            steps {

                echo "Building ICMS backend..."

                sh """
                    docker build \
                        -t ${BACKEND_REPO}:${IMAGE_TAG} \
                        ./backend
                """
            }
        }


        stage('Build Frontend') {

            steps {

                echo "Building ICMS frontend..."

                sh """
                    docker build \
                        -t ${FRONTEND_REPO}:${IMAGE_TAG} \
                        ./frontend
                """
            }
        }


        stage('Login to Amazon ECR') {

            steps {

                echo "Logging into Amazon ECR..."

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


        stage('Tag Images') {

            steps {

                echo "Tagging Docker images..."

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


        stage('Push Backend') {

            steps {

                echo "Pushing backend image to ECR..."

                sh """
                    docker push \
                        ${ECR_REGISTRY}/${BACKEND_REPO}:${IMAGE_TAG}
                """
            }
        }


        stage('Push Frontend') {

            steps {

                echo "Pushing frontend image to ECR..."

                sh """
                    docker push \
                        ${ECR_REGISTRY}/${FRONTEND_REPO}:${IMAGE_TAG}
                """
            }
        }


        stage('Deploy to Application EC2') {

            steps {

                echo "======================================="
                echo "Deploying ICMS to Application EC2"
                echo "======================================="

                sshagent(credentials: ['app-server-ssh']) {

                    withCredentials([
                        [
                            $class: 'AmazonWebServicesCredentialsBinding',
                            credentialsId: 'aws-ecr'
                        ]
                    ]) {

                        sh """
                            ssh \
                                -o StrictHostKeyChecking=no \
                                ${APP_SERVER} \
                                '
                                set -e

                                cd ${APP_DIR}

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
                                    pull

                                echo "Starting ICMS services..."

                                docker compose \
                                    -f docker-compose.prod.yml \
                                    up -d

                                echo "Deployment completed."

                                docker compose \
                                    -f docker-compose.prod.yml \
                                    ps
                                '
                        """
                    }
                }
            }
        }


        stage('Verify Deployment') {

            steps {

                echo "Verifying ICMS deployment..."

                sshagent(credentials: ['app-server-ssh']) {

                    sh """
                        ssh \
                            -o StrictHostKeyChecking=no \
                            ${APP_SERVER} \
                            '
                            cd ${APP_DIR}

                            echo "======================================="
                            echo "Container Status"
                            echo "======================================="

                            docker compose \
                                -f docker-compose.prod.yml \
                                ps

                            echo "======================================="
                            echo "Frontend Check"
                            echo "======================================="

                            curl -f http://localhost:8080/ \
                                > /dev/null

                            echo "Frontend is UP"
                            '
                    """
                }
            }
        }
    }


    post {

        success {

            echo """
            =======================================
            ICMS DEPLOYMENT SUCCESSFUL
            =======================================

            Build Number : ${BUILD_NUMBER}

            Backend:
            ${ECR_REGISTRY}/${BACKEND_REPO}:${IMAGE_TAG}

            Frontend:
            ${ECR_REGISTRY}/${FRONTEND_REPO}:${IMAGE_TAG}

            Application:
            ${APP_SERVER}

            =======================================
            """
        }


        failure {

            echo """
            =======================================
            ICMS DEPLOYMENT FAILED
            =======================================

            Build Number : ${BUILD_NUMBER}

            Check Jenkins Console Output.

            =======================================
            """
        }


        always {

            cleanWs()
        }
    }
}
