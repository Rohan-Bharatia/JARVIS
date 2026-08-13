---
name: shell.run
server: shell
timeout: 60
sudo: false
side_effects: true
requires_approval: true
arguments:
  command:
    type: string
    required: true
    description: The shell command to run, as a single string.
  cwd:
    type: string
    required: false
    description: Working directory to run the command in.
---
Run a shell command and return its stdout and stderr output. The command runs in
the JARVIS workspace directory. Prefer reading files instead of running commands
when possible. Every command is a state-changing action and requires approval.
