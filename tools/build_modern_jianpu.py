import re

# Read current file to preserve core assets and logic
with open('/Users/oneriver/Downloads/jianpu_studio.html', 'r', encoding='utf-8') as f:
    orig = f.read()

print("Original length:", len(orig))
