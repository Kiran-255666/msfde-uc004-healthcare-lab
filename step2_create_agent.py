#!/usr/bin/env python3
"""LAB PART 2 - build the grounded agent.

Two things happen here:

  1. A project connection is created so the agent can call your knowledge base with the
     project's managed identity (no keys).
  2. An agent version is created with the knowledge base attached as an MCP tool, your
     instructions, and a strict JSON response contract.

Run:
    python step2_create_agent.py            # create connection + agent
    python step2_create_agent.py --ask "..." # ask your agent one question

Fill in the TODOs. Your agent must satisfy CHS-POL-001: ground every answer, cite it,
label confidence, and defer clinical decisions to a clinician.
"""
from __future__ import annotations

import argparse
import json

import requests
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MCPTool, PromptAgentDefinition
from azure.identity import AzureCliCredential

import lab_config as cfg

# --------------------------------------------------------------------- instructions

# TODO 1: write the system instructions for your agent.
#
# The assistant must, per the Contoso policies in the corpus:
#   - call the knowledge base tool for every clinical/policy question, and answer ONLY
#     from what it returns (never from its own medical knowledge);
#   - say plainly when the corpus does not cover the question;
#   - cite the documents it used, and never invent a citation;
#   - label confidence High / Moderate / Low (CHS-POL-001 section 5);
#   - refuse and defer anything patient-specific: diagnosis, treatment changes, doses,
#     paediatric / pregnant / unstable patients, result interpretation, end-of-life
#     (CHS-POL-001 section 4), naming the escalation route from CHS-POL-002;
#   - never repeat back patient identifiers (CHS-POL-004 section 2);
#   - set requires_clinician_review whenever it defers, is Low confidence, or cannot cite.
#
# Tip: be explicit and testable. Part 4 will score these behaviours.
INSTRUCTIONS = """
TODO: write your agent instructions here.
""".strip()

# --------------------------------------------------------------------- response contract (given)

RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answer", "confidence", "citations", "requires_clinician_review", "review_reason"],
    "properties": {
        "answer": {"type": "string"},
        "confidence": {"type": "string", "enum": ["High", "Moderate", "Low"]},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["document", "detail"],
                "properties": {"document": {"type": "string"}, "detail": {"type": "string"}},
            },
        },
        "requires_clinician_review": {"type": "boolean"},
        "review_reason": {"type": "string"},
    },
}


def create_connection() -> None:
    """Let the agent authenticate to the knowledge base as the project's managed identity."""
    access_token = AzureCliCredential().get_token("https://management.azure.com/.default").token
    headers = {"Authorization": f"Bearer {access_token}"}
    url = (f"https://management.azure.com{cfg.PROJECT_RESOURCE_ID}/connections/"
           f"{cfg.CONNECTION_NAME}?api-version=2025-10-01-preview")

    # GOTCHA: 'audience' is only applied when a connection is CREATED. Updating an existing
    # connection keeps the old value and the agent fails at run time with
    # "Failed to fetch access token ... Missing required query parameter 'audience'".
    requests.delete(url, headers=headers, timeout=60)

    response = requests.put(url, headers=headers, timeout=60, json={
        "name": cfg.CONNECTION_NAME,
        "type": "Microsoft.MachineLearningServices/workspaces/connections",
        "properties": {
            "authType": "ProjectManagedIdentity",
            "category": "RemoteTool",
            "target": cfg.KB_MCP_URL,
            "isSharedToAll": True,
            "audience": "https://search.azure.com/",
            "metadata": {"ApiType": "Azure"},
        },
    })
    response.raise_for_status()
    print(f"connection ready: {cfg.CONNECTION_NAME}")


def create_agent() -> None:
    if "TODO" in INSTRUCTIONS:
        raise SystemExit("Write your instructions in INSTRUCTIONS (TODO 1) before creating the agent.")

    # TODO 2: attach your knowledge base as an MCP tool.
    #   server_label          - a short name for the tool
    #   server_url            - cfg.KB_MCP_URL
    #   project_connection_id - cfg.CONNECTION_NAME (this is what authenticates the call)
    #   allowed_tools         - the knowledge base exposes exactly one: "knowledge_base_retrieve"
    #   require_approval      - "never" for this lab (the oversight step is human review of answers)
    knowledge_tool = MCPTool(
        server_label="approved_corpus",
        server_url="TODO",
        project_connection_id="TODO",
        allowed_tools=["TODO"],
        require_approval="TODO",
    )

    project = AIProjectClient(endpoint=cfg.PROJECT_ENDPOINT, credential=AzureCliCredential())
    agent = project.agents.create_version(
        agent_name=cfg.AGENT_NAME,
        definition=PromptAgentDefinition(
            model=cfg.CHAT_DEPLOYMENT,
            instructions=INSTRUCTIONS,
            tools=[knowledge_tool],
            # TODO 3: the agent must not answer clinical questions without retrieving first.
            # Which tool_choice enforces that? ("auto" lets it skip the tool.)
            tool_choice="TODO",
            text={"format": {"type": "json_schema", "name": "clinical_answer",
                             "strict": True, "schema": RESPONSE_SCHEMA}},
        ),
    )
    print(f"agent ready: {agent.name} (version {getattr(agent, 'version', '?')})")


def ask(question: str) -> None:
    from ask_agent import ask as run          # noqa: PLC0415 - keeps the import local to this path
    result = run(question)
    print(json.dumps({k: v for k, v in result.items() if not k.startswith("_")}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ask", metavar="QUESTION", help="ask your agent a question")
    args = parser.parse_args()

    if args.ask:
        ask(args.ask)
        return

    create_connection()
    create_agent()
    print("\nTry it:  python step2_create_agent.py --ask \"What does the sepsis pathway require in the first hour?\"")


if __name__ == "__main__":
    main()
