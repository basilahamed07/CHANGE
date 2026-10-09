@echo off
title Basil Claude Code - AgentRouter

REM ================================
REM AgentRouter configuration
REM Only replace the API key below
REM ================================
set "ANTHROPIC_BASE_URL=https://agentrouter.org"
set "ANTHROPIC_AUTH_TOKEN=sk-3bDooPsb4oS1SuPRmg3bGBcfnlbgKQeEwBxud14l6FeQS8tL"
set "ANTHROPIC_MODEL=deepseek-v4-flash"
set "ANTHROPIC_deepseek_MODEL=deepseek-v4-flash"

REM Start Claude Code
"C:\Users\basilahamed.h\AppData\Roaming\npm\claude.cmd" %* -c
