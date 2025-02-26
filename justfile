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
    # Export all variables from .env file
    set -a
    source .env
    set +a
    
    # Run the container with environment variables from the current shell
    docker run -d \
        --name {{app_name}} \
        --env-file <(env | grep -E '^(JIRA_|AIRTABLE_|LOG_|SYNC_|BATCH_)') \
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
    set -a
    source .env
    set +a
    python sync.py

# Run the sync script in scheduled mode (without Docker)
run-scheduled: setup-venv
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🚀 Running {{app_name}} in scheduled mode..."
    
    . venv/bin/activate
    python sync.py --schedule

# Validate Docker prerequisites
validate-docker: setup-venv
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🔍 Validating Docker prerequisites..."
    . venv/bin/activate
    export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
    python -c "from scripts.validation import docker; docker.main()"

# Validate AWS prerequisites
validate-aws: setup-venv
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🔍 Validating AWS prerequisites..."
    . venv/bin/activate
    export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
    python -c "from scripts.validation import aws; aws.main()"

# Run all validation scripts
validate-all: setup-venv
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🔍 Running all validation scripts..."
    
    . venv/bin/activate
    export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
    python scripts/run_validation.py

# Validate Environment Configuration
validate-config: setup-venv
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🔍 Validating Environment Configuration..."
    
    . venv/bin/activate
    export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
    python -c "from scripts.validation import config; config.main()"

# Validate Connectivity and Schema
validate-connectivity: setup-venv
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🔍 Validating Connectivity and Schema..."
    
    . venv/bin/activate
    export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
    python -c "from scripts.validation import connectivity; connectivity.main()"

# Run CodeQL analysis locally (requires CodeQL CLI: https://github.com/github/codeql-cli-binaries)
security-scan:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🔒 Running CodeQL security scan..."
    if ! command -v codeql &> /dev/null; then
        echo "❌ CodeQL CLI not found. Please install it first:"
        echo "https://github.com/github/codeql-cli-binaries"
        exit 1
    fi
    
    # Create CodeQL database
    codeql database create .codeql-db --language=python --source-root=.
    
    # Run analysis
    codeql database analyze .codeql-db \
        --format=sarif-latest \
        --output=codeql-results.sarif \
        security-and-quality.qls
    
    echo "✅ Analysis complete. Results saved to codeql-results.sarif"

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

# Internal function to get logs with time filtering
_lambda-logs-filtered region time ascending="false":
    #!/usr/bin/env bash
    set -euo pipefail
    
    # Convert time to date adjustment format
    case "{{time}}" in
        *h)
            TIME_ADJ="-$(echo {{time}} | sed 's/h//g')H"
            ;;
        *m)
            TIME_ADJ="-$(echo {{time}} | sed 's/m//g')M"
            ;;
        *)
            echo "❌ Invalid time format. Use: 30m, 1h, 2h, etc."
            exit 1
            ;;
    esac
    
    # Convert time to milliseconds for the query
    START_TIME=$(date -v"$TIME_ADJ" +%s)000
    
    # Run CloudWatch Logs Insights query
    QUERY="fields @timestamp, @message"
    if [ "{{ascending}}" = "true" ]; then
        QUERY="${QUERY} | sort @timestamp asc"
    else
        QUERY="${QUERY} | sort @timestamp desc"
    fi
    
    echo "🔍 Query: $QUERY"  # Debug output
    
    # Start the query and get query ID
    QUERY_ID=$(aws {{aws_cli_opts}} logs start-query \
        --log-group-name /aws/lambda/{{app_name}} \
        --start-time $START_TIME \
        --end-time $(date +%s)000 \
        --region {{region}} \
        --query-string "$QUERY" \
        --output text \
        --query 'queryId')
    
    # Poll for results
    while true; do
        RESULTS=$(aws {{aws_cli_opts}} logs get-query-results --query-id "$QUERY_ID" --region {{region}})
        STATUS=$(echo "$RESULTS" | jq -r .status)
        if [ "$STATUS" = "Complete" ]; then
            echo "$RESULTS" | \
                jq -r ".results[] | [.[0].value, .[1].value] | @tsv" | \
                while IFS=$"\t" read -r timestamp message; do
                    printf "%s %s\n" "$timestamp" "$message"
                done
            break
        elif [ "$STATUS" = "Failed" ]; then
            echo "❌ Query failed"
            break
        fi
        sleep 1
    done

# Get recent AWS Lambda logs
lambda-logs-recent time="15m" region=default_region:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "📝 Getting logs for the last {{time}}..."
    just _lambda-logs-filtered {{region}} {{time}} true

