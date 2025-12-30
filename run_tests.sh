#!/bin/bash
# Test runner script

set -e

echo "Running tests with coverage..."
echo "==============================="

# Detect Python binary
if command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN="python3.12"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  PYTHON_BIN="python"
fi

echo "Using Python: $PYTHON_BIN"
echo ""

# Run all tests with coverage
"$PYTHON_BIN" -m pytest tests/ -v --cov=src --cov-report=term --cov-report=html

echo ""
echo "✓ All tests passed!"
echo ""
echo "Coverage report generated in htmlcov/index.html"
