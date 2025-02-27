# Metrics Package

This package provides functionality for collecting and formatting AWS Lambda metrics. It's designed to be both a standalone CLI tool and a reusable Python package.

## Components

- `collector.py`: Fetches metrics from AWS CloudWatch
- `formatter.py`: Formats metrics into human-readable tables
- `utils.py`: Shared utility functions for formatting values
- `__init__.py`: Package exports and version information

## Usage

### As a CLI Tool

Use the `get_metrics.py` script in the parent directory:

```bash
# Get metrics for the last hour
./get_metrics.py -f your-lambda-function

# Get metrics for the last 24 hours
./get_metrics.py -f your-lambda-function -H 24

# Specify a different AWS region
./get_metrics.py -f your-lambda-function -r us-east-1
```

### As a Python Package

```python
from datetime import datetime, timedelta, timezone
from metrics import MetricsCollector, process_metrics, format_table

# Initialize collector
collector = MetricsCollector('your-lambda-function')

# Define time range
end_time = datetime.now(timezone.utc)
start_time = end_time - timedelta(hours=1)

# Get and format metrics
metrics_json = collector.get_metrics_json(start_time, end_time)
metrics = process_metrics(metrics_json)
table = format_table(metrics, "Last hour")
print(table)
```

## Output Format

The metrics are presented in three grouped tables:

1. **Invocations**
   - Total invocations
   - Error count and rate
   - Throttle count

2. **Duration**
   - Average
   - Maximum
   - Minimum
   - Median
   - 90th percentile

3. **Concurrency**
   - Maximum concurrent executions
   - Average concurrent executions

Example output:
```
Invocations (Last 1 hour):
Metric         Value
-----------  -------
Invocations        6
Errors             0
Error Rate      0.0%
Throttles          0

Duration (Last 1 hour):
Metric             Value
---------------  -------
Average             9.4s
Maximum            11.1s
Minimum             8.4s
Median              8.9s
90th Percentile    10.9s

Concurrency (Last 1 hour):
Metric      Value
--------  -------
Maximum         1
Average         1
```
