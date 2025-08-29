pipeline {
    agent any

    environment {
        registry_base = 'godminhkhoa'
        registryCredential = 'dockerhub'
        imageVersion = "0.0.1.${BUILD_NUMBER}"
    }

    stages {
        stage('Run Tests') {
            agent {
                docker {
                    image 'godminhkhoa/test-traffic-detection:1.0.8'
                    reuseNode true
                }
            }
            environment {
                ENABLE_TRACING = 'false'
                DISABLE_METRICS = 'true'
                STORAGE_BACKEND = 'local' 
                GCS_BUCKET_NAME = 'iee-project-2025-bucket'


                GOOGLE_APPLICATION_CREDENTIALS = credentials('GCP_KEY_FILE')
            }
            steps {
                script {
                    sh '''
                        pytest tests/ --maxfail=1 --disable-warnings -q
                    '''
                }
            }
        }

        stage('Build and Push Images') {
            parallel {
                stage('Build Detect App') {
                    steps {
                        script {
                            def imageName = "${registry_base}/predict-iee-app"
                            def dockerImage = docker.build("${imageName}:${imageVersion}", "-f ./app/Dockerfile .")
                            docker.withRegistry('', registryCredential) {
                                dockerImage.push()
                                dockerImage.push('latest')
                            }
                        }
                    }
                }
                stage('Build Ingesting') {
                    steps {
                        script {
                            def imageName = "${registry_base}/ingesting-iee-service"
                            def dockerImage = docker.build("${imageName}:${imageVersion}", "-f ./ingesting/Dockerfile .")
                            docker.withRegistry('', registryCredential) {
                                dockerImage.push()
                                dockerImage.push('latest')
                            }
                        }
                    }
                }

            }
        }
        
        stage('Deploy Services') {
            parallel {
                stage('Deploy Ingesting') {
                    agent {
                        kubernetes {
                            containerTemplate {
                                name 'helm'
                                image 'godminhkhoa/jenkins-k8s:latest'
                                alwaysPullImage true
                            }
                        }
                    }
                    steps {
                        container('helm') {
                            sh "helm upgrade --install ingesting-service ./helm_charts/ingesting --namespace traffic-detection --set deployment.image.name=${registry_base}/ingesting-iee-service --set deployment.image.version=${imageVersion}"
                        }
                    }
                }
                stage('Deploy Detection App') {
                    agent {
                        kubernetes {
                            containerTemplate {
                                name 'helm'
                                image 'godminhkhoa/jenkins-k8s:latest'
                                alwaysPullImage true
                            }
                        }
                    }
                    steps {
                        container('helm') {
                            sh "helm upgrade --install predict-service  ./helm_charts/predict --namespace traffic-detection --set deployment.image.name=${registry_base}/predict-iee-app --set deployment.image.version=${imageVersion}"
                        }
                    }
                }
            }
        }
    }
}
