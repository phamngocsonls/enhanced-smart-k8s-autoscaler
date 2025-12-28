#!/bin/bash
# Example: Using the FinOps Recommendations API
# This script demonstrates how to get and apply resource optimization recommendations

set -e

# Configuration
DASHBOARD_URL="${DASHBOARD_URL:-http://localhost:5000}"
NAMESPACE="${NAMESPACE:-production}"
DEPLOYMENT="${DEPLOYMENT:-api-service}"
ANALYSIS_HOURS="${ANALYSIS_HOURS:-168}"  # 1 week

echo "🔍 Getting FinOps recommendations for $NAMESPACE/$DEPLOYMENT..."
echo "📊 Analyzing last $ANALYSIS_HOURS hours of data..."
echo ""

# Get recommendations
RESPONSE=$(curl -s "$DASHBOARD_URL/api/deployment/$NAMESPACE/$DEPLOYMENT/recommendations?hours=$ANALYSIS_HOURS")

# Check if we got an error
if echo "$RESPONSE" | jq -e '.error' > /dev/null 2>&1; then
    echo "❌ Error: $(echo "$RESPONSE" | jq -r '.error')"
    echo "💡 Suggestion: $(echo "$RESPONSE" | jq -r '.suggestion // "N/A"')"
    exit 1
fi

# Parse response
CURRENT_CPU=$(echo "$RESPONSE" | jq -r '.current.cpu_request_millicores')
CURRENT_MEMORY=$(echo "$RESPONSE" | jq -r '.current.memory_request_mb')
CURRENT_HPA=$(echo "$RESPONSE" | jq -r '.current.hpa_target_percent')
CURRENT_COST=$(echo "$RESPONSE" | jq -r '.current.monthly_cost_usd')

RECOMMENDED_CPU=$(echo "$RESPONSE" | jq -r '.recommended.cpu_request_millicores')
RECOMMENDED_MEMORY=$(echo "$RESPONSE" | jq -r '.recommended.memory_request_mb')
RECOMMENDED_HPA=$(echo "$RESPONSE" | jq -r '.recommended.hpa_target_percent')
RECOMMENDED_COST=$(echo "$RESPONSE" | jq -r '.recommended.monthly_cost_usd')

SAVINGS=$(echo "$RESPONSE" | jq -r '.savings.monthly_savings_usd')
SAVINGS_PERCENT=$(echo "$RESPONSE" | jq -r '.savings.savings_percent')
RECOMMENDATION_LEVEL=$(echo "$RESPONSE" | jq -r '.recommendation_level')
RECOMMENDATION_TEXT=$(echo "$RESPONSE" | jq -r '.recommendation_text')

DATA_POINTS=$(echo "$RESPONSE" | jq -r '.data_points_analyzed')
AVG_PODS=$(echo "$RESPONSE" | jq -r '.avg_pod_count')

# Display current state
echo "📋 Current Configuration:"
echo "   CPU Request:    ${CURRENT_CPU}m"
echo "   Memory Request: ${CURRENT_MEMORY}Mi"
echo "   HPA Target:     ${CURRENT_HPA}%"
echo "   Monthly Cost:   \$${CURRENT_COST}"
echo ""

# Display usage statistics
echo "📊 Usage Statistics (from $DATA_POINTS data points):"
CPU_AVG=$(echo "$RESPONSE" | jq -r '.usage_stats.cpu_avg_millicores')
CPU_P95=$(echo "$RESPONSE" | jq -r '.usage_stats.cpu_p95_millicores')
CPU_MAX=$(echo "$RESPONSE" | jq -r '.usage_stats.cpu_max_millicores')
MEM_AVG=$(echo "$RESPONSE" | jq -r '.usage_stats.memory_avg_mb')
MEM_P95=$(echo "$RESPONSE" | jq -r '.usage_stats.memory_p95_mb')
echo "   CPU:    Avg=${CPU_AVG}m, P95=${CPU_P95}m, Max=${CPU_MAX}m"
echo "   Memory: Avg=${MEM_AVG}Mi, P95=${MEM_P95}Mi"
echo "   Avg Pod Count: ${AVG_PODS}"
echo ""

