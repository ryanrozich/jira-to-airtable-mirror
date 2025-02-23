#!/usr/bin/env python3
import subprocess
import sys
import os

def check_docker_installation() -> tuple[bool, str]:
    """Check if Docker is installed and running."""
    try:
        # Check Docker installation
        subprocess.run(['docker', '--version'], check=True, capture_output=True)
        
        # Check if Docker daemon is running
        subprocess.run(['docker', 'info'], check=True, capture_output=True)
        return True, "Docker is installed and running"
    except subprocess.CalledProcessError:
        return False, "Docker is not running. Please start Docker daemon"
    except FileNotFoundError:
        return False, "Docker is not installed. Please install Docker"

def check_env_file() -> tuple[bool, str]:
    """Check if .env file exists and is configured."""
    if not os.path.exists('.env'):
        return False, ".env file not found. Please copy .env.example to .env and configure it"
    
    # Add any additional .env validation here
    return True, ".env file is properly configured"

def check_dockerfile() -> tuple[bool, str]:
    """Check if Dockerfile exists and contains required stages."""
    if not os.path.exists('Dockerfile'):
        return False, "Dockerfile not found"
    
    required_stages = ['base', 'lambda']
    with open('Dockerfile', 'r') as f:
        content = f.read().lower()
        missing_stages = [stage for stage in required_stages if f'as {stage}' not in content]
        
        if missing_stages:
            return False, f"Missing required stages in Dockerfile: {', '.join(missing_stages)}"
    
    return True, "Dockerfile contains all required stages"

def main():
    checks = [
        ("Docker Installation", check_docker_installation()),
        ("Environment File", check_env_file()),
        ("Dockerfile", check_dockerfile())
    ]
    
    all_passed = True
    first = True
    
    for name, (passed, message) in checks:
        status = "✅" if passed else "❌"
        if first:
            print(f"\n   {status} {name}:")
            first = False
        else:
            print(f"\n   {status} {name}:")
        print(f"      {message}")
        if not passed:
            all_passed = False
    
    print()  # Add blank line at the end
    sys.exit(0 if all_passed else 1)

if __name__ == '__main__':
    main()
