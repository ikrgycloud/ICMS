pipeline {

    agent any

    environment {

        AWS_REGION = "eu-north-1"

        BACKEND_REPOSITORY = "icms-backend"
        FRONTEND_REPOSITORY = "icms-frontend"

        APPLICATION_SERVER = "ubuntu@YOUR_APPLICATION_EC2_IP"

        APPLICATION_DIRECTORY = "/opt/icms"

        SSH_CREDENTIALS = "icms-app-server-ssh"
    }

    stages {

        stage('Checkout') {

            steps {

                echo "========================================"
                echo "Checking out ICMS"
                echo "========================================"

                checkout scm

                sh '''
                    echo "Commit:"
                    git rev-parse HEAD

                    echo ""
                    echo "Repository:"
                    ls -la
                '''
            }
        }


        stage('Initialize Build Variables') {

            steps {

                script {

                    env.AWS_ACCOUNT_ID = sh(
                        script: '''
                            aws sts get-caller-identity \
                            --query Account \
                            --output text
                        ''',
                        returnStdout: true
                    ).trim()

                    env.ECR_REGISTRY =
                        "${env.AWS_ACCOUNT_ID}.dkr.ecr.${env.AWS_REGION}.amazonaws.com"

                    env.BACKEND_IMAGE =
                        "${env.ECR_REGISTRY}/${env.BACKEND_REPOSITORY}"

                    env.FRONTEND_IMAGE =
                        "${env.ECR_REGISTRY}/${env.FRONTEND_REPOSITORY}"

                    env.IMAGE_TAG = "${env.BUILD_NUMBER}"

                    echo "AWS Account: ${env.AWS_ACCOUNT_ID}"
                    echo "ECR Registry: ${env.ECR_REGISTRY}"
                    echo "Image Tag: ${env.IMAGE_TAG}"
                }
            }
        }


        stage('Build Backend') {

            steps {

                echo "========================================"
                echo "Building Backend"
                echo "========================================"

                sh """
                    docker build \
                        -t ${BACKEND_IMAGE}:${IMAGE_TAG} \
                        ./backend
                """
            }
        }


        stage('Build Frontend') {

            steps {

                echo "========================================"
                echo "Building Frontend"
                echo "========================================"

                sh """
                    docker build \
                        -t ${FRONTEND_IMAGE}:${IMAGE_TAG} \
                        ./frontend
                """
            }
        }


        stage('Login to Amazon ECR') {

            steps {

                echo "========================================"
                echo "Logging into ECR"
                echo "========================================"

                sh """
                    aws ecr get-login-password \
                        --region ${AWS_REGION} |
                    docker login \
                        --username AWS \
                        --password-stdin ${ECR_REGISTRY}
                """
            }
        }


        stage('Push Backend Image') {

            steps {

                echo "Pushing Backend image..."

                sh """
                    docker push \
                        ${BACKEND_IMAGE}:${IMAGE_TAG}
                """
            }
        }


        stage('Push Frontend Image') {

            steps {

                echo "Pushing Frontend image..."

                sh """
                    docker push \
                        ${FRONTEND_IMAGE}:${IMAGE_TAG}
                """
            }
        }


        stage('Prepare Application Server') {

            steps {

                echo "Preparing Application EC2..."

                sshagent(credentials: [SSH_CREDENTIALS]) {

                    sh """
                        ssh \
                            -o StrictHostKeyChecking=no \
                            ${APPLICATION_SERVER} \
                            "mkdir -p ${APPLICATION_DIRECTORY}"
                    """
                }
            }
        }


        stage('Copy Production Compose') {

            steps {

                echo "Copying production Compose file..."

                sshagent(credentials: [SSH_CREDENTIALS]) {

                    sh """
                        scp \
                            -o StrictHostKeyChecking=no \
                            docker-compose.prod.yml \
                            ${APPLICATION_SERVER}:${APPLICATION_DIRECTORY}/docker-compose.prod.yml
                    """
                }
            }
        }


        stage('Login Application EC2 to ECR') {

            steps {

                echo "Logging Application EC2 into ECR..."

                sshagent(credentials: [SSH_CREDENTIALS]) {

                    sh """
                        ssh \
                            -o StrictHostKeyChecking=no \
                            ${APPLICATION_SERVER} \
                            "
                            aws ecr get-login-password \
                                --region ${AWS_REGION} |
                            docker login \
                                --username AWS \
                                --password-stdin ${ECR_REGISTRY}
                            "
                    """
                }
            }
        }


        stage('Deploy') {

            steps {

                echo "========================================"
                echo "Deploying ICMS"
                echo "========================================"

                sshagent(credentials: [SSH_CREDENTIALS]) {

                    sh """
                        ssh \
                            -o StrictHostKeyChecking=no \
                            ${APPLICATION_SERVER} \
                            "
                            cd ${APPLICATION_DIRECTORY} &&

                            export BACKEND_IMAGE=${BACKEND_IMAGE}:${IMAGE_TAG} &&
                            export FRONTEND_IMAGE=${FRONTEND_IMAGE}:${IMAGE_TAG} &&

                            docker compose \
                                -f docker-compose.prod.yml \
                                pull backend frontend &&

                            docker compose \
                                -f docker-compose.prod.yml \
                                up -d db backend frontend
                            "
                    """
                }
            }
        }


        stage('Verify Deployment') {

            steps {

                echo "========================================"
                echo "Verifying Deployment"
                echo "========================================"

                sshagent(credentials: [SSH_CREDENTIALS]) {

                    sh """
                        ssh \
                            -o StrictHostKeyChecking=no \
                            ${APPLICATION_SERVER} \
                            "
                            cd ${APPLICATION_DIRECTORY} &&

                            docker compose \
                                -f docker-compose.prod.yml \
                                ps
                            "
                    """
                }
            }
        }
    }


    post {

        success {

            echo """
            ==========================================
              ICMS DEPLOYMENT SUCCESSFUL
            ==========================================

            Backend:
            ${BACKEND_IMAGE}:${IMAGE_TAG}

            Frontend:
            ${FRONTEND_IMAGE}:${IMAGE_TAG}

            Application Server:
            ${APPLICATION_SERVER}

            ==========================================
            """
        }


        failure {

            echo """
            ==========================================
              ICMS DEPLOYMENT FAILED
            ==========================================

            Jenkins Build:
            ${BUILD_NUMBER}

            Check Jenkins Console Output.

            ==========================================
            """
        }


        always {

            sh '''
                docker logout ${ECR_REGISTRY} || true
                docker image prune -f || true
            '''
        }
    }
}
