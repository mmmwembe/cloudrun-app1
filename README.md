# Deploy Flask App to Cloud Run using GitHub Repository

## Prerequisites
- Google Cloud account
- Cloud Run API enabled
- Cloud Build API enabled
- GitHub account

## Steps

1. Fork the repository:
```bash
git clone https://github.com/mmmwembe/cloudrun-app1.git
cd cloudrun-app1
```

2. Configure Google Cloud:
```bash
gcloud auth login
gcloud projects create [PROJECT_ID]
gcloud config set project [PROJECT_ID]
```

3. Enable billing at: https://console.cloud.google.com/billing

4. Enable required APIs:
```bash
gcloud services enable cloudbuild.googleapis.com run.googleapis.com
```

5. Setup GitHub connection:
- Go to Cloud Run console
- Click "Set up Continuous Deployment"
- Choose GitHub as source
- Authenticate and select your forked repository
- Configure build settings:
  - Region: [your-region]
  - Branch: main
  - Build Type: Dockerfile

6. Deploy:
- Click "Create"
- Set environment variable LONG_STRING in the Cloud Run console

## Monitoring
- View logs: Cloud Run > Service > Logs
- Monitor builds: Cloud Build > History
- Check deployment status: Cloud Run > Revisions

## Local Testing
```bash
docker build -t flask-app .
docker run -p 8080:8080 -e PORT=8080 -e LONG_STRING=test flask-app
```