"""CloudWatch metrics collector for Lambda functions."""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any

import boto3


class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that can handle datetime objects."""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class MetricsCollector:
    """Collects metrics from CloudWatch for Lambda functions."""

    def __init__(self, function_name: str, region: Optional[str] = None):
        """Initialize metrics collector.
        
        Args:
            function_name: Name of the Lambda function
            region: AWS region (defaults to environment variable or boto3 default)
        """
        self.function_name = function_name
        self.region = region or os.getenv('AWS_REGION', 'us-west-2')
        self.cloudwatch = boto3.client('cloudwatch', region_name=self.region)

    def get_metrics(self, start_time: datetime, end_time: datetime) -> Dict[str, List[Dict]]:
        """Get metrics for the Lambda function.
        
        Args:
            start_time: Start time for metrics query
            end_time: End time for metrics query
            
        Returns:
            Dictionary containing metrics data for different metric types
        """
        metrics = {}
        period = 60  # 1-minute periods

        # Define metrics to collect
        metric_names = [
            'Invocations',
            'Errors',
            'Duration',
            'Throttles',
            'ConcurrentExecutions'
        ]

        # Collect each metric
        for metric_name in metric_names:
            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName=metric_name,
                Dimensions=[{'Name': 'FunctionName', 'Value': self.function_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=period,
                Statistics=['Average', 'Maximum', 'Minimum', 'Sum']
            )
            
            # Add namespace and metric name to response for processing
            response['Namespace'] = 'AWS/Lambda'
            response['Label'] = metric_name
            metrics[metric_name] = response

        return metrics

    def get_metrics_json(self, start_time: datetime, end_time: datetime) -> str:
        """Get metrics in JSON format.
        
        Args:
            start_time: Start time for metrics query
            end_time: End time for metrics query
            
        Returns:
            JSON string containing metrics data
        """
        metrics = self.get_metrics(start_time, end_time)
        return '\n\n'.join(json.dumps(metric_data, cls=DateTimeEncoder) for metric_data in metrics.values())
