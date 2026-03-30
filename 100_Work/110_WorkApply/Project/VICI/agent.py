"""LLM Orchestrator: tool use loop for the quant research agent.

The LLM acts as the orchestrator — it decides which tools to call and in what order.
Provider is configured via LLM_PROVIDER in .env ("gemini" or "anthropic").
"""

import json
import os
import tempfile
from datetime import date
from pathlib import Path

from tools.arxiv import search_papers, download_pdf
from tools.pdf import extract_text
from tools.report import save_report, save_paper_record, check_paper_exists

# ---------------------------------------------------------------------------
# Tool definitions (provider-agnostic schema)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "search_arxiv",
        "description": (
            "Search arXiv for academic papers on a given topic. "
            "Returns a list of papers with title, authors, abstract, arXiv ID, and PDF URL."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keywords, e.g. 'momentum strategy stock market'",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of papers to return",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "download_pdf",
        "description": "Download the full PDF of an arXiv paper by its arXiv ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "arxiv_id": {
                    "type": "string",
                    "description": "arXiv paper ID, e.g. '2301.00001'",
                },
            },
            "required": ["arxiv_id"],
        },
    },
    {
        "name": "extract_pdf_text",
        "description": (
            "Extract plain text from a downloaded PDF file. "
            "Use this after download_pdf to get the full paper content for analysis."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pdf_path": {
                    "type": "string",
                    "description": "Absolute file path to the downloaded PDF",
                },
            },
            "required": ["pdf_path"],
        },
    },
    {
        "name": "check_paper_exists",
        "description": (
            "Check if a paper already exists in the knowledge base by its arXiv ID. "
            "Call this before downloading a paper to avoid duplicate work. "
            "Returns existing metadata JSON if found, or 'not_found'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "arxiv_id": {
                    "type": "string",
                    "description": "arXiv paper ID, e.g. '2602.14670'",
                },
            },
            "required": ["arxiv_id"],
        },
    },
    {
        "name": "save_paper_record",
        "description": (
            "Save a structured JSON record for a single paper to the knowledge base. "
            "Call this once per paper after extracting all 13 dimensions. "
            "The record is stored in outputs/papers/{arxiv_id}.json and indexed in paper_index.json."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "record": {
                    "type": "object",
                    "description": "The full structured paper record following the knowledge base schema (must include 'arxiv_id')",
                },
            },
            "required": ["record"],
        },
    },
    {
        "name": "save_report",
        "description": "Save the final Markdown summary report to the outputs/reports directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Full Markdown report content",
                },
                "topic": {
                    "type": "string",
                    "description": "Research topic (used in filename)",
                },
            },
            "required": ["content", "topic"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool executor
# ---------------------------------------------------------------------------

def execute_tool(name: str, inputs: dict, tmp_dir: str) -> str:
    """Execute a tool call and return the result as a string."""
    if name == "search_arxiv":
        try:
            papers = search_papers(
                query=inputs["query"],
                max_results=inputs.get("max_results", 5),
            )
            return json.dumps(papers, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"Error searching arXiv: {e}"

    elif name == "download_pdf":
        try:
            pdf_path = download_pdf(arxiv_id=inputs["arxiv_id"], tmp_dir=tmp_dir)
            return pdf_path
        except Exception as e:
            return f"Error downloading PDF for {inputs['arxiv_id']}: {e}"

    elif name == "extract_pdf_text":
        text = extract_text(pdf_path=inputs["pdf_path"])
        return text

    elif name == "check_paper_exists":
        return check_paper_exists(arxiv_id=inputs["arxiv_id"])

    elif name == "save_paper_record":
        try:
            filepath = save_paper_record(record=inputs["record"])
            return filepath
        except Exception as e:
            return f"Error saving paper record: {e}"

    elif name == "save_report":
        filepath = save_report(
            content=inputs["content"],
            topic=inputs.get("topic", "research"),
        )
        return filepath

    else:
        return f"Error: unknown tool '{name}'"


# ---------------------------------------------------------------------------
# System prompt loader
# ---------------------------------------------------------------------------

def _load_system_prompt() -> str:
    prompts_dir = Path(__file__).parent / "prompts"
    system_md = (prompts_dir / "system.md").read_text(encoding="utf-8")
    report_format_md = (prompts_dir / "report_format.md").read_text(encoding="utf-8")
    return f"{system_md}\n\n## Report Format Template\n\n{report_format_md}"


# ---------------------------------------------------------------------------
# Provider adapters
# ---------------------------------------------------------------------------

def _run_anthropic(topic: str, max_papers: int, system_prompt: str, tmp_dir: str) -> str:
    """Tool use loop using Anthropic Claude."""
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Convert our schema to Anthropic's tool format
    tools = [
        {
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["input_schema"],
        }
        for t in TOOLS
    ]

    messages = [
        {
            "role": "user",
            "content": (
                f"Today's date is {date.today().isoformat()}. "
                f"Research the following quantitative strategy topic: '{topic}'. "
                f"Analyze up to {max_papers} papers. "
                "Follow your workflow: search → download PDFs → extract text → analyze → save report."
            ),
        }
    ]

    report_path = None

    while True:
        response = client.messages.create(
            model=os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-5"),
            max_tokens=8096,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )

        # Append assistant response to message history
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  → calling tool: {block.name}({list(block.input.keys())})")
                    result = execute_tool(block.name, block.input, tmp_dir)

                    if block.name == "save_report":
                        report_path = result
                        print(f"  ✓ report saved: {result}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "user", "content": tool_results})

    return report_path


def _run_gemini(topic: str, max_papers: int, system_prompt: str, tmp_dir: str) -> str:
    """Tool use loop using Google Gemini."""
    import google.genai as genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    model_id = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-preview-04-17")

    # Convert our schema to Gemini's function declaration format
    def _to_gemini_schema(schema: dict) -> dict:
        """Recursively convert JSON Schema to Gemini-compatible format."""
        result = {}
        if "type" in schema:
            result["type"] = schema["type"].upper()
        if "description" in schema:
            result["description"] = schema["description"]
        if "properties" in schema:
            result["properties"] = {
                k: _to_gemini_schema(v) for k, v in schema["properties"].items()
            }
        if "required" in schema:
            result["required"] = schema["required"]
        if "items" in schema:
            result["items"] = _to_gemini_schema(schema["items"])
        return result

    function_declarations = [
        types.FunctionDeclaration(
            name=t["name"],
            description=t["description"],
            parameters=_to_gemini_schema(t["input_schema"]),
        )
        for t in TOOLS
    ]

    gemini_tools = [types.Tool(function_declarations=function_declarations)]

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=gemini_tools,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )

    # Build initial message
    user_message = (
        f"Today's date is {date.today().isoformat()}. "
        f"Research the following quantitative strategy topic: '{topic}'. "
        f"Analyze up to {max_papers} papers. "
        "Follow your workflow: search → download PDFs → extract text → analyze → save report."
    )

    contents = [types.Content(role="user", parts=[types.Part(text=user_message)])]
    report_path = None
    empty_response_count = 0
    MAX_EMPTY_RESPONSES = 5

    while True:
        response = client.models.generate_content(
            model=model_id,
            contents=contents,
            config=config,
        )

        candidate = response.candidates[0]

        # Guard against empty content (e.g. safety filter or context too long)
        if candidate.content is None or not candidate.content.parts:
            empty_response_count += 1
            if empty_response_count >= MAX_EMPTY_RESPONSES:
                print(f"  ✗ model returned empty response {MAX_EMPTY_RESPONSES} times, stopping.")
                break
            print(f"  ⚠ empty response from model ({empty_response_count}/{MAX_EMPTY_RESPONSES}), attempting recovery...")
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part(text="Please continue with the next step in your workflow.")],
                )
            )
            continue

        empty_response_count = 0  # reset on successful response

        contents.append(candidate.content)

        # Check if there are function calls
        function_calls = [
            part.function_call
            for part in candidate.content.parts
            if part.function_call is not None
        ]

        if not function_calls:
            # No more tool calls — LLM is done
            break

        # Execute all function calls and collect results
        function_responses = []
        for fc in function_calls:
            tool_inputs = dict(fc.args)
            print(f"  → calling tool: {fc.name}({list(tool_inputs.keys())})")
            result = execute_tool(fc.name, tool_inputs, tmp_dir)

            if fc.name == "save_report":
                report_path = result
                print(f"  ✓ report saved: {result}")

            function_responses.append(
                types.Part.from_function_response(
                    name=fc.name,
                    response={"result": result},
                )
            )

        contents.append(
            types.Content(role="user", parts=function_responses)
        )

    return report_path


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(topic: str, max_papers: int = 5) -> str:
    """Run the research agent for a given topic.

    Args:
        topic: Quantitative strategy topic to research.
        max_papers: Maximum number of papers to analyze.

    Returns:
        Path to the saved report file.

    Raises:
        ValueError: If LLM_PROVIDER is not set or unsupported.
    """
    provider = os.environ.get("LLM_PROVIDER", "").lower()
    if not provider:
        raise ValueError(
            "LLM_PROVIDER not set in .env. Set it to 'gemini' or 'anthropic'."
        )

    system_prompt = _load_system_prompt()
    tmp_dir = tempfile.mkdtemp(prefix="arxiv_pdfs_")

    print(f"[agent] provider: {provider}")
    print(f"[agent] topic: {topic}")
    print(f"[agent] max papers: {max_papers}")
    print(f"[agent] tmp dir: {tmp_dir}")
    print()

    if provider == "anthropic":
        return _run_anthropic(topic, max_papers, system_prompt, tmp_dir)
    elif provider == "gemini":
        return _run_gemini(topic, max_papers, system_prompt, tmp_dir)
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: '{provider}'. Use 'gemini' or 'anthropic'.")
