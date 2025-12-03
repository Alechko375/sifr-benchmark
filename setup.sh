#!/bin/bash

# SiFR Benchmark - Directory Setup Script
# Run once to create folder structure

echo "🚀 Creating SiFR Benchmark directory structure..."

# Create main directories
mkdir -p benchmark/ground-truth
mkdir -p datasets/pages/ecommerce
mkdir -p datasets/pages/news
mkdir -p datasets/pages/saas
mkdir -p datasets/pages/forms
mkdir -p datasets/pages/social
mkdir -p datasets/formats/sifr
mkdir -p datasets/formats/html
mkdir -p datasets/formats/axtree
mkdir -p datasets/formats/screenshots
mkdir -p examples
mkdir -p results/raw
mkdir -p results/analysis
mkdir -p src
mkdir -p scripts

# Create .gitkeep files to preserve empty directories
touch datasets/pages/ecommerce/.gitkeep
touch datasets/pages/news/.gitkeep
touch datasets/pages/saas/.gitkeep
touch datasets/pages/forms/.gitkeep
touch datasets/pages/social/.gitkeep
touch datasets/formats/sifr/.gitkeep
touch datasets/formats/html/.gitkeep
touch datasets/formats/axtree/.gitkeep
touch datasets/formats/screenshots/.gitkeep
touch results/raw/.gitkeep
touch results/analysis/.gitkeep

echo "✅ Directory structure created!"
echo ""
echo "📁 Structure:"
echo "."
echo "├── benchmark/"
echo "│   ├── ground-truth/"
echo "│   ├── protocol.md"
echo "│   └── tasks.json"
echo "├── datasets/"
echo "│   ├── pages/{ecommerce,news,saas,forms,social}/"
echo "│   └── formats/{sifr,html,axtree,screenshots}/"
echo "├── examples/"
echo "├── results/{raw,analysis}/"
echo "├── scripts/"
echo "└── src/"
echo ""
echo "Next steps:"
echo "  1. Copy the files I gave you to their locations"
echo "  2. Run: npm install"
echo "  3. Run: npm run bench:quick"
