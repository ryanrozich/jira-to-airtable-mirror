# Jira to Airtable Mirror

## Overview
This tool maintains a live mirror of your Jira issues in Airtable, providing a flexible and configurable way to keep your Airtable base in sync with Jira. Key features include:
- Continuous one-way synchronization from Jira to Airtable
- Smart upserting of records based on Jira issue key
- Support for parent-child issue relationships
- Configurable field mappings
- Docker support for easy deployment
- Scheduled updates with configurable intervals

## Prerequisites
- Python 3.8+ (if running locally)
- Docker (if running containerized)
- Jira Cloud account with API access
- Airtable account with API access

## Quick Start with Docker
1. Clone the repository
2. Copy `.env.example` to `.env` and configure your environment variables
3. Run with Docker:
   ```bash
   # Build the image
   docker build -t jira-airtable-mirror .
   
   # Run once
   docker run --env-file .env jira-airtable-mirror --no-schedule
   
   # Or run scheduled
   docker run --env-file .env jira-airtable-mirror --schedule
   ```

## Local Installation
1. Clone the repository
2. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and configure your environment variables

## Configuration

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Configure your environment variables:
   ```env
   JIRA_SERVER=https://your-domain.atlassian.net
   JIRA_USERNAME=your_email@example.com
   JIRA_API_TOKEN=your_jira_api_token
   JIRA_PROJECT_KEY=PROJECT
   JIRA_JQL_FILTER=project = PROJECT

   AIRTABLE_API_KEY=your_airtable_pat
   AIRTABLE_BASE_ID=your_base_id
   AIRTABLE_TABLE_NAME=Your Table Name  # The actual table name, not ID

   SYNC_INTERVAL_MINUTES=5

   # Field Mappings (JSON string)
   # Map Jira fields to Airtable column IDs (not names)
   # Get column IDs from: https://airtable.com/developers/web/api/get-base-schema
   JIRA_TO_AIRTABLE_FIELD_MAP={
     "key": "fldXXXXXXXXXXXXXX",        # Issue Key
     "summary": "fldYYYYYYYYYYYYYY",     # Summary
     "description": "fldZZZZZZZZZZZZZZ"  # Description
   }
   ```

## Validation Scripts

Before running the sync, validate your configuration:

1. **Test Connections**:
   ```bash
   # Test Jira connection
   python scripts/test_jira_connection.py

   # Test Airtable connection
   python scripts/test_airtable_connection.py
   ```

2. **Validate Schema**:
   ```bash
   # Verify field mappings match Airtable schema
   python scripts/validate_schema.py
   ```

3. **Test Sync**:
   ```bash
   # Dry run of sync process
   python scripts/test_sync.py
   ```

These scripts will help you:
- Verify API credentials
- Confirm field mapping correctness
- Test the sync process without writing data
- Debug any configuration issues

## Local Development

### Running with Docker

```bash
# Run production service (default)
docker compose up -d

# Or run once with example configuration for testing
docker compose --profile dev run --rm mirror-dev
```

### Portainer Deployment

Deploy using Portainer's web interface:

1. **Create Stack**:
   - Go to Stacks → Add stack
   - Choose "Repository"
   - Enter repository URL: `https://github.com/ryanrozich/jira-to-airtable-mirror`
   - Set compose path to `docker-compose.yml`

2. **Add Environment Variables**:
   - Click "Load variables from env file" and select your `.env` file
   - Or manually add these required variables:
   ```env
   JIRA_SERVER=https://your-domain.atlassian.net
   JIRA_USERNAME=your_email@example.com
   JIRA_API_TOKEN=your_jira_api_token
   JIRA_PROJECT_KEY=PROJECT
   JIRA_JQL_FILTER=project = PROJECT
   SYNC_INTERVAL_MINUTES=5
   AIRTABLE_API_KEY=your_airtable_pat
   AIRTABLE_BASE_ID=your_base_id
   AIRTABLE_TABLE_NAME=your_table_name
   JIRA_TO_AIRTABLE_FIELD_MAP={"key":"fldXXX",...}
   TZ=UTC
   ```

3. **Deploy**:
   - Click "Deploy the stack"
   - The mirror service will start automatically
   - Logs can be viewed in the container view

Note: When using Portainer, the environment variables will be automatically saved to a `stack.env` file, which is referenced in the docker-compose.yml configuration.

## Cloud Deployment

This project includes Terraform configurations for deploying to AWS Lambda or Google Cloud Functions. Both options provide:
- Serverless execution
- Automatic scaling
- Built-in scheduling
- Secure secrets management
- Cost-effective pricing (likely within free tier)

For detailed deployment instructions, see [terraform/README.md](terraform/README.md)

## Logging
Logs are written to both console and `sync.log` file. When running with Docker, logs are preserved in a volume at `/app/logs`.

## Troubleshooting

### Common Issues

1. **Field Mapping Errors**
   - Verify field IDs in Airtable by inspecting the field properties
   - Ensure all mapped fields exist in both Jira and Airtable
   - Check field types are compatible

2. **Authentication Issues**
   - Verify Jira API token has required permissions
   - Ensure Airtable PAT has correct scopes and base access
   - Check for typos in credentials

3. **Parent-Child Relationship Issues**
   - Ensure parent field in Airtable is "Link to another record" type
   - Verify parent issues exist in Airtable before syncing child issues
   - Check JQL ordering to process parent issues first

### Debug Mode
Enable debug logging by setting the logging level to DEBUG in `sync.py`:

```python
logging.basicConfig(
    level=logging.DEBUG,
    ...
)
```

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
