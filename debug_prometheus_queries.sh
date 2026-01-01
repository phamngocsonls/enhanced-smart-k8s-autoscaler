#!/bin/bash
# Debug Prometheus Queries for Cluster Monitoring

echo "=== Debugging Prometheus Queries ==="
echo ""

# Prometheus URL (adjust if needed)
PROM_URL="http://localhost:9091"
NODE_NAME="orbstack"

echo "Testing CPU queries for node: $NODE_NAME"
echo "================================================"

# Query 1: node_exporter with instance label
echo -e "\n1. node_cpu_seconds_total (instance label):"
curl -s "${PROM_URL}/api/v1/query?query=sum(rate(node_cpu_seconds_total{mode!=\"idle\",instance=~\".*${NODE_NAME}.*\"}[5m]))" | jq -r '.data.result[0].value[1] // "NO DATA"'

# Query 2: node_exporter with node label
echo -e "\n2. node_cpu_seconds_total (node label):"
curl -s "${PROM_URL}/api/v1/query?query=sum(rate(node_cpu_seconds_total{mode!=\"idle\",node=\"${NODE_NAME}\"}[5m]))" | jq -r '.data.result[0].value[1] // "NO DATA"'

# Query 3: container metrics by node
echo -e "\n3. container_cpu_usage_seconds_total (node label):"
curl -s "${PROM_URL}/api/v1/query?query=sum(rate(container_cpu_usage_seconds_total{node=\"${NODE_NAME}\",container!=\"\",container!=\"POD\"}[5m]))" | jq -r '.data.result[0].value[1] // "NO DATA"'

# Query 4: container metrics by instance
echo -e "\n4. container_cpu_usage_seconds_total (instance label):"
curl -s "${PROM_URL}/api/v1/query?query=sum(rate(container_cpu_usage_seconds_total{instance=~\".*${NODE_NAME}.*\",container!=\"\",container!=\"POD\"}[5m]))" | jq -r '.data.result[0].value[1] // "NO DATA"'

# Query 5: Simple node CPU without rate
echo -e "\n5. node_cpu_seconds_total (no rate):"
curl -s "${PROM_URL}/api/v1/query?query=sum(node_cpu_seconds_total{mode!=\"idle\",instance=~\".*${NODE_NAME}.*\"})/100" | jq -r '.data.result[0].value[1] // "NO DATA"'

echo -e "\n\n================================================"
echo "Testing Memory queries for node: $NODE_NAME"
echo "================================================"

# Memory Query 1: node_memory with instance label
echo -e "\n1. node_memory (instance label):"
curl -s "${PROM_URL}/api/v1/query?query=node_memory_MemTotal_bytes{instance=~\".*${NODE_NAME}.*\"}-node_memory_MemAvailable_bytes{instance=~\".*${NODE_NAME}.*\"}" | jq -r '.data.result[0].value[1] // "NO DATA"'

# Memory Query 2: node_memory with node label
echo -e "\n2. node_memory (node label):"
curl -s "${PROM_URL}/api/v1/query?query=node_memory_MemTotal_bytes{node=\"${NODE_NAME}\"}-node_memory_MemAvailable_bytes{node=\"${NODE_NAME}\"}" | jq -r '.data.result[0].value[1] // "NO DATA"'

# Memory Query 3: container memory by node
echo -e "\n3. container_memory_working_set_bytes (node label):"
curl -s "${PROM_URL}/api/v1/query?query=sum(container_memory_working_set_bytes{node=\"${NODE_NAME}\",container!=\"\",container!=\"POD\"})" | jq -r '.data.result[0].value[1] // "NO DATA"'

# Memory Query 4: container memory by instance
echo -e "\n4. container_memory_working_set_bytes (instance label):"
curl -s "${PROM_URL}/api/v1/query?query=sum(container_memory_working_set_bytes{instance=~\".*${NODE_NAME}.*\",container!=\"\",container!=\"POD\"})" | jq -r '.data.result[0].value[1] // "NO DATA"'

# Memory Query 5: Simple node memory active
echo -e "\n5. node_memory_Active_bytes (instance label):"
curl -s "${PROM_URL}/api/v1/query?query=node_memory_Active_bytes{instance=~\".*${NODE_NAME}.*\"}" | jq -r '.data.result[0].value[1] // "NO DATA"'

echo -e "\n\n================================================"
echo "Checking available labels for container_cpu_usage_seconds_total:"
echo "================================================"
curl -s "${PROM_URL}/api/v1/query?query=container_cpu_usage_seconds_total" | jq -r '.data.result[0].metric | keys[]' | head -10

echo -e "\n\nDone!"
