#!/bin/bash

# Exit on error
set -e

# Configuration
PROJECT_ID=$(gcloud config get-value project)
SERVICE_NAME="document-qa"
REGION="us-central1"
BUCKET_NAME="document-qa-storage-$PROJECT_ID"

echo "Deploying Document Q&A application to Google Cloud Run..."

# Create GCS bucket if it doesn't exist
if ! gsutil ls -b gs://$BUCKET_NAME > /dev/null 2>&1; then
    echo "Creating GCS bucket: $BUCKET_NAME"
    gsutil mb -l $REGION gs://$BUCKET_NAME
else
    echo "GCS bucket already exists: $BUCKET_NAME"
fi

# Build the container image
echo "Building container image..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME

# Deploy to Cloud Run
echo "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 1 \
  --set-env-vars="GCS_BUCKET_NAME=$BUCKET_NAME,GOOGLE_API_KEY=$GOOGLE_API_KEY"

echo "Deployment complete!"
echo "Your application is now available at: $(gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)')"
