# Traffic-Sign-Detection
## System Architecture

## Technology
* Source control: [![Git/Github][Github-logo]][Github-url]
* CI/CD: [![Jenkins][Jenkins-logo]][Jenkins-url]
* Build API: [![FastAPI][FastAPI-logo]][FastAPI-url]
* Containerize application: [![Docker][Docker-logo]][Docker-url]
* Container orchestration system: [![Kubernetes(K8s)][Kubernetes-logo]][Kubernetes-url]
* K8s's package manager: [![Helm][Helm-logo]][Helm-url]
* Data Storage for images: [![Google Cloud Storage][Google-Cloud-Storage-logo]][Google-Cloud-Storage-url]
* Ingress controller: [![Nginx][Nginx-logo]][Nginx-url]
* Observable tools: [![Prometheus][Prometheus-logo]][Prometheus-url] [![Elasticsearch][Elasticsearch-logo]][Elasticsearch-url] [![Grafana][Grafana-logo]][Grafana-url] [![Jaeger][Jaeger-logo]][Jaeger-url] [![Kibana][Kibana-logo]][Kibana-url]
* Deliver infrastructure as code: [![Ansible][Ansible-logo]][Ansible-url] [![Terraform][Terraform-logo]][Terraform-url]
* Cloud platform: [![GCP][GCP-logo]][GCP-url]

## Project Structure


# Tables of contents

