"""
Verification script for Dynamic 3D Construction Platform
Tests server status, page downloads, asset presence, and code integrity.
"""
import urllib.request
import json
import re

BASE_URL = "http://127.0.0.1:8080"

def test_page(path):
    url = f"{BASE_URL}/{path}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200, f"Failed: {path} status {resp.status}"
        content = resp.read().decode('utf-8')
        return content

print("1. Testing index.html availability...")
index_html = test_page("index.html")
print("   - index.html loaded successfully!")

print("2. Checking CodeMirror and Studio UI integration in index.html...")
assert "codemirror.min.js" in index_html, "Missing CodeMirror JS in index.html"
assert "codemirror.min.css" in index_html, "Missing CodeMirror CSS in index.html"
assert "dracula.min.css" in index_html, "Missing Dracula theme in index.html"
assert "CodeEditorPanel" in index_html, "Missing CodeEditorPanel import"
assert "DesignBrowser" in index_html, "Missing DesignBrowser import"
assert "DesignService" in index_html, "Missing DesignService import"
assert "initDesignStudio()" in index_html, "Missing initDesignStudio() call"
print("   - CodeMirror and Studio assets successfully integrated!")

print("3. Testing other workbench pages...")
inspector_html = test_page("inspector.html")
manufacturing_html = test_page("manufacturing.html")
validation_html = test_page("validation.html")
guide_html = test_page("guide.html")
print("   - All 4 workbenches returned HTTP 200!")

print("4. Testing JavaScript module files...")
js_files = [
    "js/core/firebase.js",
    "js/services/firebase-designs.js",
    "js/services/design-parser.js",
    "js/models/registry.js",
    "js/models/templates.js",
    "js/ui/code-editor-panel.js",
    "js/ui/design-browser.js",
    "js/ui/nav.js"
]

for f in js_files:
    content = test_page(f)
    assert len(content) > 50, f"File {f} is suspiciously small"
    print(f"   - {f} loaded ({len(content)} bytes)")

print("5. Checking documentation in docs/...")
import os
docs = os.listdir("docs")
expected_docs = [
    "architecture.md",
    "design-data-schema.md",
    "javascript-api.md",
    "firebase-schema.md",
    "validation.md",
    "dynamic-design-workflow.md",
    "ai-design-generation.md"
]
for doc in expected_docs:
    assert doc in docs, f"Missing documentation file docs/{doc}"
    size = os.path.getsize(os.path.join("docs", doc))
    assert size > 200, f"Doc {doc} is too short"
    print(f"   - docs/{doc} verified ({size} bytes)")

print("\nALL VERIFICATION CHECKS PASSED SUCCESSFULLY!")
