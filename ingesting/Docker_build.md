# Build and push to docker hub

```bash
docker build -f ingesting/Dockerfile -t godminhkhoa/ingesting-iee-service:1.0.1
docker push godminhkhoa/ingesting-iee-service:1.0.1
```

# Test ingesting Docker 

+ Create .env.test

```bash
docker run -d --name ingesting-svc \
  --env-file .env.test \
  -p 5001:5001 \
  -v /home/godminhkhoa/Documents/Final_Project_IEE/iac/ansible/secrets/iee-project-2025-2305f145d9ec.json:/var/secrets/key.json:ro \
  godminhkhoa/ingesting-iee-service:1.0.0

docker logs -f ingesting-svc
```

+ The ingesting service will be here http://0.0.0.0:5001/ingesting/docs