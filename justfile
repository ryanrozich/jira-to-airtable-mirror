set dotenv-load

# Default variables
default_region := "us-west-2"
app_name := "jira-to-airtable-mirror"
aws_cli_opts := "--no-cli-pager"

# Build Docker image for local development
docker-build:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🔨 Building Docker image for local development..."
    docker build --target base -t {{app_name}}:local .

# Run Docker container locally
docker-run:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🚀 Running {{app_name}} in Docker..."
    
    if [ ! -f ".env" ]; then
        echo "❌ Error: .env file not found"
        echo "Please copy .env.example to .env and configure it"
        exit 1
    fi
    
    echo "📝 Using environment file: .env"
    docker run -d \
        --name {{app_name}} \
        --env-file .env \
        {{app_name}}:local

# View Docker container logs
docker-logs:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "📝 Following logs for {{app_name}}..."
    docker logs -f {{app_name}}

# Stop Docker container
docker-stop:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🛑 Stopping {{app_name}}..."
    docker stop {{app_name}} || true
    docker rm {{app_name}} || true

# Clean up Docker resources
docker-clean:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🧹 Cleaning up Docker resources..."
    docker stop {{app_name}} || true
    docker rm {{app_name}} || true
    docker rmi {{app_name}}:local {{app_name}}:lambda || true
    echo "✅ Docker cleanup complete"

# Build for AWS Lambda
lambda-build:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🧹 Cleaning up old images..."
    docker rmi {{app_name}}:lambda 2>/dev/null || true
    echo "🔨 Building Docker image for AWS Lambda..."
    docker build \
        --platform linux/amd64 \
        --target lambda \
        -t {{app_name}}:lambda \
        .

# Deploy to AWS Lambda
lambda-deploy region=default_region: lambda-build
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🚀 Deploying {{app_name}} to region {{region}}"
    
    # Create timestamp for unique tag
    TIMESTAMP=$(date +%Y%m%d%H%M%S)
    
    # Create ECR repository if it doesnt exist
    echo "🏗️  Ensuring ECR repository exists..."
    aws {{aws_cli_opts}} ecr describe-repositories --repository-names {{app_name}} --region {{region}} 2>/dev/null || \
    aws {{aws_cli_opts}} ecr create-repository \
        --repository-name {{app_name}} \
        --image-scanning-configuration scanOnPush=true \
        --region {{region}}
    
    # Get ECR login
    echo "🔑 Logging into ECR..."
    aws {{aws_cli_opts}} ecr get-login-password --region {{region}} | \
    docker login --username AWS --password-stdin \
    $(aws {{aws_cli_opts}} sts get-caller-identity --query Account --output text).dkr.ecr.{{region}}.amazonaws.com

    # Tag and push image with timestamp
    ECR_REPO=$(aws {{aws_cli_opts}} sts get-caller-identity --query Account --output text).dkr.ecr.{{region}}.amazonaws.com/{{app_name}}
    echo "📦 Tagging and pushing image to $ECR_REPO:$TIMESTAMP..."
    docker tag {{app_name}}:lambda $ECR_REPO:$TIMESTAMP
    docker push $ECR_REPO:$TIMESTAMP
    
    # Also update latest tag
    docker tag {{app_name}}:lambda $ECR_REPO:latest
    docker push $ECR_REPO:latest

    # Apply Terraform
    echo "🏗️  Applying Terraform configuration..."
    cd terraform/aws
    terraform init
    terraform apply -auto-approve \
        -var="aws_region={{region}}" \
        -var="ecr_repository_name={{app_name}}"
        
    # Force Lambda to use new image
    echo "🔄 Updating Lambda function configuration..."
    aws {{aws_cli_opts}} lambda update-function-code \
        --function-name {{app_name}} \
        --image-uri $ECR_REPO:$TIMESTAMP \
        --region {{region}}
        
    # Wait for update to complete
    echo "⏳ Waiting for function update to complete..."
    aws {{aws_cli_opts}} lambda wait function-updated \
        --function-name {{app_name}} \
        --region {{region}}
    echo "✅ Function update completed successfully"
    
    echo "🎉 Deployment completed successfully!"

# Create and setup virtual environment
setup-venv:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🔧 Setting up Python virtual environment..."
    
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        echo "✓ Created new virtual environment"
    fi
    
    . venv/bin/activate
    pip install -r requirements.txt
    echo "✓ Installed dependencies"

# Run the sync script directly (without Docker)
run: setup-venv
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🚀 Running {{app_name}} with Python..."
    
    . venv/bin/activate
    python sync.py

# Run the sync script in scheduled mode (without Docker)
run-scheduled: setup-venv
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🚀 Running {{app_name}} in scheduled mode..."
    
    . venv/bin/activate
    python sync.py --schedule

# Run all validation scripts
validate-all: setup-venv
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🔍 Running all validation scripts..."
    
    . venv/bin/activate
    export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
    python scripts/validate_config.py
    python scripts/validate_schema.py
    python scripts/test_jira_connection.py
    python scripts/test_airtable_connection.py
    python scripts/test_sync.py
    
    echo "✅ All validation passed"

# Clean up local development resources
clean: docker-clean
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🧹 Cleaning up local development resources..."
    rm -rf venv
    rm -rf __pycache__
    rm -rf .pytest_cache
    rm -rf .coverage
    echo "✅ Local cleanup complete"

# Tail AWS Lambda logs in real-time
lambda-logs region=default_region:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "📝 Tailing logs for {{app_name}}..."
    aws {{aws_cli_opts}} logs tail \
        /aws/lambda/{{app_name}} \
        --region {{region}} \
        --follow \
        --format short

# Get recent AWS Lambda logs
lambda-logs-recent region=default_region minutes="30":
    #!/usr/bin/env bash
    set -euo pipefail
    echo "📝 Getting last {{minutes}} minutes of logs for {{app_name}}..."
    aws {{aws_cli_opts}} logs tail \
        /aws/lambda/{{app_name}} \
        --region {{region}} \
        --format short \
        --since {{minutes}}m

# Invoke AWS Lambda function manually
lambda-invoke region=default_region:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🚀 Invoking {{app_name}} Lambda function..."
    aws {{aws_cli_opts}} lambda invoke \
        --region {{region}} \
        --function-name {{app_name}} \
        --invocation-type RequestResponse \
        --payload '{}' \
        /dev/stdout

# View Lambda container image details
lambda-image:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🔍 Inspecting Lambda image configuration..."
    docker inspect {{app_name}}:lambda

# Destroy AWS infrastructure
lambda-destroy region=default_region:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "💣 Destroying AWS infrastructure in {{region}}..."
    
    cd terraform/aws
    terraform init
    terraform destroy -auto-approve \
        -var="aws_region={{region}}" \
        -var="ecr_repository_name={{app_name}}"
    
    echo "✅ AWS infrastructure destroyed"

# Destroy everything (cleans up local resources including Docker, and destroys AWS infrastructure)
destroy-all region=default_region: clean (lambda-destroy region)
