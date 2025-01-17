#!/usr/bin/env python3
import os
import sys
import json
import click
from sync import load_config, JiraAirtableSync

@click.command()
@click.option('--env-file', default='.env', help='Path to environment file')
def validate_config(env_file):
    """Validate configuration and test connections to Jira and Airtable."""
    try:
        # Load configuration
        if os.path.exists(env_file):
            click.echo(f"✓ Loading configuration from {env_file}")
        else:
            click.echo(f"⚠️  {env_file} not found, using environment variables")
        
        config = load_config()
        click.echo("✓ Configuration loaded successfully")
        
        # Initialize sync client (this will validate Airtable schema)
        click.echo("\nTesting connections...")
        sync = JiraAirtableSync(config)
        click.echo("✓ Successfully connected to Airtable and validated schema")
        
        # Test Jira connection by fetching a single issue
        jql = f"project = {config['jira_project_key']} ORDER BY created DESC"
        issues = sync.jira_client.search_issues(jql, maxResults=1)
        if issues:
            click.echo(f"✓ Successfully connected to Jira and found {len(issues)} issue")
            
            # Test field mapping with the sample issue
            click.echo("\nTesting field mapping with sample issue...")
            record = sync._transform_jira_issue(issues[0])
            click.echo(f"✓ Successfully mapped {len(record)} fields:")
            for jira_field, airtable_field in config['field_map'].items():
                value = record.get(airtable_field, '[NOT MAPPED]')
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                click.echo(f"  - {jira_field}: {value}")
        else:
            click.echo("⚠️  Connected to Jira but found no issues matching the filter")
        
        click.echo("\n✅ Configuration is valid and all connections are working!")
        return 0
        
    except Exception as e:
        click.echo(f"\n❌ Validation failed: {str(e)}", err=True)
        return 1

if __name__ == '__main__':
    sys.exit(validate_config())
