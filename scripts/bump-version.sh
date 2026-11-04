#!/bin/sh
# Versiyani bir vaqtda uch joyda yangilaydi: VERSION, frontend/package.json, backend/app/__init__.py
# Ishlatish: scripts/bump-version.sh 1.6.0   (CHANGELOG.md ga yozuvni o'zingiz qo'shasiz)
set -e
[ -n "$1" ] || { echo "Ishlatish: $0 X.Y.Z" >&2; exit 1; }
cd "$(dirname "$0")/.."
echo "$1" > VERSION
sed -i.bak -E "s/^(  \"version\": )\"[^\"]+\"/\1\"$1\"/" frontend/package.json && rm frontend/package.json.bak
sed -i.bak -E "s/^__version__ = \".*\"/__version__ = \"$1\"/" backend/app/__init__.py && rm backend/app/__init__.py.bak
grep -m1 '"version"' frontend/package.json; grep '^__version__' backend/app/__init__.py; cat VERSION
