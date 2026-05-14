#!/bin/sh
# Build models.json from environment variables
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-https://ollama.com/v1}"
OLLAMA_MODEL="${OLLAMA_MODEL:-gemma4:31b}"
OLLAMA_API_KEY="${OLLAMA_API_KEY:-ollama}"

cat > /root/.pi/agent/models.json << EOF
{
  "providers": {
    "ollama": {
      "baseUrl": "$OLLAMA_BASE_URL",
      "api": "openai-completions",
      "apiKey": "$OLLAMA_API_KEY",
      "models": [
        { "id": "$OLLAMA_MODEL" }
      ]
    }
  }
}
EOF

cat > /root/.pi/agent/settings.json << EOF
{
  "defaultProvider": "ollama",
  "defaultModel": "$OLLAMA_MODEL"
}
EOF

mkdir -p /workspace/.pi/sessions

# Generate AGENTS.md dynamically: static instructions + registered tools
cat > /workspace/AGENTS.md << 'STATIC'
You are a coding agent working in a project workspace directory.

When asked to write code:
- Always use the `write` tool to create files directly in the workspace
- Always use the `edit` tool to modify existing files
- Never ask the user to copy and paste code — write it to files yourself
- Use `bash` to run commands, install dependencies, and test code
- Use `read` to examine existing files before modifying them

When creating a project:
- Create proper directory structure
- Include any necessary configuration files (e.g., requirements.txt, package.json, Cargo.toml)
- Write all source files directly to disk
- Install dependencies using bash (pip install, npm install, cargo build, etc.)

Testing and running:
- The user does NOT have direct shell access to this system
- Always run and test code yourself using bash before telling the user it's done
- If something fails, fix it and try again
- For web apps, start the server and report which port it's running on
- Available ports for user apps: check $BARK_PORT_START to $BARK_PORT_END

Handling large files (CSV, logs, datasets, etc.):
- Do NOT read entire large files and send them to the LLM — this is extremely slow
- Prefer registered tools over bash for file inspection when an appropriate tool is available
- When using bash and the full file content is not necessary, read only portions (e.g., `head -20`, column headers) rather than the entire file
- For deeper analysis, write a Python script that processes the file locally and prints a summary
- Only read small files (< 10KB) directly with the `read` tool

Available runtimes: Python 3, Node.js/npm, Dart, Flutter, Rust/Cargo, GCC/G++ (build-essential)
STATIC

# Append registered extension tools
if [ -d /root/.pi/agent/extensions ] && [ "$(ls /root/.pi/agent/extensions/*.ts 2>/dev/null)" ]; then
  echo "" >> /workspace/AGENTS.md
  echo "Registered extension tools (use these instead of bash when appropriate):" >> /workspace/AGENTS.md
  for ext in /root/.pi/agent/extensions/*.ts; do
    name=$(grep -E '^\s+name: "' "$ext" | head -1 | sed 's/.*name: "//;s/".*//')
    desc=$(grep -E '^\s+description: "' "$ext" | head -1 | sed 's/.*description: "//;s/".*//')
    if [ -n "$name" ] && [ -n "$desc" ]; then
      echo "- \`$name\`: $desc" >> /workspace/AGENTS.md
    fi
  done
fi

exec pi --mode rpc --session-dir /workspace/.pi/sessions
