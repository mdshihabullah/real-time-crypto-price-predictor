#!/usr/bin/env python3
"""
Generate Grafana Dashboard ConfigMaps from JSON files
This script reads dashboard JSON files and creates Kubernetes ConfigMaps for automatic loading
"""

import json
import yaml
import os
import sys

def update_datasource_uids(obj):
    """Recursively update datasource UIDs to match our RisingWave datasource"""
    if isinstance(obj, dict):
        if 'datasource' in obj and isinstance(obj['datasource'], dict):
            if obj['datasource'].get('type') == 'grafana-postgresql-datasource':
                obj['datasource']['uid'] = 'risingwave'
                obj['datasource']['type'] = 'postgres'
        for value in obj.values():
            update_datasource_uids(value)
    elif isinstance(obj, list):
        for item in obj:
            update_datasource_uids(item)

def main():
    # Paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    dashboards_dir = os.path.join(project_root, 'dashboards', 'grafana')
    output_file = os.path.join(script_dir, 'manifests', 'infrastructure', 'grafana-dashboards.yaml')
    
    print(f"Looking for dashboards in: {dashboards_dir}")
    print(f"Output file: {output_file}")
    
    if not os.path.exists(dashboards_dir):
        print(f"Error: Dashboards directory not found: {dashboards_dir}")
        sys.exit(1)
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    configmaps = []
    
    # Process each JSON file in the dashboards directory
    for filename in os.listdir(dashboards_dir):
        if filename.endswith('.json'):
            print(f"Processing dashboard: {filename}")
            
            with open(os.path.join(dashboards_dir, filename), 'r') as f:
                try:
                    dashboard_json = json.load(f)
                except json.JSONDecodeError as e:
                    print(f"Error parsing {filename}: {e}")
                    continue
            
            # Update datasource UIDs to match our RisingWave datasource
            update_datasource_uids(dashboard_json)
            
            # Create ConfigMap name from filename
            name_part = filename.replace('.json', '').lower()
            # Clean up the name to be Kubernetes-compliant
            name_part = name_part.replace('_', '-').replace(' ', '-')
            # Remove numbers and special characters from the end
            import re
            name_part = re.sub(r'-\d+$', '', name_part)
            
            configmap_name = f'grafana-dashboard-{name_part}'
            
            configmap = {
                'apiVersion': 'v1',
                'kind': 'ConfigMap',
                'metadata': {
                    'name': configmap_name,
                    'namespace': 'grafana',
                    'labels': {
                        'grafana_dashboard': '1',
                        'app.kubernetes.io/name': 'grafana',
                        'app.kubernetes.io/component': 'dashboards'
                    }
                },
                'data': {
                    f'{name_part}.json': json.dumps(dashboard_json, separators=(',', ':'))
                }
            }
            configmaps.append(configmap)
    
    if not configmaps:
        print("No dashboard JSON files found!")
        sys.exit(1)
    
    # Write all ConfigMaps to a single YAML file
    with open(output_file, 'w') as f:
        for i, configmap in enumerate(configmaps):
            if i > 0:
                f.write('---\n')
            yaml.dump(configmap, f, default_flow_style=False, sort_keys=False)
    
    print(f"Generated {len(configmaps)} dashboard ConfigMaps in {output_file}")
    print("Dashboard ConfigMaps:")
    for configmap in configmaps:
        print(f"  - {configmap['metadata']['name']}")

if __name__ == '__main__':
    main() 