#!/usr/bin/env python3
"""Script to collect and display Lambda function metrics."""

import argparse
from datetime import datetime, timedelta, timezone

from metrics import MetricsCollector, process_metrics, format_table


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Get Lambda function metrics')
    parser.add_argument('--function-name', '-f', required=True,
                       help='Name of the Lambda function')
    parser.add_argument('--region', '-r',
                       help='AWS region (defaults to AWS_REGION env var)')
    parser.add_argument('--hours', '-H', type=int, default=1,
                       help='Number of hours to look back (default: 1)')
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Calculate time range
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=args.hours)
    time_range = f"Last {args.hours} hour{'s' if args.hours != 1 else ''}"
    
    # Collect metrics
    collector = MetricsCollector(args.function_name, args.region)
    metrics_json = collector.get_metrics_json(start_time, end_time)
    
    # Process and format metrics
    metrics = process_metrics(metrics_json)
    table = format_table(metrics, time_range)
    
    # Print results
    print(table)


if __name__ == '__main__':
    main()
