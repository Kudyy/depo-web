#!/bin/bash

# AWS Deployment Script for Depo Web Application

set -e

echo "🚀 Starting AWS deployment..."

# Variables
AWS_REGION="us-east-1"
ECR_REPOSITORY="depo-web"
CLUSTER_NAME="depo-web-cluster"
SERVICE_NAME="depo-web-service"
TASK_DEFINITION="depo-web-task"

# Get AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}"

echo "📦 Building Docker image..."
docker build -t ${ECR_REPOSITORY} .

echo "🏷️ Tagging image..."
docker tag ${ECR_REPOSITORY}:latest ${ECR_URI}:latest

echo "🔐 Logging into ECR..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_URI}

echo "⬆️ Pushing to ECR..."
docker push ${ECR_URI}:latest

echo "📋 Updating task definition..."
# Update task definition with new image URI
sed "s/YOUR_ACCOUNT_ID/${AWS_ACCOUNT_ID}/g" task-definition.json > task-definition-updated.json

echo "📝 Registering new task definition..."
aws ecs register-task-definition --cli-input-json file://task-definition-updated.json

echo "🔄 Updating service..."
aws ecs update-service \
    --cluster ${CLUSTER_NAME} \
    --service ${SERVICE_NAME} \
    --task-definition ${TASK_DEFINITION}

echo "✅ Deployment completed!"
echo "🌐 Your application will be available at the load balancer URL"