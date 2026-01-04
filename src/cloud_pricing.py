"""
Cloud Pricing Auto-Detection
Automatically detect cloud provider and instance types to get accurate pricing
"""

import logging
import re
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class CloudPricingDetector:
    """Detect cloud provider and get pricing from instance types"""
    
    # GCP pricing (asia-southeast1/Singapore, on-demand, per hour)
    # Source: https://cloud.google.com/compute/vm-instance-pricing
    GCP_PRICING = {
        # General Purpose (E2 - Shared-core, cost-optimized)
        'e2-micro': {'vcpu': 0.0084, 'memory_gb': 0.0011},
        'e2-small': {'vcpu': 0.0168, 'memory_gb': 0.0022},
        'e2-medium': {'vcpu': 0.0336, 'memory_gb': 0.0045},
        'e2-standard': {'vcpu': 0.0369, 'memory_gb': 0.0049},
        'e2-highmem': {'vcpu': 0.0369, 'memory_gb': 0.0066},
        'e2-highcpu': {'vcpu': 0.0369, 'memory_gb': 0.0033},
        
        # General Purpose (N1 - First generation)
        'n1-standard': {'vcpu': 0.0523, 'memory_gb': 0.0070},
        'n1-highmem': {'vcpu': 0.0523, 'memory_gb': 0.0094},
        'n1-highcpu': {'vcpu': 0.0523, 'memory_gb': 0.0047},
        
        # General Purpose (N2 - Second generation, Intel)
        'n2-standard': {'vcpu': 0.0537, 'memory_gb': 0.0072},
        'n2-highmem': {'vcpu': 0.0537, 'memory_gb': 0.0096},
        'n2-highcpu': {'vcpu': 0.0537, 'memory_gb': 0.0048},
        
        # General Purpose (N2D - AMD EPYC)
        'n2d-standard': {'vcpu': 0.0430, 'memory_gb': 0.0058},
        'n2d-highmem': {'vcpu': 0.0430, 'memory_gb': 0.0077},
        'n2d-highcpu': {'vcpu': 0.0430, 'memory_gb': 0.0039},
        
        # General Purpose (T2D - AMD, cost-optimized)
        't2d-standard': {'vcpu': 0.0387, 'memory_gb': 0.0052},
        
        # General Purpose (T2A - Arm-based, cost-optimized)
        't2a-standard': {'vcpu': 0.0310, 'memory_gb': 0.0041},
        
        # Compute Optimized (C2 - Intel, high-performance)
        'c2-standard': {'vcpu': 0.0577, 'memory_gb': 0.0077},
        
        # Compute Optimized (C2D - AMD EPYC, high-performance)
        'c2d-standard': {'vcpu': 0.0461, 'memory_gb': 0.0062},
        'c2d-highcpu': {'vcpu': 0.0461, 'memory_gb': 0.0031},
        
        # Compute Optimized (C3 - Intel Sapphire Rapids, latest)
        'c3-standard': {'vcpu': 0.0620, 'memory_gb': 0.0083},
        'c3-highcpu': {'vcpu': 0.0620, 'memory_gb': 0.0041},
        
        # Compute Optimized (C3D - AMD EPYC Genoa, latest)
        'c3d-standard': {'vcpu': 0.0496, 'memory_gb': 0.0066},
        'c3d-highcpu': {'vcpu': 0.0496, 'memory_gb': 0.0033},
        
        # Memory Optimized (M1 - First generation)
        'm1-ultramem': {'vcpu': 0.0654, 'memory_gb': 0.0163},
        'm1-megamem': {'vcpu': 0.0654, 'memory_gb': 0.0163},
        
        # Memory Optimized (M2 - Second generation)
        'm2-ultramem': {'vcpu': 0.0739, 'memory_gb': 0.0099},
        'm2-megamem': {'vcpu': 0.0739, 'memory_gb': 0.0099},
        
        # Memory Optimized (M3 - Latest generation)
        'm3-ultramem': {'vcpu': 0.0795, 'memory_gb': 0.0106},
        'm3-megamem': {'vcpu': 0.0795, 'memory_gb': 0.0106},
        
        # Accelerator Optimized (A2 - GPU instances)
        'a2-highgpu': {'vcpu': 0.0620, 'memory_gb': 0.0083},
        'a2-megagpu': {'vcpu': 0.0620, 'memory_gb': 0.0083},
        
        # Accelerator Optimized (A3 - Latest GPU instances)
        'a3-highgpu': {'vcpu': 0.0700, 'memory_gb': 0.0093},
        'a3-megagpu': {'vcpu': 0.0700, 'memory_gb': 0.0093},
        
        # Accelerator Optimized (G2 - GPU instances)
        'g2-standard': {'vcpu': 0.0620, 'memory_gb': 0.0083},
    }
    
    # AWS pricing (ap-southeast-1/Singapore, on-demand, per hour)
    # Source: https://aws.amazon.com/ec2/pricing/on-demand/
    AWS_PRICING = {
        # General Purpose (T2 - Burstable)
        't2': {'vcpu': 0.0464, 'memory_gb': 0.0058},
        
        # General Purpose (T3 - Burstable, latest)
        't3': {'vcpu': 0.0458, 'memory_gb': 0.0057},
        't3a': {'vcpu': 0.0411, 'memory_gb': 0.0051},
        
        # General Purpose (T4g - Arm-based, Graviton2)
        't4g': {'vcpu': 0.0368, 'memory_gb': 0.0046},
        
        # General Purpose (M5 - Intel)
        'm5': {'vcpu': 0.0528, 'memory_gb': 0.0066},
        'm5a': {'vcpu': 0.0475, 'memory_gb': 0.0059},
        'm5n': {'vcpu': 0.0655, 'memory_gb': 0.0082},
        'm5zn': {'vcpu': 0.0792, 'memory_gb': 0.0099},
        
        # General Purpose (M6i - Intel, latest)
        'm6i': {'vcpu': 0.0528, 'memory_gb': 0.0066},
        'm6a': {'vcpu': 0.0475, 'memory_gb': 0.0059},
        'm6in': {'vcpu': 0.0655, 'memory_gb': 0.0082},
        
        # General Purpose (M6g - Arm-based, Graviton2)
        'm6g': {'vcpu': 0.0422, 'memory_gb': 0.0053},
        'm6gd': {'vcpu': 0.0475, 'memory_gb': 0.0059},
        
        # General Purpose (M7g - Arm-based, Graviton3, latest)
        'm7g': {'vcpu': 0.0448, 'memory_gb': 0.0056},
        'm7gd': {'vcpu': 0.0504, 'memory_gb': 0.0063},
        
        # General Purpose (M7i - Intel, latest)
        'm7i': {'vcpu': 0.0560, 'memory_gb': 0.0070},
        'm7i-flex': {'vcpu': 0.0476, 'memory_gb': 0.0060},
        
        # Compute Optimized (C5 - Intel)
        'c5': {'vcpu': 0.0468, 'memory_gb': 0.0117},
        'c5a': {'vcpu': 0.0423, 'memory_gb': 0.0106},
        'c5n': {'vcpu': 0.0594, 'memory_gb': 0.0149},
        
        # Compute Optimized (C6i - Intel, latest)
        'c6i': {'vcpu': 0.0468, 'memory_gb': 0.0117},
        'c6a': {'vcpu': 0.0420, 'memory_gb': 0.0105},
        'c6in': {'vcpu': 0.0594, 'memory_gb': 0.0149},
        
        # Compute Optimized (C6g - Arm-based, Graviton2)
        'c6g': {'vcpu': 0.0374, 'memory_gb': 0.0094},
        'c6gd': {'vcpu': 0.0422, 'memory_gb': 0.0106},
        'c6gn': {'vcpu': 0.0475, 'memory_gb': 0.0119},
        
        # Compute Optimized (C7g - Arm-based, Graviton3, latest)
        'c7g': {'vcpu': 0.0397, 'memory_gb': 0.0099},
        'c7gd': {'vcpu': 0.0448, 'memory_gb': 0.0112},
        'c7gn': {'vcpu': 0.0504, 'memory_gb': 0.0126},
        
        # Compute Optimized (C7i - Intel, latest)
        'c7i': {'vcpu': 0.0497, 'memory_gb': 0.0124},
        
        # Memory Optimized (R5 - Intel)
        'r5': {'vcpu': 0.0693, 'memory_gb': 0.0087},
        'r5a': {'vcpu': 0.0622, 'memory_gb': 0.0078},
        'r5n': {'vcpu': 0.0820, 'memory_gb': 0.0103},
        'r5b': {'vcpu': 0.0820, 'memory_gb': 0.0103},
        
        # Memory Optimized (R6i - Intel, latest)
        'r6i': {'vcpu': 0.0693, 'memory_gb': 0.0087},
        'r6a': {'vcpu': 0.0622, 'memory_gb': 0.0078},
        'r6in': {'vcpu': 0.0820, 'memory_gb': 0.0103},
        
        # Memory Optimized (R6g - Arm-based, Graviton2)
        'r6g': {'vcpu': 0.0554, 'memory_gb': 0.0069},
        'r6gd': {'vcpu': 0.0622, 'memory_gb': 0.0078},
        
        # Memory Optimized (R7g - Arm-based, Graviton3, latest)
        'r7g': {'vcpu': 0.0588, 'memory_gb': 0.0074},
        'r7gd': {'vcpu': 0.0661, 'memory_gb': 0.0083},
        
        # Memory Optimized (R7i - Intel, latest)
        'r7i': {'vcpu': 0.0735, 'memory_gb': 0.0092},
        'r7iz': {'vcpu': 0.0882, 'memory_gb': 0.0110},
        
        # Memory Optimized (X1 - High memory)
        'x1': {'vcpu': 0.1466, 'memory_gb': 0.0183},
        'x1e': {'vcpu': 0.2933, 'memory_gb': 0.0367},
        
        # Memory Optimized (X2 - High memory, latest)
        'x2idn': {'vcpu': 0.1833, 'memory_gb': 0.0229},
        'x2iedn': {'vcpu': 0.3666, 'memory_gb': 0.0458},
        'x2iezn': {'vcpu': 0.3666, 'memory_gb': 0.0458},
        
        # Storage Optimized (I3 - NVMe SSD)
        'i3': {'vcpu': 0.0693, 'memory_gb': 0.0087},
        'i3en': {'vcpu': 0.0820, 'memory_gb': 0.0103},
        
        # Storage Optimized (I4i - Latest NVMe SSD)
        'i4i': {'vcpu': 0.0735, 'memory_gb': 0.0092},
        'i4g': {'vcpu': 0.0588, 'memory_gb': 0.0074},
    }
    
    # Azure pricing (Southeast Asia/Singapore, on-demand, per hour)
    # Source: https://azure.microsoft.com/en-us/pricing/details/virtual-machines/
    AZURE_PRICING = {
        # General Purpose (A-series - Basic)
        'standard_a': {'vcpu': 0.0440, 'memory_gb': 0.0055},
        
        # General Purpose (B-series - Burstable)
        'standard_b': {'vcpu': 0.0458, 'memory_gb': 0.0057},
        
        # General Purpose (D-series v2)
        'standard_d': {'vcpu': 0.0528, 'memory_gb': 0.0066},
        'standard_ds': {'vcpu': 0.0581, 'memory_gb': 0.0073},
        
        # General Purpose (D-series v3)
        'standard_d2': {'vcpu': 0.0528, 'memory_gb': 0.0066},
        'standard_d2s': {'vcpu': 0.0581, 'memory_gb': 0.0073},
        
        # General Purpose (D-series v4)
        'standard_d4': {'vcpu': 0.0560, 'memory_gb': 0.0070},
        'standard_d4s': {'vcpu': 0.0616, 'memory_gb': 0.0077},
        'standard_d4d': {'vcpu': 0.0616, 'memory_gb': 0.0077},
        'standard_d4ds': {'vcpu': 0.0678, 'memory_gb': 0.0085},
        
        # General Purpose (D-series v5)
        'standard_d5': {'vcpu': 0.0594, 'memory_gb': 0.0074},
        'standard_d5s': {'vcpu': 0.0653, 'memory_gb': 0.0082},
        'standard_d5d': {'vcpu': 0.0653, 'memory_gb': 0.0082},
        'standard_d5ds': {'vcpu': 0.0719, 'memory_gb': 0.0090},
        
        # General Purpose (Dps-series v5 - Arm-based)
        'standard_dps': {'vcpu': 0.0475, 'memory_gb': 0.0059},
        'standard_dpds': {'vcpu': 0.0523, 'memory_gb': 0.0065},
        
        # Compute Optimized (F-series v2)
        'standard_f': {'vcpu': 0.0523, 'memory_gb': 0.0131},
        'standard_fs': {'vcpu': 0.0575, 'memory_gb': 0.0144},
        
        # Compute Optimized (Fx-series)
        'standard_fx': {'vcpu': 0.0594, 'memory_gb': 0.0149},
        'standard_fxs': {'vcpu': 0.0653, 'memory_gb': 0.0163},
        
        # Memory Optimized (E-series v3)
        'standard_e': {'vcpu': 0.0693, 'memory_gb': 0.0087},
        'standard_es': {'vcpu': 0.0762, 'memory_gb': 0.0095},
        
        # Memory Optimized (E-series v4)
        'standard_e4': {'vcpu': 0.0735, 'memory_gb': 0.0092},
        'standard_e4s': {'vcpu': 0.0809, 'memory_gb': 0.0101},
        'standard_e4d': {'vcpu': 0.0809, 'memory_gb': 0.0101},
        'standard_e4ds': {'vcpu': 0.0890, 'memory_gb': 0.0111},
        
        # Memory Optimized (E-series v5)
        'standard_e5': {'vcpu': 0.0780, 'memory_gb': 0.0098},
        'standard_e5s': {'vcpu': 0.0858, 'memory_gb': 0.0107},
        'standard_e5d': {'vcpu': 0.0858, 'memory_gb': 0.0107},
        'standard_e5ds': {'vcpu': 0.0944, 'memory_gb': 0.0118},
        
        # Memory Optimized (Eps-series v5 - Arm-based)
        'standard_eps': {'vcpu': 0.0624, 'memory_gb': 0.0078},
        'standard_epds': {'vcpu': 0.0686, 'memory_gb': 0.0086},
        
        # Memory Optimized (M-series - High memory)
        'standard_m': {'vcpu': 0.1100, 'memory_gb': 0.0138},
        'standard_ms': {'vcpu': 0.1210, 'memory_gb': 0.0151},
        
        # Memory Optimized (Mv2-series - Very high memory)
        'standard_m2': {'vcpu': 0.1320, 'memory_gb': 0.0165},
        'standard_m2s': {'vcpu': 0.1452, 'memory_gb': 0.0182},
        
        # Storage Optimized (L-series v2)
        'standard_l': {'vcpu': 0.0693, 'memory_gb': 0.0087},
        'standard_ls': {'vcpu': 0.0762, 'memory_gb': 0.0095},
        
        # Storage Optimized (L-series v3)
        'standard_l3': {'vcpu': 0.0735, 'memory_gb': 0.0092},
        'standard_l3s': {'vcpu': 0.0809, 'memory_gb': 0.0101},
        
        # GPU Optimized (NC-series)
        'standard_nc': {'vcpu': 0.0900, 'memory_gb': 0.0113},
        'standard_ncs': {'vcpu': 0.0990, 'memory_gb': 0.0124},
        
        # GPU Optimized (ND-series)
        'standard_nd': {'vcpu': 0.1100, 'memory_gb': 0.0138},
        'standard_nds': {'vcpu': 0.1210, 'memory_gb': 0.0151},
    }
    
    # Default fallback pricing (Singapore region average across clouds)
    DEFAULT_PRICING = {
        'vcpu': 0.045,  # Average for Singapore region
        'memory_gb': 0.006  # Average for Singapore region
    }
    
    def __init__(self, core_v1):
        self.core_v1 = core_v1
        self.detected_provider = None
        self.detected_pricing = None
    
    def detect_cloud_provider(self) -> Optional[str]:
        """Detect cloud provider from node labels"""
        try:
            nodes = self.core_v1.list_node()
            
            for node in nodes.items:
                labels = node.metadata.labels or {}
                
                # Check for cloud provider labels
                if 'cloud.google.com/gke-nodepool' in labels or \
                   'beta.kubernetes.io/instance-type' in labels and labels.get('beta.kubernetes.io/instance-type', '').startswith('n'):
                    return 'gcp'
                
                if 'eks.amazonaws.com/nodegroup' in labels or \
                   'node.kubernetes.io/instance-type' in labels and any(labels.get('node.kubernetes.io/instance-type', '').startswith(t) for t in ['t3', 'm5', 'c5', 'r5']):
                    return 'aws'
                
                if 'kubernetes.azure.com/cluster' in labels or \
                   'node.kubernetes.io/instance-type' in labels and 'standard_' in labels.get('node.kubernetes.io/instance-type', '').lower():
                    return 'azure'
            
            logger.warning("Could not detect cloud provider from node labels")
            return None
            
        except Exception as e:
            logger.error(f"Failed to detect cloud provider: {e}")
            return None
    
    def detect_region(self) -> Optional[str]:
        """Detect region from node labels"""
        try:
            nodes = self.core_v1.list_node()
            
            for node in nodes.items:
                labels = node.metadata.labels or {}
                
                # GCP region labels
                region = (
                    labels.get('topology.kubernetes.io/region') or
                    labels.get('failure-domain.beta.kubernetes.io/region') or
                    labels.get('cloud.google.com/gke-nodepool-region')
                )
                
                if region:
                    logger.info(f"Detected region from node labels: {region}")
                    return region
            
            logger.warning("Could not detect region from node labels")
            return None
            
        except Exception as e:
            logger.error(f"Failed to detect region: {e}")
            return None
    
    def get_region_display_name(self, provider: str, region: str) -> str:
        """Get human-readable region name"""
        region_names = {
            'gcp': {
                'asia-southeast1': 'Singapore',
                'asia-southeast2': 'Jakarta',
                'asia-east1': 'Taiwan',
                'asia-east2': 'Hong Kong',
                'asia-northeast1': 'Tokyo',
                'asia-northeast2': 'Osaka',
                'asia-northeast3': 'Seoul',
                'asia-south1': 'Mumbai',
                'asia-south2': 'Delhi',
                'us-central1': 'Iowa',
                'us-east1': 'South Carolina',
                'us-east4': 'Virginia',
                'us-west1': 'Oregon',
                'europe-west1': 'Belgium',
                'europe-west2': 'London',
            },
            'aws': {
                'ap-southeast-1': 'Singapore',
                'ap-southeast-2': 'Sydney',
                'ap-southeast-3': 'Jakarta',
                'ap-east-1': 'Hong Kong',
                'ap-northeast-1': 'Tokyo',
                'ap-northeast-2': 'Seoul',
                'ap-northeast-3': 'Osaka',
                'ap-south-1': 'Mumbai',
                'us-east-1': 'Virginia',
                'us-east-2': 'Ohio',
                'us-west-1': 'California',
                'us-west-2': 'Oregon',
                'eu-west-1': 'Ireland',
                'eu-west-2': 'London',
            },
            'azure': {
                'southeastasia': 'Singapore',
                'eastasia': 'Hong Kong',
                'australiaeast': 'Sydney',
                'japaneast': 'Tokyo',
                'koreacentral': 'Seoul',
                'centralindia': 'Mumbai',
                'eastus': 'Virginia',
                'eastus2': 'Virginia',
                'westus': 'California',
                'westus2': 'Washington',
                'northeurope': 'Ireland',
                'westeurope': 'Netherlands',
            }
        }
        
        return region_names.get(provider, {}).get(region, region)
    
    def get_instance_type_from_node(self, node_name: str) -> Optional[str]:
        """Get instance type from node"""
        try:
            node = self.core_v1.read_node(node_name)
            labels = node.metadata.labels or {}
            
            # Try different label keys
            instance_type = (
                labels.get('node.kubernetes.io/instance-type') or
                labels.get('beta.kubernetes.io/instance-type') or
                labels.get('node.kubernetes.io/machine-type')
            )
            
            return instance_type
            
        except Exception as e:
            logger.warning(f"Failed to get instance type for node {node_name}: {e}")
            return None
    
    def extract_instance_family(self, instance_type: str, provider: str) -> Optional[str]:
        """Extract instance family from full instance type"""
        if not instance_type:
            return None
        
        instance_type = instance_type.lower()
        
        if provider == 'gcp':
            # GCP: n1-standard-4 -> n1-standard
            match = re.match(r'^([a-z0-9]+-[a-z]+)', instance_type)
            if match:
                return match.group(1)
        
        elif provider == 'aws':
            # AWS: m5.xlarge -> m5
            match = re.match(r'^([a-z0-9]+)', instance_type)
            if match:
                return match.group(1)
        
        elif provider == 'azure':
            # Azure: Standard_D4s_v3 -> standard_d
            match = re.match(r'^(standard_[a-z]+)', instance_type.lower())
            if match:
                return match.group(1)
        
        return None
    
    def get_pricing_for_instance_family(self, instance_family: str, provider: str) -> Optional[Dict[str, float]]:
        """Get pricing for instance family"""
        if provider == 'gcp':
            return self.GCP_PRICING.get(instance_family)
        elif provider == 'aws':
            return self.AWS_PRICING.get(instance_family)
        elif provider == 'azure':
            return self.AZURE_PRICING.get(instance_family)
        return None
    
    def auto_detect_pricing(self) -> Tuple[float, float]:
        """
        Auto-detect cloud pricing from cluster nodes
        Returns: (vcpu_price_per_hour, memory_gb_price_per_hour)
        """
        try:
            # Detect cloud provider
            provider = self.detect_cloud_provider()
            if not provider:
                logger.info("Using default pricing (cloud provider not detected)")
                return self.DEFAULT_PRICING['vcpu'], self.DEFAULT_PRICING['memory_gb']
            
            self.detected_provider = provider
            
            # Detect region
            region = self.detect_region()
            if region:
                region_name = self.get_region_display_name(provider, region)
                logger.info(f"Detected cloud provider: {provider.upper()}, Region: {region} ({region_name})")
            else:
                logger.info(f"Detected cloud provider: {provider.upper()}, Region: unknown (using default)")
            
            # Get instance types from nodes
            nodes = self.core_v1.list_node()
            instance_families = {}
            
            for node in nodes.items:
                instance_type = self.get_instance_type_from_node(node.metadata.name)
                if instance_type:
                    family = self.extract_instance_family(instance_type, provider)
                    if family:
                        instance_families[family] = instance_families.get(family, 0) + 1
            
            if not instance_families:
                logger.warning(f"No instance types detected for {provider}, using default pricing")
                return self.DEFAULT_PRICING['vcpu'], self.DEFAULT_PRICING['memory_gb']
            
            # Use most common instance family
            most_common_family = max(instance_families, key=instance_families.get)
            pricing = self.get_pricing_for_instance_family(most_common_family, provider)
            
            if pricing:
                self.detected_pricing = pricing
                logger.info(f"Using pricing from {provider.upper()} {most_common_family}: "
                          f"${pricing['vcpu']:.4f}/vCPU/hr, ${pricing['memory_gb']:.4f}/GB/hr")
                return pricing['vcpu'], pricing['memory_gb']
            else:
                logger.warning(f"No pricing data for {provider} {most_common_family}, using default")
                return self.DEFAULT_PRICING['vcpu'], self.DEFAULT_PRICING['memory_gb']
            
        except Exception as e:
            logger.error(f"Failed to auto-detect pricing: {e}")
            return self.DEFAULT_PRICING['vcpu'], self.DEFAULT_PRICING['memory_gb']
    
    def get_pricing_info(self) -> Dict:
        """Get detected pricing information for display"""
        # Detect region for display
        region = self.detect_region()
        region_display = self.get_region_display_name(
            self.detected_provider or 'unknown', 
            region or 'unknown'
        ) if region else 'unknown'
        
        return {
            'provider': self.detected_provider or 'unknown',
            'region': region or 'unknown',
            'region_name': region_display,
            'vcpu_price': self.detected_pricing['vcpu'] if self.detected_pricing else self.DEFAULT_PRICING['vcpu'],
            'memory_gb_price': self.detected_pricing['memory_gb'] if self.detected_pricing else self.DEFAULT_PRICING['memory_gb'],
            'auto_detected': self.detected_pricing is not None,
            'source': f"{self.detected_provider.upper()} {region_display} pricing" if self.detected_provider and region else "Default pricing"
        }
