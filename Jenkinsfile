pipeline {
    agent any

    environment {
        registry_base = 'godminhkhoa'
        registryCredential = 'dockerhub'
        imageVersion = "0.0.1.${BUILD_NUMBER}"
        discordWebhook = credentials('DISCORD_WEBHOOK')
    }

    stages {
        stage('Run Tests') {
            steps {
                script {
                    docker.image('godminhkhoa/test-traffic-detection:1.0.8').inside {
                        withEnv([
                            "ENABLE_TRACING=false",
                            "DISABLE_METRICS=true",
                            "STORAGE_BACKEND=local",
                            "GCS_BUCKET_NAME=iee-project-2025-bucket"
                        ]) {
                            withCredentials([file(credentialsId: 'GCP_KEY_FILE', variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {
                                sh 'pytest tests/ --maxfail=1 --disable-warnings -q'
                            }
                        }
                    }
                }
            }
        }

        stage('Build and Push Images') {
            when { branch 'master' }   // chỉ chạy khi nhánh là master
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
            when { branch 'master' }   // chỉ deploy khi nhánh là master
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
                            sh "helm upgrade --install predict-service ./helm_charts/predict --namespace traffic-detection --set deployment.image.name=${registry_base}/predict-iee-app --set deployment.image.version=${imageVersion}"
                        }
                    }
                }
            }
        }

        stage('Notify Discord') {
            steps {
                script {
                    def status = currentBuild.currentResult
                    def timeNow = sh(script: "date -u +'%Y-%m-%d %H:%M UTC'", returnStdout: true).trim()
                    def runUrl = env.BUILD_URL
                    def msg = ""

                    if (env.BRANCH_NAME != "master") {
                        // Với nhánh khác master → chỉ chạy test
                        if (status == "SUCCESS") {
                            msg = "✅ Dev tests passed (branch: ${env.BRANCH_NAME})"
                        } else {
                            msg = "❌ Dev tests failed (branch: ${env.BRANCH_NAME})"
                        }
                    } else {
                        // Với master → test + build + deploy
                        if (status == "SUCCESS") {
                            msg = "✅ Tests passed, images pushed & deployed 🎉"
                        } else if (status == "UNSTABLE") {
                            msg = "⚠️ Tests passed but some stages failed"
                        } else {
                            msg = "❌ Pipeline failed"
                        }
                    }

                    def payload = """{
                      "content": "${msg}\\n[Run Logs](${runUrl}) at ${timeNow}"
                    }"""

                    sh """
                      curl -H "Content-Type: application/json" \
                      -X POST -d '${payload}' $discordWebhook
                    """
                }
            }
        }
    }
}