1. [Create GKE Cluster](#1-create-gke-cluster)





## 1. Create GKE Cluster

### 1.1. Create a [Project](https://console.cloud.google.com/projectcreate) in Google Cloud Platform (GCP)
Start by creating a new project on Google Cloud Platform.
### 1.2. Install the Google Cloud CLI
Follow the instructions in the https://cloud.google.com/sdk/docs/install#deb to install the gcloud CLI on your local machine.

### 1.3. Install gke-cloud-auth-plugin
Install the GKE-specific authentication plugin with the following command:
```bash
sudo apt-get install google-cloud-cli-gke-gcloud-auth-plugin
```

### 1.4. Using [terraform](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli) to create GKE cluster
Update the value of <your_project_id> in `terraform/variables.tf`. Then run the following commands to initialize and apply the Terraform configuration:
```bash
cd terraform
terraform init
terraform plan
terraform apply
```
+ The GKE cluster will be deployed in the **asia-southeast1** region.
+ Each node will use the machine type **e2-standard-4** (4 vCPUs, 16 GB RAM, approx. $396.51/month).
+ The cluster is configured in **Standard mode**, not **Autopilot**. Autopilot mode is not recommended in this setup because it restricts certain functionalities such as Prometheus-based node metrics scraping.

Provisioning may take up to 10 minutes. You can monitor the cluster status via the [GKE Console](https://console.cloud.google.com/kubernetes/list).

### 1.5. Connect to the GKE cluster
+ Go to the [GKE Console](https://console.cloud.google.com/kubernetes/list).
+ Select your cluster and click **Connect**.
+ Copy and run the `gcloud container clusters get-credentials ...` command provided.

For example:
```bash
(IEE) godminhkhoa@CaoKhoa29072005:~/Documents/Final_Project_IEE/iac/terraform$ gcloud container clusters get-credentials iee-project-2025-gke --region asia-southeast1 --project iee-project-2025
Fetching cluster endpoint and auth data.
kubeconfig entry generated for iee-project-2025-gke.
```


Once authenticated, you can verify the connection using:
```bash
kubectx
```

For example:

```bash
(IEE) godminhkhoa@CaoKhoa29072005:~/Documents/Final_Project_IEE/iac/terraform$ kubectx
gke_iee-project-2025_asia-southeast1_iee-project-2025-gke
```

### 1.6 Download service account keys

Để tải file Service Account key dưới dạng JSON từ Google Cloud Console, thực hiện như sau:

+ **Truy cập Google Cloud Console**:  
  Mở [https://console.cloud.google.com/](https://console.cloud.google.com/) và đảm bảo bạn đang chọn đúng project (ví dụ: `iee-project-2025`).

+ **Đi đến trang Service Accounts**:  
  Trong menu bên trái, chọn **IAM & Admin** → **Service Accounts**.

+ **Tìm Service Account cần lấy key**:  
  Ví dụ: `ingest-sa@iee-project-2025.iam.gserviceaccount.com`.

+ **Vào phần Manage keys**:  
  Ở cột **Actions** của service account, nhấn vào biểu tượng **3 chấm** → chọn **Manage keys**.

+ **Tạo key mới**:  
  Nhấn **Add Key** → **Create new key**.

+ **Chọn định dạng key**:  
  Chọn **Key type** = `JSON`.

+ **Tải xuống key**:  
  Nhấn **Create**.  
  File JSON sẽ được tải về tự động (ví dụ: `iee-project-2025-123abc456def.json`).

+ **Lưu trữ key an toàn**:  
  Lưu file JSON vào vị trí an toàn (ví dụ: `~/sa-ingest.json`).  
  **Không commit** key vào repository công khai.

+ **Xuất biến môi trường để ứng dụng sử dụng key**:
  ```bash
  export GOOGLE_APPLICATION_CREDENTIALS=~/sa-ingest.json
  ```


<!-- MARKDOWN LINKS & IMAGES -->
[Github-logo]: https://img.shields.io/badge/GitHub-181717?logo=github&logoColor=white
[Github-url]: https://github.com/

[Jenkins-logo]: https://img.shields.io/badge/Jenkins-ff6600?logo=jenkins&logoColor=white
[Jenkins-url]: https://www.jenkins.io/

[FastAPI-logo]: https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white
[FastAPI-url]: https://fastapi.tiangolo.com/

[Docker-logo]: https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white
[Docker-url]: https://www.docker.com/

[Kubernetes-logo]: https://img.shields.io/badge/Kubernetes-326CE5?logo=kubernetes&logoColor=white
[Kubernetes-url]: https://kubernetes.io/

[Helm-logo]: https://img.shields.io/badge/Helm-0F1689?logo=helm&logoColor=white
[Helm-url]: https://helm.sh/

[Google-Cloud-Storage-logo]: https://img.shields.io/badge/Google_Cloud_Storage-4285F4?logo=google-cloud&logoColor=white
[Google-Cloud-Storage-url]: https://cloud.google.com/storage

[Pinecone-logo]: https://img.shields.io/badge/Pinecone-4A90E2?logo=pinecone&logoColor=white
[Pinecone-url]: https://www.pinecone.io

[Google-Cloud-Functions-logo]: https://img.shields.io/badge/Google_Cloud_Functions-4285F4?logo=google-cloud&logoColor=white
[Google-Cloud-Functions-url]: https://cloud.google.com/functions

[Nginx-logo]: https://img.shields.io/badge/Nginx-009639?logo=nginx&logoColor=white
[Nginx-url]: https://docs.nginx.com/nginx-ingress-controller/

[Prometheus-logo]: https://img.shields.io/badge/Prometheus-E6522C?logo=prometheus&logoColor=white
[Prometheus-url]: https://prometheus.io/

[Elasticsearch-logo]: https://img.shields.io/badge/Elasticsearch-005571?logo=elasticsearch&logoColor=white
[Elasticsearch-url]: https://www.elastic.co/elasticsearch

[Kibana-logo]: https://img.shields.io/badge/Kibana-00BFB3?logo=kibana&logoColor=white
[Kibana-url]: https://www.elastic.co/kibana

[Grafana-logo]: https://img.shields.io/badge/Grafana-009C84?logo=grafana&logoColor=white
[Grafana-url]: https://grafana.com/

[Jaeger-logo]: https://img.shields.io/badge/Jaeger-5E8E88?logo=jaeger&logoColor=white
[Jaeger-url]: https://www.jaegertracing.io/

[Ansible-logo]: https://img.shields.io/badge/Ansible-3A3A3A?logo=ansible&logoColor=white
[Ansible-url]: https://www.ansible.com/

[Terraform-logo]: https://img.shields.io/badge/Terraform-7A4D8C?logo=terraform&logoColor=white
[Terraform-url]: https://www.terraform.io/

[GCP-logo]: https://img.shields.io/badge/Google_Cloud_Platform-4285F4?logo=google-cloud&logoColor=white
[GCP-url]: https://cloud.google.com/
