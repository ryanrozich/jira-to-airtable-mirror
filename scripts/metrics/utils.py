"""Utility functions for metrics processing."""

from typing import List, Optional


def format_duration(ms: float, right_align: Optional[int] = None) -> str:
    """Format milliseconds into a readable duration.
    
    Args:
        ms: Duration in milliseconds
        right_align: Optional width for right alignment
        
    Returns:
        Formatted duration string
    """
    if ms < 1000:
        result = f"{ms:.1f}ms"
    else:
        result = f"{ms/1000:.1f}s"
        
    if right_align is not None:
        return result.rjust(right_align)
    return result


def format_memory(mb: float) -> str:
    """Format memory in MB into a readable size."""
    if mb < 1024:
        return f"{mb:.1f}MB"
    return f"{mb/1024:.1f}GB"


def format_bytes(bytes_value: float) -> str:
    """Format bytes into human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f}{unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f}TB"


def calculate_percentile(values: List[float], percentile: float) -> float:
    """Calculate percentile from a list of values."""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    k = (len(sorted_values) - 1) * (percentile/100.0)
    f = int(k)
    c = int(k) + 1 if k % 1 else int(k)
    if f >= len(sorted_values):
        return sorted_values[-1]
    d0 = sorted_values[f] * (c - k)
    d1 = sorted_values[c] * (k - f) if c < len(sorted_values) else sorted_values[f] * (k - f)
    return d0 + d1