# Tail AWS Lambda logs in real-time
lambda-logs-tail region=default_region:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "📝 Tailing logs for {{app_name}}..."
    aws {{aws_cli_opts}} logs tail \
        /aws/lambda/{{app_name}} \
        --region {{region}} \
        --follow \
        --since 1m \
        --format short

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

# Get current Lambda log level
lambda-get-log-level region=default_region:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "📝 Getting current log level..."
    aws {{aws_cli_opts}} lambda get-function-configuration \
        --function-name {{app_name}} \
        --region {{region}} \
        --query 'Environment.Variables.LOG_LEVEL' \
        --output text

# Invoke Lambda function synchronously
lambda-invoke-sync region=default_region:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🚀 Invoking Lambda function synchronously..."
    RESPONSE_FILE=$(mktemp)
    aws {{aws_cli_opts}} lambda invoke \
        --function-name {{app_name}} \
        --region {{region}} \
        --invocation-type RequestResponse \
        --log-type Tail \
        --payload '{}' \
        "$RESPONSE_FILE" \
        --query 'LogResult' \
        --output text | base64 -d
    echo "Response payload:"
    cat "$RESPONSE_FILE"
    rm "$RESPONSE_FILE"

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

# Lint Python code with flake8
lint: setup-venv
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🔍 Linting Python code..."
    source venv/bin/activate
    pip install flake8
    echo "Running basic error checks..."
    flake8 app.py sync.py scripts/ --count --select=E9,F63,F7,F82 --show-source --statistics --extend-ignore=W29
    echo "Running style checks..."
    flake8 app.py sync.py scripts/ --count --max-complexity=10 --max-line-length=127 --statistics --extend-ignore=W29

# View CloudWatch metrics for Lambda function
lambda-metrics period="1h": setup-venv
    #!/usr/bin/env bash
    set -euo pipefail
    echo "📊 Getting CloudWatch metrics for {{app_name}}..."
    
    . venv/bin/activate
    
    # Convert period to hours
    HOURS=$(echo "{{period}}" | sed 's/h$//')
    
    ./scripts/get_metrics.py \
        --function-name {{app_name}} \
        --region {{default_region}} \
        --hours ${HOURS}

# Update Lambda log level without redeploying
lambda-set-log-level level region=default_region:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "📝 Setting log level to {{level}}..."
    ENV_VARS=$(aws {{aws_cli_opts}} lambda get-function-configuration \
        --function-name {{app_name}} \
        --region {{region}} \
        --query 'Environment.Variables' \
        --output json)
    UPDATED_ENV=$(echo "$ENV_VARS" | jq '. + {"LOG_LEVEL": "{{level}}"}')
    aws {{aws_cli_opts}} lambda update-function-configuration \
        --function-name {{app_name}} \
        --region {{region}} \
        --cli-input-json "{\"FunctionName\": \"{{app_name}}\", \"Environment\": {\"Variables\": $UPDATED_ENV}}"

# Display Jira field schema
schema-jira: setup-venv
    #!/usr/bin/env bash
    set -euo pipefail
    echo "📝 Displaying Jira field schema..."
    . venv/bin/activate
    python scripts/schema/jira_schema.py

# Display Airtable schema
schema-airtable: setup-venv
    #!/usr/bin/env bash
    set -euo pipefail
    echo "📝 Displaying Airtable schema..."
    . venv/bin/activate
    python scripts/schema/airtable_schema.py

# Pause the Lambda scheduler
lambda-scheduler-pause region=default_region:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "⏸️  Pausing Lambda scheduler..."
    aws {{aws_cli_opts}} events disable-rule \
        --name "{{app_name}}-schedule" \
        --region {{region}}
    echo "✅ Scheduler paused"

# Resume the Lambda scheduler
lambda-scheduler-resume region=default_region:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "▶️  Resuming Lambda scheduler..."
    aws {{aws_cli_opts}} events enable-rule \
        --name "{{app_name}}-schedule" \
        --region {{region}}
    echo "✅ Scheduler resumed"

# Check Lambda scheduler status
lambda-scheduler-status region=default_region:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "📊 Checking Lambda scheduler status..."
    STATE=$(aws {{aws_cli_opts}} events describe-rule \
        --name "{{app_name}}-schedule" \
        --region {{region}} \
        --query 'State' \
        --output text)
    if [ "$STATE" = "ENABLED" ]; then
        echo "🟢 Scheduler is ACTIVE"
    else
        echo "⭕ Scheduler is PAUSED"
    fi
