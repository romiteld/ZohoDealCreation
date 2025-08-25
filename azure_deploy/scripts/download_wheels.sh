#!/bin/bash
# Download pre-built wheels for faster installation

cd wheels

# Download wheels for critical packages
pip download --only-binary :all: --platform linux_x86_64 --python-version 312     numpy==1.26.2     psycopg2-binary==2.9.9     lxml==4.9.3     2>/dev/null || true

echo "✓ Wheels downloaded (if available)"
