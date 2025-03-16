#!/usr/bin/env python3
import subprocess
import sys
import os
from typing import Tuple
import boto3


def check_aws_cli() -> Tuple[bool, str, str]:
    """Check if AWS CLI is installed and configured."""
    try:
        subprocess.run(['aws', '--version'], check=True, capture_output=True)
        
        session = boto3.Session()
        credentials = session.get_credentials()
        if not credentials:
            return False, "AWS credentials not found", """
            To fix:
            1. Run 'aws configure'
            2. Enter your AWS Access Key ID and Secret Access Key
            3. Set default region (e.g., us-west-2)
            4. Set output format (e.g., json)
            """
        
        sts = session.client('sts')
        sts.get_caller_identity()
        
        return True, "AWS CLI is installed and configured", ""
    except subprocess.CalledProcessError:
        return False, "AWS CLI is not installed", """
        To fix:
        1. Install AWS CLI:
           - macOS: brew install awscli
           - Other: https://aws.amazon.com/cli/
        2. Run 'aws configure' to set up credentials
        """
    except Exception as e:
        return False, "AWS CLI error: " + str(e), """
        To fix:
        1. Ensure your AWS credentials are valid
        2. Check if your AWS account is active
        3. Verify you have necessary permissions
        """


def check_terraform() -> Tuple[bool, str, str]:
    """Check if Terraform is installed."""
    try:
        subprocess.run(['terraform', '--version'], check=True, capture_output=True)
        return True, "Terraform is installed", ""
    except FileNotFoundError:
        return False, "Terraform is not installed", """
        To fix:
        1. Install Terraform:
           - macOS: brew install terraform
           - Other: https://developer.hashicorp.com/terraform/downloads
        2. Verify installation: terraform --version
        """
    except subprocess.CalledProcessError as e:
        return False, "Terraform error: " + str(e), """
        To fix:
        1. Try reinstalling Terraform
        2. Check if Terraform binary is corrupted
        """


def check_terraform_config() -> Tuple[bool, str, str]:
    """Check if terraform.tfvars exists and contains required variables."""
    tfvars_path = os.path.join('terraform', 'aws', 'terraform.tfvars')
    try:
        with open(tfvars_path, 'r') as f:
            tfvars_content = f.read()
        
        required_vars = {
            'aws_region': 'AWS region for deployment (e.g., us-west-2)',
            'ecr_repository_name': 'Name for your ECR repository',
            'jira_server': 'Your Jira server URL',
            'jira_username': 'Your Jira username/email',
            'jira_project_key': 'Your Jira project key',
            'airtable_base_id': 'Your Airtable base ID',
            'airtable_table_name': 'Your Airtable table name',
            'jira_api_token_secret_arn': 'ARN of the secret containing your Jira API token',
            'airtable_api_key_secret_arn': 'ARN of the secret containing your Airtable API key'
        }
        
        missing_vars = []
        for var, description in required_vars.items():
            if var not in tfvars_content:
                missing_vars.append("- " + var + ": " + description)
        
        if missing_vars:
            fix_instructions = """
            To fix:
            1. Copy terraform.tfvars.example to terraform.tfvars if not done:
               cp terraform/aws/terraform.tfvars.example terraform/aws/terraform.tfvars
            
            2. Add the following missing variables to terraform.tfvars:
            """ + "\n            ".join(missing_vars) + """
            
            3. For secret ARNs:
               - Create secrets in AWS Secrets Manager
               - Copy the ARNs to terraform.tfvars
            """
            return False, "Missing required variables in terraform.tfvars", fix_instructions
        return True, "terraform.tfvars is properly configured", ""
    except FileNotFoundError:
        return False, "terraform.tfvars not found", """
        To fix:
        1. Copy the example file:
           cp terraform/aws/terraform.tfvars.example terraform/aws/terraform.tfvars
        2. Edit terraform.tfvars and fill in your configuration values
        """


def check_aws_permissions() -> Tuple[bool, str, str]:
    """Check if AWS user has required permissions."""
    try:
        session = boto3.Session()
        
        ecr = session.client('ecr')
        ecr.describe_repositories()
        
        lambda_client = session.client('lambda')
        lambda_client.list_functions()
        
        secrets = session.client('secretsmanager')
        secrets.list_secrets()
        
        events = session.client('events')
        events.list_rules()
        
        return True, "AWS user has required permissions", ""
    except Exception as e:
        service = str(e).split('.')[0] if '.' in str(e) else 'unknown'
        return False, "Missing AWS permissions: " + str(e), """
        To fix:
        1. Ensure your AWS user has these permissions:
           - Amazon ECR: Full access
           - AWS Lambda: Full access
           - AWS Secrets Manager: Read access
           - Amazon EventBridge: Full access
        
        2. Add missing permissions for """ + service + """ :
           - Ask your AWS administrator to grant necessary permissions
           - Or update your IAM policy to include required actions
        """


def run_aws_validation():
    """Run all AWS validation checks and return the results."""
    checks = [
        ("AWS CLI", check_aws_cli()),
        ("Terraform", check_terraform()),
        ("Terraform Configuration", check_terraform_config()),
        ("AWS Permissions", check_aws_permissions())
    ]
    
    all_passed = True
    first = True
    
    for name, (passed, message, fix) in checks:
        status = "✅" if passed else "❌"
        if first:
            print(f"\n   {status} {name}:")
            first = False
        else:
            print(f"\n   {status} {name}:")
        print(f"      {message}")
        
        if not passed and fix:
            print(f"      {fix}")
    
    print()  # Add blank line at the end
    return all_passed


if __name__ == "__main__":
    sys.exit(0 if run_aws_validation() else 1)
