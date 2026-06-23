# surgmentor/mcp/server.py
"""
SurgMentor MCP Server — STRETCH GOAL (Phase 8).

Exposes surgical education tools as MCP-compliant endpoints so that
any MCP-compatible agent can discover and invoke them (Day 2 concept).

Only active when USE_MCP=true in .env.
The AgentController falls back to direct function calls when USE_MCP=false,
ensuring the demo works even if the MCP process is not running.

MCP tools exposed:
  search_surgical_cases    — query ChromaDB for relevant cases
  get_case_by_id           — retrieve a specific case by ID
  evaluate_osce_session    — score a completed session
  get_student_profile      — return student weak_areas and score history

Phase 8 (stretch) implementation target.
"""

# TODO (Phase 8): Define MCP tool schemas (JSON Schema for each tool)
# TODO (Phase 8): Implement MCP server using mcp library
# TODO (Phase 8): search_surgical_cases handler → retrieval_tool.search_vector_store()
# TODO (Phase 8): get_case_by_id handler → retrieval_tool.get_case_by_id()
# TODO (Phase 8): evaluate_osce_session handler → EvaluationSkill.run()
# TODO (Phase 8): get_student_profile handler → db_store.get_student_stats()
# TODO (Phase 8): Entry point: run_mcp_server() starts server on localhost
