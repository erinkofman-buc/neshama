#!/bin/bash
set -e

cd "$(dirname "$0")/tests"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
  echo "Installing dependencies..."
  npm install
  npx playwright install chromium
fi

# Run tests
echo "Running Neshama E2E smoke tests..."
npx playwright test "$@"

# Generate report if not already generated
if [ -f "test-results/community-member.json" ] && [ -f "test-results/shiva-organizer.json" ] && [ -f "test-results/caterer-directory.json" ]; then
  npm run report
fi

echo ""
echo "Report saved to tests/playwright-report.md"
echo "Screenshots saved to tests/screenshots/"
