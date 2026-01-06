#!/usr/bin/env python3
"""
Generate Helm values.yaml for many deployments

Usage:
    # From CSV file
    python3 scripts/generate-helm-values.py --csv deployments.csv

    # From kubectl (auto-discover HPAs)
    python3 scripts/generate-helm-values.py --auto-discover

    # Generate template
    python3 scripts/generate-helm-values.py --template > deployments.csv

CSV Format:
    namespace,deployment,hpa_name,startup_filter,priority
    production,api-gateway,api-gateway-hpa,2,critical
    production,auth-service,auth-service-hpa,3,critical
"""

import argparse
import csv
import sys
import yaml
from typing import List, Dict
import subprocess
import json


def generate_template():
    """Generate CSV template"""
    print("namespace,deployment,hpa_name,startup_filter,priority")
    print("production,api-gateway,api-gateway-hpa,2,critical")
    print("production,auth-service,auth-service-hpa,3,critical")
    print("production,payment-service,payment-service-hpa,5,critical")
    print("production,user-service,user-service-hpa,2,high")
    print("production,order-service,order-service-hpa,2,high")
    print("production,search-service,search-service-hpa,2,medium")
    print("production,analytics-worker,analytics-worker-hpa,1,low")


def read_csv(filename: str) -> List[Dict]:
    """Read deployments from CSV file"""
    deployments = []
    
    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            deployments.append({
                'namespace': row['namespace'],
                'name': row['deployment'],
                'hpaName': row['hpa_name'],
                'startupFilterMinutes': int(row.get('startup_filter', 2)),
                'priority': row.get('priority', 'medium')
            })
    
    return deployments


def auto_discover_hpas() -> List[Dict]:
    """Auto-discover HPAs from cluster"""
    try:
        # Get all HPAs
        result = subprocess.run(
            ['kubectl', 'get', 'hpa', '-A', '-o', 'json'],
            capture_output=True,
            text=True,
            check=True
        )
        
        hpas = json.loads(result.stdout)
        deployments = []
        
        for hpa in hpas.get('items', []):
            namespace = hpa['metadata']['namespace']
            hpa_name = hpa['metadata']['name']
            
            # Get target deployment name
            target = hpa['spec'].get('scaleTargetRef', {})
            if target.get('kind') == 'Deployment':
                deployment_name = target.get('name')
                
                # Guess priority based on namespace
                if namespace in ['production', 'prod']:
                    priority = 'high'
                elif namespace in ['staging', 'stage']:
                    priority = 'medium'
                else:
                    priority = 'medium'
                
                deployments.append({
                    'namespace': namespace,
                    'name': deployment_name,
                    'hpaName': hpa_name,
                    'startupFilterMinutes': 2,  # Default
                    'priority': priority
                })
        
        return deployments
    
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to get HPAs from cluster: {e}", file=sys.stderr)
        print("Make sure kubectl is configured and you have access to the cluster", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse kubectl output: {e}", file=sys.stderr)
        sys.exit(1)


def generate_helm_values(deployments: List[Dict], prometheus_url: str = None) -> Dict:
    """Generate Helm values.yaml structure"""
    
    values = {
        'config': {
            'prometheusUrl': prometheus_url or 'http://prometheus-server.monitoring:9090',
            'checkInterval': 60,
            'targetNodeUtilization': 30,
            'dryRun': False,
            'enablePredictive': True,
            'enableAutotuning': True,
            'costPerVcpuHour': 0.04,  # 1:8 ratio with memory
            'costPerGbMemoryHour': 0.005,
            'logLevel': 'INFO'
        },
        'deployments': deployments,
        'webhooks': {
            'slack': '',
            'teams': ''
        },
        'resources': {
            'requests': {
                'cpu': '200m',
                'memory': '512Mi'
            },
            'limits': {
                'cpu': '1000m',
                'memory': '1Gi'
            }
        },
        'persistence': {
            'enabled': True,
            'size': '10Gi'
        }
    }
    
    return values


def main():
    parser = argparse.ArgumentParser(
        description='Generate Helm values.yaml for Smart Autoscaler',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--csv',
        help='CSV file with deployment list'
    )
    
    parser.add_argument(
        '--auto-discover',
        action='store_true',
        help='Auto-discover HPAs from cluster using kubectl'
    )
    
    parser.add_argument(
        '--template',
        action='store_true',
        help='Generate CSV template'
    )
    
    parser.add_argument(
        '--prometheus-url',
        default='http://prometheus-server.monitoring:9090',
        help='Prometheus URL (default: http://prometheus-server.monitoring:9090)'
    )
    
    parser.add_argument(
        '--output',
        '-o',
        help='Output file (default: stdout)'
    )
    
    args = parser.parse_args()
    
    # Generate template
    if args.template:
        generate_template()
        return
    
    # Get deployments
    if args.csv:
        deployments = read_csv(args.csv)
        print(f"# Loaded {len(deployments)} deployments from {args.csv}", file=sys.stderr)
    elif args.auto_discover:
        print("# Auto-discovering HPAs from cluster...", file=sys.stderr)
        deployments = auto_discover_hpas()
        print(f"# Found {len(deployments)} HPAs", file=sys.stderr)
    else:
        print("Error: Must specify --csv, --auto-discover, or --template", file=sys.stderr)
        parser.print_help()
        sys.exit(1)
    
    # Generate values
    values = generate_helm_values(deployments, args.prometheus_url)
    
    # Output
    output = yaml.dump(values, default_flow_style=False, sort_keys=False)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"# Written to {args.output}", file=sys.stderr)
    else:
        print(output)
    
    # Print summary
    print(f"#", file=sys.stderr)
    print(f"# Generated Helm values for {len(deployments)} deployments", file=sys.stderr)
    print(f"#", file=sys.stderr)
    print(f"# Install with:", file=sys.stderr)
    if args.output:
        print(f"#   helm install smart-autoscaler ./helm/smart-autoscaler \\", file=sys.stderr)
        print(f"#     --namespace autoscaler-system \\", file=sys.stderr)
        print(f"#     --create-namespace \\", file=sys.stderr)
        print(f"#     --values {args.output}", file=sys.stderr)
    else:
        print(f"#   helm install smart-autoscaler ./helm/smart-autoscaler \\", file=sys.stderr)
        print(f"#     --namespace autoscaler-system \\", file=sys.stderr)
        print(f"#     --create-namespace \\", file=sys.stderr)
        print(f"#     --values values.yaml", file=sys.stderr)


if __name__ == '__main__':
    main()
