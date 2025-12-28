#!/bin/bash
# Test runner script

set -e

echo "Running tests..."
echo "================"

# Run basic tests
echo ""
echo "1. Basic import tests..."
python3 -m pytest tests/test_basic.py -v

# Run core feature tests
echo ""
echo "2. Core feature tests..."
python3 -m pytest tests/test_core_features.py -v

# Run all tests with coverage if available
echo ""
echo "3. All tests..."
python3 -m pytest tests/ -v --tb=short

echo ""
echo "✓ All tests passed!"
