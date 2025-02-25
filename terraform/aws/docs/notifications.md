# AWS Lambda Notifications

This document describes the notification system for the Jira to Airtable Mirror Lambda function.

## SNS Topics

The following SNS topics are configured for the Lambda function:

### Error Notifications
- **Topic Name**: `${app_name}-errors`
- **Purpose**: Notifies about Lambda function errors and failures
- **Triggered by**:
  - Function execution errors
  - Timeouts
  - Memory errors
  - Permission issues
  - Integration failures (Jira/Airtable API errors)

### Sync Status Notifications
- **Topic Name**: `${app_name}-sync-status`
- **Purpose**: Provides updates about sync operations
- **Triggered by**:
  - Sync completion
  - Number of records synced
  - Sync warnings
  - Rate limiting events

## Subscribing to Notifications

You can subscribe to these notifications through various channels:

### Email Subscription
1. Open the [SNS Console](https://console.aws.amazon.com/sns/)
2. Select the desired topic
3. Click "Create subscription"
4. Protocol: Choose "Email"
5. Enter your email address
6. Confirm subscription via the email you receive

### SMS Subscription
1. Open the [SNS Console](https://console.aws.amazon.com/sns/)
2. Select the desired topic
3. Click "Create subscription"
4. Protocol: Choose "SMS"
5. Enter your phone number
6. You'll start receiving SMS notifications

### Slack Integration
To receive notifications in Slack:

1. Create a Slack webhook:
   - Go to Slack Apps
   - Create or select an app
   - Enable webhooks
   - Copy the webhook URL

2. Create an AWS Lambda function:
   - Use the provided `slack-notifier` template
   - Configure the webhook URL as an environment variable

3. Subscribe the Lambda function to the SNS topic:
   - Protocol: AWS Lambda
   - Select your Slack notifier function

### AWS Chatbot Integration
For notifications in AWS Chatbot:

1. Configure AWS Chatbot:
   - Open AWS Chatbot console
   - Set up chat client (Slack/Chime)
   - Create a configuration

2. Subscribe to SNS topics:
   - Select your chat channel
   - Add the SNS topics
   - Configure notification preferences

## Message Format

### Error Notifications
```json
{
  "function": "jira-to-airtable-mirror",
  "error_type": "ExecutionError",
  "error_message": "Detailed error message",
  "timestamp": "2025-02-24T12:00:00Z",
  "request_id": "abc123",
  "additional_context": {
    "memory_used": "128MB",
    "duration": "10.5s"
  }
}
```

### Sync Status Notifications
```json
{
  "function": "jira-to-airtable-mirror",
  "status": "completed",
  "records_synced": 50,
  "warnings": [],
  "duration": "45.2s",
  "timestamp": "2025-02-24T12:00:00Z"
}
```

## Notification Preferences

You can customize notification preferences:

1. **Frequency**:
   - Immediate: Get notifications as events occur
   - Digest: Receive a summary (hourly/daily)

2. **Severity Levels**:
   - Critical: System-down situations
   - Error: Function failures
   - Warning: Performance issues
   - Info: Sync status updates

3. **Delivery Hours**:
   - 24/7 delivery
   - Business hours only
   - Custom schedule

Configure these preferences in the SNS subscription settings or through AWS Chatbot configuration.
