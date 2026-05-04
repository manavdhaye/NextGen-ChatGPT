# #!/bin/bash

# # Project root

# PROJECT_NAME="nextgen-chatgpt"

# echo "Creating project: $PROJECT_NAME"

# # Create root folder

# mkdir -p $PROJECT_NAME
# cd $PROJECT_NAME

# Root files

touch app.py config.py requirements.txt .env

# Templates & static

mkdir -p templates static
touch templates/index.html
touch static/style.css static/script.js

# API

mkdir -p api
touch api/chat.py

# Core

mkdir -p core
touch core/supervisor.py core/workflow.py core/state.py core/llm_setup.py core/rag_manager.py

# Agents

mkdir -p agents
touch agents/chat_agent.py 
agents/code_agent.py 
agents/research_agent.py 
agents/doc_agent.py 
agents/multimodal_agent.py 
agents/ppt_agent.py

# Tools

mkdir -p tools
touch tools/all_tools.py tools/tool_manager.py
# RAG

# Database

mkdir -p database
touch database/threads.json database/chatbot.db

# Utils

mkdir -p utils
touch utils/thread.py utils/helpers.py utils/multimodal_processor.py utils/video_processor.py utils/logger.py utils/exception.py

# Uploads folder

mkdir -p uploads

mkdir -p workflows
touch workflows/code_workflow.py workflows/docx_workflow.py workflows/ppt_workflow.py workflows/research_workflow.py

echo "✅ Project structure created successfully!"
