# Day 2 - Agent Tools and Interoperability

## Core Idea

Agents become useful when they interact with external systems.

## MCP

Model Context Protocol

Purpose:

- Standardized tool access
- Tool discovery
- Tool interoperability

## A2A

Agent-to-Agent communication.

Agents may delegate work to other agents.

Example:

Tutor Agent
    ↓
OSCE Agent
    ↓
Evaluation Agent

## Interoperability

Avoid monolithic designs.

Prefer modular components.

## Application to SurgMentor

Potential MCP Tools:

- search_surgical_cases
- retrieve_osce_case
- evaluate_session
- generate_study_plan

Potential Agents:

- Tutor Agent
- OSCE Agent
- Evaluation Agent