#!/bin/bash
# Test runner script

set -e

echo "Running tests..."
echo "================"

# Run basic tests
echo ""
echo "1. Basic import tests..."
if command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN="python3.12"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  PYTHON_BIN="python"
fi

"$PYTHON_BIN" -m pytest tests/test_basic.py -v

# Run core feature tests
echo ""
echo "2. Core feature tests..."
"$PYTHON_BIN" -m pytest tests/test_core_features.py -v

# Run all tests with coverage if available
echo ""
echo "3. All tests..."
"$PYTHON_BIN" -m pytest tests/ -v --tb=short

echo ""
echo "✓ All tests passed!"
