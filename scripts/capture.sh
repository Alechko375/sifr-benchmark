#!/bin/bash

# SiFR Benchmark - Page Capture Script
# Usage: ./scripts/capture.sh <url> <page_name> [category]
#
# Example: ./scripts/capture.sh https://amazon.com/dp/B123 amazon_product ecommerce

URL=$1
PAGE_NAME=$2
CATEGORY=${3:-"uncategorized"}

if [ -z "$URL" ] || [ -z "$PAGE_NAME" ]; then
    echo "Usage: ./scripts/capture.sh <url> <page_name> [category]"
    echo "Example: ./scripts/capture.sh https://example.com/product my_product ecommerce"
    exit 1
fi

echo "🔍 Capturing: $URL"
echo "   Name: $PAGE_NAME"
echo "   Category: $CATEGORY"
echo ""

# Create output directories
mkdir -p "datasets/pages/$CATEGORY"
mkdir -p "datasets/formats/sifr"
mkdir -p "datasets/formats/html"
mkdir -p "datasets/formats/screenshots"

# Placeholder for actual capture logic
# In practice, you would use:
# 1. Element-to-LLM browser extension for SiFR
# 2. curl/wget for raw HTML
# 3. Puppeteer/Playwright for screenshots

echo "📋 Manual capture steps:"
echo ""
echo "1. Open URL in browser: $URL"
echo ""
echo "2. Capture SiFR (using Element-to-LLM extension):"
echo "   → Save as: datasets/formats/sifr/${PAGE_NAME}.sifr"
echo ""
echo "3. Capture raw HTML:"
echo "   curl '$URL' > datasets/formats/html/${PAGE_NAME}.html"
echo ""
echo "4. Capture screenshot (using browser DevTools or Puppeteer):"
echo "   → Save as: datasets/formats/screenshots/${PAGE_NAME}.png"
echo ""
echo "5. Create ground truth:"
echo "   cp benchmark/ground-truth/template.json benchmark/ground-truth/${PAGE_NAME}.json"
echo "   → Edit to add correct answers"
echo ""
echo "6. Create page metadata:"

cat << EOF > "datasets/pages/$CATEGORY/${PAGE_NAME}.json"
{
  "page_id": "${PAGE_NAME}",
  "url": "${URL}",
  "category": "${CATEGORY}",
  "captured_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "viewport": {
    "width": 1440,
    "height": 900
  },
  "formats_available": ["sifr", "html", "screenshot"],
  "notes": ""
}
EOF

echo "✅ Created: datasets/pages/$CATEGORY/${PAGE_NAME}.json"
echo ""
echo "Next: Complete manual capture steps above, then annotate ground truth."
