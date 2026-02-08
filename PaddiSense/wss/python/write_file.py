#!/usr/bin/env python3
"""Simple file writer helper for WSS.
Accepts base64-encoded content to avoid shell escaping issues.

Usage: python3 write_file.py /path/to/file <base64_content>
"""
import base64
import sys
from pathlib import Path

def main():
    if len(sys.argv) < 3:
        print("Usage: write_file.py <file_path> <base64_content>", file=sys.stderr)
        return 1

    file_path = Path(sys.argv[1])
    b64_content = sys.argv[2]

    try:
        # Decode base64 content
        content = base64.b64decode(b64_content).decode('utf-8')
    except Exception as e:
        print(f"ERROR: Failed to decode base64: {e}", file=sys.stderr)
        return 1

    # Ensure parent directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Write content
    file_path.write_text(content, encoding='utf-8')
    print(f"OK:{file_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
