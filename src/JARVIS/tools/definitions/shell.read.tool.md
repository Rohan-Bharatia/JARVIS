---
name: shell.read
server: shell
timeout: 30
sudo: false
side_effects: false
requires_approval: false
arguments:
  path:
    type: string
    required: true
    description: Path of the file to read, relative to the workspace.
  max_bytes:
    type: integer
    required: false
    description: Maximum number of bytes to read (default 65536).
---
Read a file from the JARVIS workspace and return its contents as text.