# Display recommendations
echo "✨ Recommended Configuration:"
echo "   CPU Request:    ${RECOMMENDED_CPU}m ($(echo "$RESPONSE" | jq -r '.savings.cpu_reduction_percent')% reduction)"
echo "   Memory Request: ${RECOMMENDED_MEMORY}Mi ($(echo "$RESPONSE" | jq -r '.savings.memory_reduction_percent')% reduction)"
echo "   HPA Target:     ${RECOMMENDED_HPA}% ($(echo "$RESPONSE" | jq -r '.savings.hpa_adjustment_percent')% adjustment)"
echo "   Monthly Cost:   \$${RECOMMENDED_COST}"
echo ""

# Display savings
echo "💰 Cost Savings:"
echo "   Monthly Savings: \$${SAVINGS} (${SAVINGS_PERCENT}%)"
echo "   Recommendation Level: ${RECOMMENDATION_LEVEL}"
echo "   ${RECOMMENDATION_TEXT}"
echo ""

# Display warnings if any
WARNINGS=$(echo "$RESPONSE" | jq -r '.warnings[]' 2>/dev/null)
if [ -n "$WARNINGS" ]; then
    echo "⚠️  Warnings:"
    echo "$WARNINGS" | while IFS= read -r warning; do
        echo "   $warning"
    done
    echo ""
fi

# Display implementation steps
echo "🛠️  Implementation Steps:"
echo "$RESPONSE" | jq -r '.implementation | to_entries[] | "   \(.key): \(.value)"' | grep "^   step"
echo ""

# Save YAML snippet to file
YAML_FILE="/tmp/${DEPLOYMENT}-optimized.yaml"
echo "$RESPONSE" | jq -r '.implementation.yaml_snippet' > "$YAML_FILE"
echo "📝 YAML configuration saved to: $YAML_FILE"
echo ""

# Display YAML snippet
echo "📄 YAML Configuration:"
echo "---"
cat "$YAML_FILE"
echo "---"
echo ""

# Ask for confirmation to apply
if [ "$RECOMMENDATION_LEVEL" = "optimal" ]; then
    echo "✅ Resources are already well-optimized. No changes needed."
    exit 0
fi

echo "❓ Would you like to apply these recommendations? (yes/no)"
read -r APPLY

if [ "$APPLY" = "yes" ] || [ "$APPLY" = "y" ]; then
    echo ""
    echo "⚠️  IMPORTANT: Before applying, ensure you:"
    echo "   1. Have tested in staging environment"
    echo "   2. Are applying during low-traffic period"
    echo "   3. Have monitoring and alerting ready"
    echo "   4. Have a rollback plan"
    echo ""
    echo "❓ Continue? (yes/no)"
    read -r CONFIRM
    
    if [ "$CONFIRM" = "yes" ] || [ "$CONFIRM" = "y" ]; then
        echo ""
        echo "🚀 To apply these changes:"
        echo ""
        echo "1. Update your Deployment:"
        echo "   kubectl set resources deployment/$DEPLOYMENT -n $NAMESPACE \\"
        echo "     --requests=cpu=${RECOMMENDED_CPU}m,memory=${RECOMMENDED_MEMORY}Mi \\"
        echo "     --limits=cpu=$((RECOMMENDED_CPU * 2))m,memory=$((RECOMMENDED_MEMORY * 2))Mi"
        echo ""
        echo "2. Update your HPA:"
        echo "   kubectl patch hpa ${DEPLOYMENT}-hpa -n $NAMESPACE --type=json -p='[{\"op\": \"replace\", \"path\": \"/spec/metrics/0/resource/target/averageUtilization\", \"value\": ${RECOMMENDED_HPA%.*}}]'"
        echo ""
        echo "3. Monitor the deployment:"
        echo "   kubectl get hpa -n $NAMESPACE -w"
        echo ""
        echo "4. Check for issues:"
        echo "   kubectl top pods -n $NAMESPACE"
        echo "   kubectl get events -n $NAMESPACE --sort-by='.lastTimestamp'"
        echo ""
        echo "💡 Monitor for 24-48 hours and verify scaling behavior!"
    else
        echo "❌ Cancelled. No changes applied."
    fi
else
    echo "❌ Cancelled. No changes applied."
    echo "💡 You can review the YAML configuration at: $YAML_FILE"
fi

echo ""
echo "✅ Done!"
