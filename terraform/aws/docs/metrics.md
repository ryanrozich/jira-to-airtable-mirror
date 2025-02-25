# AWS Lambda Metrics Monitoring

This document describes the metrics monitoring capabilities of the Jira to Airtable Mirror Lambda function.

## Available Metrics

The following metrics are available through CloudWatch and Lambda Insights:

### Core Lambda Metrics
- **Invocations**: Total number of function invocations
- **Errors**: Number of failed executions
- **Duration**: Function execution time
  - Minimum, Average, Maximum
  - p80 and p90 percentiles
- **Throttles**: Number of throttled invocations
- **ConcurrentExecutions**: Number of functions running simultaneously
  - Maximum and Average values

### Memory Metrics (via Lambda Insights)
- **Memory Usage**:
  - Minimum, Average, Maximum usage
  - p80 and p90 percentiles
  - Memory allocation
  - Utilization percentage
  - Available headroom

### Network Metrics (via Lambda Insights)
- **Transmitted Data**:
  - Total bytes sent
  - Average bytes per invocation
  - Maximum bytes in a single invocation
- **Received Data**:
  - Total bytes received
  - Average bytes per invocation
  - Maximum bytes in a single invocation

## Viewing Metrics

### Using Just Commands

The project provides convenient commands to view metrics:

```bash
# View last hour's metrics
just lambda-metrics 1h

# View last 24 hours metrics
just lambda-metrics 24h

# View last 7 days metrics
just lambda-metrics 7d
```

The metrics output is organized into sections:
1. 🔢 **Counts**: Invocations, Errors, Error Rate, and Throttles
2. ⏱️ **Duration Statistics**: Min, Avg, Max, and percentiles
3. 🔄 **Concurrency Statistics**: Max and Average concurrent executions
4. 🌐 **Network Statistics**: Transmitted and Received data
5. 💾 **Memory Statistics**: Usage, allocation, utilization, and headroom

### Using CloudWatch Console

You can also view these metrics directly in the AWS CloudWatch console:

1. Open the [CloudWatch Console](https://console.aws.amazon.com/cloudwatch/)
2. Navigate to "Metrics" → "Lambda"
3. Find your function name
4. Select the desired metrics to view

For Lambda Insights metrics:
1. Navigate to "Insights" → "Lambda Insights"
2. Select your function name
3. View the detailed performance metrics dashboard

## Metric Retention

- CloudWatch Metrics are retained for 15 months
- High-resolution metrics (period of less than 1 minute) are retained for 3 hours

## Cost Considerations

- Basic CloudWatch metrics are included in the AWS Lambda free tier
- Lambda Insights incurs additional charges:
  - Per Lambda function monitored
  - Per GB of logs ingested
  - Per metric collected

For current pricing, see [AWS Lambda Pricing](https://aws.amazon.com/lambda/pricing/) and [CloudWatch Pricing](https://aws.amazon.com/cloudwatch/pricing/).
