#!/usr/bin/env python3
"""
Cloud Pricing Update Script
Fetches latest pricing from cloud provider APIs and updates the pricing database

Usage:
  python scripts/update-pricing.py --provider gcp --region asia-southeast1
  python scripts/update-pricing.py --provider aws --region ap-southeast-1
  python scripts/update-pricing.py --provider azure --region southeastasia
  python scripts/update-pricing.py --all  # Update all providers

Can be scheduled as a cron job for daily updates:
  0 2 * * * /path/to/update-pricing.py --all
"""

import argparse
import requests
import json
import sys
from datetime import datetime

# Azure Retail Prices API (public, no auth required)
AZURE_API = "https://prices.azure.com/api/retail/prices"

def fetch_azure_pricing(region='southeastasia'):
    """Fetch Azure pricing from Retail Prices API"""
    print(f"Fetching Azure pricing for {region}...")
    
    try:
        # Filter for Virtual Machines in the specified region
        filter_query = f"armRegionName eq '{region}' and serviceName eq 'Virtual Machines' and priceType eq 'Consumption'"
        
        response = requests.get(
            AZURE_API,
            params={
                '$filter': filter_query,
                'currencyCode': 'USD'
            },
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"Error: API returned status {response.status_code}")
            return None
        
        data = response.json()
        items = data.get('Items', [])
        
        print(f"Found {len(items)} pricing items")
        
        # Parse and aggregate pricing by instance family
        pricing = {}
        for item in items:
            sku_name = item.get('skuName', '')
            unit_price = item.get('unitPrice', 0)
            unit_of_measure = item.get('unitOfMeasure', '')
            
            # Extract instance family (e.g., "Standard_D4s_v3" -> "standard_d")
            if sku_name and unit_of_measure == '1 Hour':
                sku_lower = sku_name.lower()
                if sku_lower.startswith('standard_'):
                    # Extract family
                    parts = sku_lower.split('_')
                    if len(parts) >= 2:
                        family = f"{parts[0]}_{parts[1][0]}"  # e.g., standard_d
                        
                        if family not in pricing:
                            pricing[family] = []
                        pricing[family].append(unit_price)
        
        # Calculate average pricing per family
        result = {}
        for family, prices in pricing.items():
            if prices:
                avg_price = sum(prices) / len(prices)
                # Estimate vCPU and memory pricing (rough approximation)
                result[family] = {
                    'vcpu': round(avg_price * 0.7, 4),  # ~70% for CPU
                    'memory_gb': round(avg_price * 0.3 / 4, 4)  # ~30% for memory, /4 for GB
                }
        
        return result
        
    except Exception as e:
        print(f"Error fetching Azure pricing: {e}")
        return None

def print_pricing_dict(pricing, provider):
    """Print pricing in Python dict format"""
    print(f"\n# {provider.upper()} Pricing")
    print(f"{provider.upper()}_PRICING = {{")
    for family, prices in sorted(pricing.items()):
        print(f"    '{family}': {{'vcpu': {prices['vcpu']}, 'memory_gb': {prices['memory_gb']}}},")
    print("}")

def main():
    parser = argparse.ArgumentParser(description='Update cloud pricing from APIs')
    parser.add_argument('--provider', choices=['gcp', 'aws', 'azure', 'all'], 
                       help='Cloud provider to update')
    parser.add_argument('--region', help='Region to fetch pricing for')
    parser.add_argument('--output', help='Output file (default: print to stdout)')
    
    args = parser.parse_args()
    
    if not args.provider:
        parser.print_help()
        sys.exit(1)
    
    results = {}
    
    if args.provider in ['azure', 'all']:
        region = args.region or 'southeastasia'
        azure_pricing = fetch_azure_pricing(region)
        if azure_pricing:
            results['azure'] = azure_pricing
            print_pricing_dict(azure_pricing, 'azure')
    
    if args.provider in ['gcp', 'all']:
        print("\nGCP Cloud Billing API requires authentication.")
        print("Please use gcloud CLI or set up service account:")
        print("  gcloud auth application-default login")
        print("  export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json")
    
    if args.provider in ['aws', 'all']:
        print("\nAWS Pricing API returns large JSON files (100MB+).")
        print("Consider using AWS Price List API with filters:")
        print("  aws pricing get-products --service-code AmazonEC2 --region ap-southeast-1")
    
    if args.output and results:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nPricing data saved to {args.output}")
    
    print(f"\nLast updated: {datetime.now().isoformat()}")

if __name__ == '__main__':
    main()
