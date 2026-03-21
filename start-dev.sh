#!/bin/bash
export PATH="$HOME/.nvm/versions/node/v22.16.0/bin:$PATH"
cd "$(dirname "$0")"
npx vite --port 5173
