"""Format CloudWatch metrics into human-readable tables."""

import json
import statistics
import sys
from datetime import datetime
from typing import Dict, Any

from tabulate import tabulate

from .utils import format_duration, calculate_percentile


def process_metrics(raw_metrics: str) -> Dict[str, Any]:
    """Process raw metrics into summary statistics."""
    metrics = {}
    
    # Split the input into separate JSON objects
    json_objects = raw_metrics.strip().split('\n\n')
    
    for json_str in json_objects:
        try:
            data = json.loads(json_str)
            
            # Skip empty responses
            if not data.get('Datapoints'):
                continue
                
            metric_name = data['Label']
            namespace = data.get('Namespace', 'AWS/Lambda')  # Default to AWS/Lambda namespace
            
            if namespace == 'AWS/Lambda':
                if metric_name == 'Invocations':
                    metrics['invocations'] = {
                        'total': sum(point['Sum'] for point in data['Datapoints']),
                        'type': 'count'
                    }
                elif metric_name == 'Errors':
                    metrics['errors'] = {
                        'total': sum(point['Sum'] for point in data['Datapoints']),
                        'type': 'count'
                    }
                elif metric_name == 'Duration':
                    duration_points = [point['Average'] for point in data['Datapoints']]
                    if duration_points:
                        metrics['duration'] = {
                            'avg': statistics.mean(duration_points),
                            'max': max(point['Maximum'] for point in data['Datapoints']),
                            'min': min(point['Minimum'] for point in data['Datapoints']),
                            'median': statistics.median(duration_points),
                            'p90': calculate_percentile(duration_points, 90),
                            'type': 'duration'
                        }
                elif metric_name == 'Throttles':
                    metrics['throttles'] = {
                        'total': sum(point['Sum'] for point in data['Datapoints']),
                        'type': 'count'
                    }
                elif metric_name == 'ConcurrentExecutions':
                    concurrent_points = [point['Maximum'] for point in data['Datapoints']]
                    if concurrent_points:
                        metrics['concurrency'] = {
                            'max': max(concurrent_points),
                            'avg': statistics.mean([point['Average'] for point in data['Datapoints']]),
                            'type': 'count'
                        }
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}", file=sys.stderr)
            continue
        except KeyError as e:
            print(f"Missing key in data: {e}", file=sys.stderr)
            continue
            
    return metrics


def format_table(metrics: Dict[str, Dict[str, Any]], time_range: str) -> str:
    """Format metrics into pretty tables grouped by category.
    
    Args:
        metrics: Dictionary of processed metrics
        time_range: String describing the time range of the metrics
        
    Returns:
        Formatted tables as string
    """
    # Group 1: Invocations and Errors
    invocation_rows = []
    if 'invocations' in metrics:
        invocation_rows.append(['Invocations', f"{metrics['invocations']['total']:>8.0f}"])
    if 'errors' in metrics:
        invocation_rows.append(['Errors', f"{metrics['errors']['total']:>8.0f}"])
    if 'invocations' in metrics and 'errors' in metrics:
        error_rate = (metrics['errors']['total'] / metrics['invocations']['total'] * 100) \
            if metrics['invocations']['total'] > 0 else 0
        invocation_rows.append(['Error Rate', f"{error_rate:>8.1f}%"])
    if 'throttles' in metrics:
        invocation_rows.append(['Throttles', f"{metrics['throttles']['total']:>8.0f}"])
        
    # Group 2: Duration Statistics
    duration_rows = []
    if 'duration' in metrics:
        duration_rows.extend([
            ['Average', format_duration(metrics['duration']['avg'], right_align=8)],
            ['Maximum', format_duration(metrics['duration']['max'], right_align=8)],
            ['Minimum', format_duration(metrics['duration']['min'], right_align=8)],
            ['Median', format_duration(metrics['duration']['median'], right_align=8)],
            ['90th Percentile', format_duration(metrics['duration']['p90'], right_align=8)]
        ])
        
    # Group 3: Concurrency
    concurrency_rows = []
    if 'concurrency' in metrics:
        concurrency_rows.extend([
            ['Maximum', f"{metrics['concurrency']['max']:>8.0f}"],
            ['Average', f"{metrics['concurrency']['avg']:>8.1f}"]
        ])
    
    # Build the output with section headers
    output = []
    
    if invocation_rows:
        output.extend([
            f"\nInvocations ({time_range}):",
            tabulate(invocation_rows, headers=['Metric', 'Value'], 
                    tablefmt='simple', colalign=('left', 'right'))
        ])
    
    if duration_rows:
        output.extend([
            f"\nDuration ({time_range}):",
            tabulate(duration_rows, headers=['Metric', 'Value'],
                    tablefmt='simple', colalign=('left', 'right'))
        ])
    
    if concurrency_rows:
        output.extend([
            f"\nConcurrency ({time_range}):",
            tabulate(concurrency_rows, headers=['Metric', 'Value'],
                    tablefmt='simple', colalign=('left', 'right'))
        ])
    
    return '\n'.join(output)
