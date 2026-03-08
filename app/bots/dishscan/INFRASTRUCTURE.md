#### Redeploying lambda function with new code
```bash
cd app/bots/dishscan/infra
terraform apply -replace=aws_lambda_function.worker
```

#### LOGS!!!
```bash
STREAM=$(aws logs describe-log-streams \
 --log-group-name "/ecs/dishscan-bot" \
 --region us-east-2 \
 --order-by LastEventTime \
 --descending \
 --limit 1 \
 --query "logStreams[0].logStreamName" \
 --output text)
 
aws logs get-log-events \
 --log-group-name "/ecs/dishscan-bot" \
  --log-stream-name "$STREAM" \
  --region us-east-2 \
  --limit 80 \
  --query "events[].message" \
  --output text
```

#### Build docker image and push to ECR
```bash
terraform apply -auto-approve

docker build \
  --platform=linux/amd64 \
  -f human_scanner_bot.dockerfile \
  -t dishscan-bot:dishscan \
  .
ECR_URL=$(cd infra && terraform output -raw ecr_repo_url)
docker tag dishscan-bot:dishscan "${ECR_URL}:dishscan"
docker push "${ECR_URL}:dishscan"
```

#### Re-login (just in case)
```bash
DISHSCAN_AWS_REGION=us-east-2
ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)

aws ecr get-login-password --region $DISHSCAN_AWS_REGION \
  | docker login --username AWS --password-stdin \
  ${ACCOUNT_ID}.dkr.ecr.${DISHSCAN_AWS_REGION}.amazonaws.com
```

#### Local running for testing Docker with AWS credentials
```bash
aws configure --profile dishscan
aws sts get-caller-identity --profile dishscan
docker run --rm -it \
  --env-file .env \
  -e AWS_PROFILE=dishscan \
  -v ~/.aws:/root/.aws:ro \
  dishscan-bot:dishscan \
  python3 app/bots/dishscan/main.py
```

#### Get task role ARN for fargate role permissions
```bash
aws ecs describe-services \
  --cluster dishscan-cluster \
  --services dishscan-bot \
  --region us-east-2 \
  --query "services[0].taskDefinition" \
  --output text
  
aws ecs describe-task-definition \
  --task-definition dishscan-bot:4 \
  --region us-east-2 \
  --query "taskDefinition.taskRoleArn" \
  --output text
```

#### Scale down to 0 tasks to stop the bot
```bash
aws ecs update-service \
  --cluster dishscan-cluster \
  --service dishscan-bot \
  --desired-count 0 \
  --region us-east-2
```

#### Run the bot locally with AWS credentials
```ini
[profile dishscan-fargate-role]
role_arn = arn:aws:iam::477975426794:role/dishscan-bot-role
source_profile = dishscan
region = us-east-2
```
```bash
#PYTHONPATH=. AWS_PROFILE=dishscan-fargate-role python3 app/bots/dishscan/main.py
PYTHONPATH=. AWS_PROFILE=dishscan-dev-role python3 app/bots/dishscan/main.py
```
