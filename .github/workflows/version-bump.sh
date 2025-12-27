#!/bin/bash
# Helper script to manually bump version
# Usage: ./version-bump.sh [major|minor|patch]

set -e

VERSION_FILE="src/__init__.py"
CURRENT_VERSION=$(grep "__version__" "$VERSION_FILE" | sed "s/.*= ['\"]\(.*\)['\"]/\1/")

if [ -z "$CURRENT_VERSION" ]; then
    CURRENT_VERSION="0.0.0"
fi

IFS='.' read -ra ADDR <<< "$CURRENT_VERSION"
MAJOR=${ADDR[0]}
MINOR=${ADDR[1]}
PATCH=${ADDR[2]}

BUMP_TYPE=${1:-patch}

case $BUMP_TYPE in
    major)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        ;;
    minor)
        MINOR=$((MINOR + 1))
        PATCH=0
        ;;
    patch)
        PATCH=$((PATCH + 1))
        ;;
    *)
        echo "Invalid bump type: $BUMP_TYPE"
        echo "Usage: $0 [major|minor|patch]"
        exit 1
        ;;
esac

NEW_VERSION="$MAJOR.$MINOR.$PATCH"

echo "Current version: $CURRENT_VERSION"
echo "New version: $NEW_VERSION"

sed -i.bak "s/__version__ = \".*\"/__version__ = \"$NEW_VERSION\"/" "$VERSION_FILE"
rm -f "${VERSION_FILE}.bak"

echo "✅ Version updated to $NEW_VERSION in $VERSION_FILE"

