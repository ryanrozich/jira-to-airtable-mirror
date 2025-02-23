#!/usr/bin/env python3
"""
Main entry point for running all validation scripts.
This script eliminates the RuntimeWarnings by importing and running
validation functions directly instead of using python -m.
"""

import sys
import logging
from scripts.validation import config, docker, aws, schema
from scripts.tests import jira_connection, airtable_connection, sync

# Configure logging - only show INFO and above from our scripts, WARNING and above from others
logging.basicConfig(
    level=logging.WARNING,
    format='%(message)s'
)
logger = logging.getLogger('scripts')
logger.setLevel(logging.INFO)

def run_all_validations():
    """Run all validation scripts in sequence."""
    all_passed = True
    
    # Environment Configuration
    print("\n1️⃣  Validating Environment Configuration")
    if not config.main():
        all_passed = False
    
    # Docker Prerequisites
    print("\n2️⃣  Validating Docker Prerequisites")
    if not docker.main():
        all_passed = False
    
    # AWS Prerequisites
    print("\n3️⃣  Validating AWS Prerequisites")
    if not aws.main():
        all_passed = False
    
    # Connectivity and Schema
    print("\n4️⃣  Validating Connectivity and Schema")
    
    # Jira Connection
    print("\n   Testing Jira connection...")
    if not jira_connection.main():
        print("   ❌ Jira connection failed")
        all_passed = False
    else:
        print("   ✅ Jira connection successful")
    
    # Airtable Connection
    print("\n   Testing Airtable connection...")
    if not airtable_connection.main():
        print("   ❌ Airtable connection failed")
        all_passed = False
    else:
        print("   ✅ Airtable connection successful")
    
    # Schema Validation
    print("\n   Validating Airtable schema...")
    if not schema.main():
        print("   ❌ Airtable schema validation failed")
        all_passed = False
    else:
        print("   ✅ Airtable schema validation successful")
    
    # Sync Test
    print("\n   Testing sync functionality...")
    if not sync.main():
        print("   ❌ Sync functionality test failed")
        all_passed = False
    else:
        print("   ✅ Sync functionality test successful")
    
    # Final Status
    if all_passed:
        print("\n✨ All validation tests passed successfully!")
    else:
        print("\n❌ Some validation tests failed. Please check the logs above for details.")
    
    return all_passed

if __name__ == '__main__':
    sys.exit(0 if run_all_validations() else 1)
