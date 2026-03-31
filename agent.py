"""LLM Orchestrator: tool use loop for the quant research agent.

The LLM acts as the orchestrator — it decides which tools to call and in what order.
Provider is configured via LLM_PROVIDER in .env ("gemini" or "anthropic").
"""

import json
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Optional

from tools.arxiv import download_pdf, search_external_evidence, search_papers
from tools.pdf import extract_text
from tools.qa import (
    build_fallback_answer,
    build_memory,
    format_evidence_for_prompt,
    normalize_external_evidence,
    retrieve_local_evidence,
    should_search_externally,
)
from tools.relevance import has_explicit_market_constraint, parse_query_constraints
from tools.report import save_report, save_paper_record, check_paper_exists
from tools.schema_audit import (
    audit_paper_record as run_schema_audit,
    cache_search_metadata,
    format_audit_summary,
    get_last_saved_audit,
    reset_runtime_state,
)

MAX_RESEARCH_TURNS = 20
MAX_CONSECUTIVE_TOOL_FAILURES = 3
MAX_CONSECUTIVE_MODEL_ERRORS = 3

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
        "name": "audit_paper_record",
        "description": (
            "Audit a structured paper record before saving it. "
            "Applies deterministic autofill for metadata, returns issues, and indicates whether one LLM repair pass is still needed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "record": {
                    "type": "object",
                    "description": "The full structured paper record to validate and autofill before saving.",
                },
            },
            "required": ["record"],
        },
    },
    {
        "name": "save_paper_record",
        "description": (
            "Save a structured JSON record for a single paper to the knowledge base. "
            "Call this once per paper after audit_paper_record. "
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
            cache_search_metadata(papers)
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
        try:
            text = extract_text(pdf_path=inputs["pdf_path"])
            return text
        except Exception as e:
            return f"Error extracting PDF text: {e}"

    elif name == "audit_paper_record":
        try:
            result = run_schema_audit(
                inputs["record"],
                apply_autofill=True,
                increment_call_count=True,
            )
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"Error auditing paper record: {e}"

    elif name == "check_paper_exists":
        return check_paper_exists(arxiv_id=inputs["arxiv_id"])

    elif name == "save_paper_record":
        try:
            filepath = save_paper_record(record=inputs["record"])
            arxiv_id = inputs["record"].get("arxiv_id", "")
            latest_audit = get_last_saved_audit(arxiv_id)
            if latest_audit:
                _log(f"  ↳ audit summary: {format_audit_summary(latest_audit)}")
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


def _extract_gemini_text_parts(candidate: Any) -> str:
    """Return concatenated text parts from a Gemini candidate content block."""
    if candidate is None or getattr(candidate, "content", None) is None:
        return ""
    texts = []
    non_text_parts = []
    for part in candidate.content.parts or []:
        text = getattr(part, "text", None)
        if text:
            texts.append(text)
            continue
        if getattr(part, "function_call", None) is not None:
            continue
        if getattr(part, "function_response", None) is not None:
            continue
        part_kind = getattr(part, "thought_signature", None)
        non_text_parts.append("thought_signature" if part_kind else type(part).__name__)
    if non_text_parts:
        _log(f"  ⚠ non-text parts in Gemini response ignored: {non_text_parts}")
    return "\n".join(texts).strip()


def _load_provider() -> str:
    provider = os.environ.get("LLM_PROVIDER", "").lower()
    if not provider:
        raise ValueError(
            "LLM_PROVIDER not set in .env. Set it to 'gemini' or 'anthropic'."
        )
    if provider not in {"gemini", "anthropic"}:
        raise ValueError(f"Unsupported LLM_PROVIDER: '{provider}'. Use 'gemini' or 'anthropic'.")
    return provider


def _result_preview(result: Any, limit: int = 160) -> str:
    text = str(result).replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _log(message: str) -> None:
    print(message, flush=True)


def _tool_result_status(name: str, result: str) -> str:
    if isinstance(result, str) and result.startswith("Error "):
        return "error"
    if name == "search_arxiv":
        try:
            payload = json.loads(result)
        except Exception:
            return "success"
        if isinstance(payload, list) and not payload:
            return "empty"
    if name == "extract_pdf_text" and (not isinstance(result, str) or not result.strip()):
        return "empty"
    if name == "save_report" and isinstance(result, str) and result.strip():
        return "saved"
    return "success"


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
                "Follow your workflow: search → download PDFs → extract text → build record → audit → save report."
            ),
        }
    ]

    report_path = None
    turn_count = 0
    consecutive_tool_failures = 0

    while True:
        turn_count += 1
        if turn_count > MAX_RESEARCH_TURNS:
            _log(f"  ✗ reached max research turns ({MAX_RESEARCH_TURNS}), stopping.")
            break
        _log(f"[agent] anthropic turn {turn_count}: waiting for model response...")
        response = client.messages.create(
            model=os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-5"),
            max_tokens=8096,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )
        _log(f"[agent] anthropic turn {turn_count}: stop_reason={response.stop_reason}")

        # Append assistant response to message history
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            statuses = []
            for block in response.content:
                if block.type == "tool_use":
                    _log(f"  → calling tool: {block.name}({list(block.input.keys())})")
                    result = execute_tool(block.name, block.input, tmp_dir)
                    status = _tool_result_status(block.name, result)
                    statuses.append(status)
                    _log(f"  ↳ {block.name} status={status}: {_result_preview(result)}")

                    if block.name == "save_report":
                        report_path = result
                        _log(f"  ✓ report saved: {result}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "user", "content": tool_results})
            if statuses and all(status in {"error", "empty"} for status in statuses):
                consecutive_tool_failures += 1
            else:
                consecutive_tool_failures = 0
            if consecutive_tool_failures >= MAX_CONSECUTIVE_TOOL_FAILURES:
                _log(f"  ✗ tool calls made no progress {MAX_CONSECUTIVE_TOOL_FAILURES} turns in a row, stopping.")
                break

    return report_path


def _run_gemini(topic: str, max_papers: int, system_prompt: str, tmp_dir: str) -> str:
    """Tool use loop using Google Gemini."""
    import google.genai as genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    model_id = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")

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
        "Follow your workflow: search → download PDFs → extract text → build record → audit → save report."
    )

    contents = [types.Content(role="user", parts=[types.Part(text=user_message)])]
    report_path = None
    empty_response_count = 0
    MAX_EMPTY_RESPONSES = 5
    turn_count = 0
    consecutive_tool_failures = 0
    consecutive_model_errors = 0

    while True:
        turn_count += 1
        if turn_count > MAX_RESEARCH_TURNS:
            _log(f"  ✗ reached max research turns ({MAX_RESEARCH_TURNS}), stopping.")
            break
        _log(f"[agent] gemini turn {turn_count}: waiting for model response...")
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=contents,
                config=config,
            )
        except Exception as e:
            consecutive_model_errors += 1
            _log(f"  ⚠ model request failed ({consecutive_model_errors}/{MAX_CONSECUTIVE_MODEL_ERRORS}): {e}")
            if consecutive_model_errors >= MAX_CONSECUTIVE_MODEL_ERRORS:
                _log(f"  ✗ model request failed {MAX_CONSECUTIVE_MODEL_ERRORS} times in a row, stopping.")
                break
            continue
        consecutive_model_errors = 0
        candidates = getattr(response, "candidates", None) or []
        candidate = candidates[0] if candidates else None

        # Guard against empty content (e.g. safety filter or context too long)
        if candidate is None or candidate.content is None or not candidate.content.parts:
            empty_response_count += 1
            if empty_response_count >= MAX_EMPTY_RESPONSES:
                _log(f"  ✗ model returned empty response {MAX_EMPTY_RESPONSES} times, stopping.")
                break
            _log(f"  ⚠ empty response from model ({empty_response_count}/{MAX_EMPTY_RESPONSES}), attempting recovery...")
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
            text_preview = _result_preview(_extract_gemini_text_parts(candidate))
            if text_preview:
                _log(f"[agent] gemini turn {turn_count}: model finished with text: {text_preview}")
            break

        # Execute all function calls and collect results
        function_responses = []
        statuses = []
        for fc in function_calls:
            tool_inputs = dict(fc.args)
            _log(f"  → calling tool: {fc.name}({list(tool_inputs.keys())})")
            result = execute_tool(fc.name, tool_inputs, tmp_dir)
            status = _tool_result_status(fc.name, result)
            statuses.append(status)
            _log(f"  ↳ {fc.name} status={status}: {_result_preview(result)}")

            if fc.name == "save_report":
                report_path = result
                _log(f"  ✓ report saved: {result}")

            function_responses.append(
                types.Part.from_function_response(
                    name=fc.name,
                    response={"result": result},
                )
            )

        contents.append(
            types.Content(role="user", parts=function_responses)
        )
        if statuses and all(status in {"error", "empty"} for status in statuses):
            consecutive_tool_failures += 1
        else:
            consecutive_tool_failures = 0
        if consecutive_tool_failures >= MAX_CONSECUTIVE_TOOL_FAILURES:
            _log(f"  ✗ tool calls made no progress {MAX_CONSECUTIVE_TOOL_FAILURES} turns in a row, stopping.")
            break

    return report_path


def _build_qa_prompt(question: str, memory: dict[str, Any], local_evidence: list[Any], external_evidence: list[Any]) -> str:
    evidence_json = format_evidence_for_prompt(local_evidence, external_evidence)
    return (
        "You are a quantitative finance research assistant.\n"
        "Answer the user's question using the supplied evidence only.\n"
        "Rules:\n"
        "- Prefer verified_knowledge_base evidence.\n"
        "- Use latest_external_supplement only when local evidence is insufficient, and label it clearly.\n"
        "- Give the conclusion first, then support it with citations.\n"
        "- Do not fabricate metrics, markets, or causal claims.\n"
        "- If evidence is weak, say so explicitly.\n"
        "- Return ONLY valid JSON with keys: answer, citations, evidence_basis, freshness_note, confidence.\n"
        "- citations must be an array of objects with keys: title, source_type, locator, arxiv_id, url, detail. Omit keys that do not apply.\n\n"
        f"Session memory:\n{json.dumps(memory, ensure_ascii=False, indent=2)}\n\n"
        f"User question:\n{question}\n\n"
        f"Evidence:\n{evidence_json}\n"
    )


def _parse_answer_payload(text: str) -> Optional[dict[str, Any]]:
    raw = (text or "").strip()
    if not raw:
        return None
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1] if raw.count("```") >= 2 else raw
        raw = raw.replace("json\n", "", 1).strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    required = {"answer", "citations", "evidence_basis", "freshness_note", "confidence"}
    if not isinstance(payload, dict) or not required.issubset(payload):
        return None
    if not isinstance(payload.get("citations"), list):
        payload["citations"] = []
    return payload


def _build_stable_answer_metadata(
    local_evidence: list[Any],
    external_evidence: list[Any],
) -> dict[str, Any]:
    has_local = bool(local_evidence)
    has_external = bool(external_evidence)
    eligible_local = [item for item in local_evidence if item.primary_evidence_eligible]
    market_matched_local = [item for item in eligible_local if getattr(item, "market_match", False)]
    citation_candidates = market_matched_local or eligible_local or local_evidence
    top_local_score = citation_candidates[0].score if citation_candidates else 0
    local_cutoff = max(3.0, top_local_score - 2.0) if top_local_score else 0.0
    stable_local = [
        item
        for item in citation_candidates
        if item.score >= local_cutoff
    ]
    if stable_local:
        top_score = stable_local[0].score
        stable_local = [
            item
            for index, item in enumerate(stable_local)
            if index == 0 or item.score >= top_score * 0.8
        ]
    stable_external = external_evidence[:2]
    citations = [item.to_citation() for item in (stable_local[:3] + stable_external)[:4]]

    if has_local and has_external:
        evidence_basis = (
            "Used verified knowledge-base records first and added approved external supplements only where local evidence was thin."
        )
        freshness_note = (
            "Answer is grounded in audited local records and includes approved external supplements that are not yet fully ingested into the local knowledge base."
        )
        confidence = "medium"
    elif has_local:
        evidence_basis = "Used verified knowledge-base records first."
        freshness_note = "Answer grounded primarily in audited local records."
        confidence = "high" if eligible_local else "medium"
    elif has_external:
        evidence_basis = "Used approved external supplement because local evidence was insufficient."
        freshness_note = "Answer is based on approved external supplements that are not yet fully ingested into the local knowledge base."
        confidence = "low"
    else:
        evidence_basis = "No sufficient verified evidence was available."
        freshness_note = "No supporting evidence was available in the local knowledge base or approved external supplements."
        confidence = "low"

    return {
        "citations": citations,
        "evidence_basis": evidence_basis,
        "freshness_note": freshness_note,
        "confidence": confidence,
    }


def _finalize_answer_payload(
    question: str,
    payload: Optional[dict[str, Any]],
    local_evidence: list[Any],
    external_evidence: list[Any],
) -> dict[str, Any]:
    constraints = parse_query_constraints(question)
    has_market_constraint = has_explicit_market_constraint(constraints)
    has_market_matched_primary = any(
        item.primary_evidence_eligible and getattr(item, "market_match", False)
        for item in local_evidence
    )
    if (
        payload is None
        or not isinstance(payload.get("answer"), str)
        or not payload["answer"].strip()
        or (has_market_constraint and not has_market_matched_primary and not external_evidence)
    ):
        payload = build_fallback_answer(question, local_evidence, external_evidence)
    stable = _build_stable_answer_metadata(local_evidence, external_evidence)
    payload["answer"] = payload["answer"].strip()
    payload["citations"] = stable["citations"]
    payload["evidence_basis"] = stable["evidence_basis"]
    payload["freshness_note"] = stable["freshness_note"]
    payload["confidence"] = stable["confidence"]
    return payload


def _generate_answer_with_anthropic(
    question: str,
    memory: dict[str, Any],
    local_evidence: list[Any],
    external_evidence: list[Any],
) -> Optional[dict[str, Any]]:
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    prompt = _build_qa_prompt(question, memory, local_evidence, external_evidence)
    response = client.messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-5"),
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    text_parts = []
    for block in response.content:
        if getattr(block, "type", "") == "text":
            text_parts.append(block.text)
    return _parse_answer_payload("\n".join(text_parts))


def _generate_answer_with_gemini(
    question: str,
    memory: dict[str, Any],
    local_evidence: list[Any],
    external_evidence: list[Any],
) -> Optional[dict[str, Any]]:
    import google.genai as genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    model_id = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
    prompt = _build_qa_prompt(question, memory, local_evidence, external_evidence)
    response = client.models.generate_content(
        model=model_id,
        contents=prompt,
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    candidates = getattr(response, "candidates", None) or []
    candidate = candidates[0] if candidates else None
    return _parse_answer_payload(_extract_gemini_text_parts(candidate))


def _generate_answer_payload(
    question: str,
    memory: dict[str, Any],
    local_evidence: list[Any],
    external_evidence: list[Any],
) -> dict[str, Any]:
    provider = _load_provider()
    try:
        if provider == "anthropic":
            payload = _generate_answer_with_anthropic(question, memory, local_evidence, external_evidence)
        else:
            payload = _generate_answer_with_gemini(question, memory, local_evidence, external_evidence)
    except Exception as e:
        print(f"  ⚠ QA generation failed, using fallback answer: {e}")
        payload = None

    return _finalize_answer_payload(question, payload, local_evidence, external_evidence)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def research(topic: str, max_papers: int = 5) -> str:
    """Run the deep research workflow for a given topic.

    Args:
        topic: Quantitative strategy topic to research.
        max_papers: Maximum number of papers to analyze.

    Returns:
        Path to the saved report file.

    Raises:
        ValueError: If LLM_PROVIDER is not set or unsupported.
    """
    provider = _load_provider()

    system_prompt = _load_system_prompt()
    tmp_dir = tempfile.mkdtemp(prefix="arxiv_pdfs_")
    reset_runtime_state()

    _log(f"[agent] provider: {provider}")
    _log(f"[agent] topic: {topic}")
    _log(f"[agent] max papers: {max_papers}")
    _log(f"[agent] tmp dir: {tmp_dir}")
    _log("")

    if provider == "anthropic":
        return _run_anthropic(topic, max_papers, system_prompt, tmp_dir)
    if provider == "gemini":
        return _run_gemini(topic, max_papers, system_prompt, tmp_dir)

    raise ValueError(f"Unsupported LLM_PROVIDER: '{provider}'. Use 'gemini' or 'anthropic'.")


def ask(question: str, session_memory: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Answer a question using the local knowledge base first, then approved external sources."""
    _load_provider()
    memory = build_memory(session_memory, question)
    local_evidence = retrieve_local_evidence(question, memory)
    external_evidence = []

    if should_search_externally(question, local_evidence):
        try:
            external_items = search_external_evidence(question, max_results=3)
            external_evidence = normalize_external_evidence(external_items)
        except Exception as e:
            _log(f"  ⚠ external evidence search failed: {e}")

    payload = _generate_answer_payload(question, memory, local_evidence, external_evidence)
    payload["session_memory"] = memory
    return payload


def _has_sufficient_primary_evidence(question: str, local_evidence: list[Any]) -> bool:
    constraints = parse_query_constraints(question)
    eligible = [item for item in local_evidence if item.primary_evidence_eligible]
    if not eligible:
        return False
    if has_explicit_market_constraint(constraints):
        return any(getattr(item, "market_match", False) for item in eligible)
    return eligible[0].score >= 3


def _should_trigger_research(
    question: str,
    local_evidence: list[Any],
    external_evidence: list[Any],
    session_memory: Optional[dict[str, Any]] = None,
) -> bool:
    if _has_sufficient_primary_evidence(question, local_evidence):
        return False

    lowered = question.lower()
    explicit_research_terms = (
        "find papers",
        "search papers",
        "research papers",
        "literature",
        "papers",
        "paper",
        "文獻",
        "論文",
        "研究",
    )
    if any(term in lowered for term in explicit_research_terms):
        return True

    if not local_evidence and not external_evidence:
        return True

    constraints = parse_query_constraints(question)
    if has_explicit_market_constraint(constraints):
        return not any(getattr(item, "market_match", False) for item in local_evidence)

    prior_queries = (session_memory or {}).get("researched_queries", [])
    return question not in prior_queries and not _has_sufficient_primary_evidence(question, local_evidence)


def chat(
    question: str,
    session_memory: Optional[dict[str, Any]] = None,
    max_papers: int = 3,
) -> dict[str, Any]:
    """Conversational QA that can trigger the research workflow when evidence is insufficient."""
    _load_provider()
    memory = build_memory(session_memory, question)
    local_evidence = retrieve_local_evidence(question, memory)
    external_evidence = []

    if should_search_externally(question, local_evidence):
        try:
            external_items = search_external_evidence(question, max_results=3)
            external_evidence = normalize_external_evidence(external_items)
        except Exception as e:
            _log(f"  ⚠ external evidence search failed: {e}")

    research_triggered = False
    report_path = ""
    if _should_trigger_research(question, local_evidence, external_evidence, session_memory=memory):
        _log("[chat] local evidence insufficient; triggering research workflow")
        try:
            report_path = research(topic=question, max_papers=max_papers)
            research_triggered = bool(report_path)
            local_evidence = retrieve_local_evidence(question, memory)
            external_evidence = []
        except Exception as e:
            _log(f"  ⚠ research workflow failed during chat: {e}")

    payload = _generate_answer_payload(question, memory, local_evidence, external_evidence)
    updated_memory = dict(memory)
    researched_queries = list(updated_memory.get("researched_queries", []))
    if research_triggered and question not in researched_queries:
        researched_queries.append(question)
    updated_memory["researched_queries"] = researched_queries
    if research_triggered and report_path:
        updated_memory["last_report_path"] = report_path
    payload["session_memory"] = updated_memory
    payload["research_triggered"] = research_triggered
    payload["report_path"] = report_path
    return payload


class ResearchSession:
    """Lightweight in-process session memory for conversational QA."""

    def __init__(self) -> None:
        self.memory: dict[str, Any] = {}

    def ask(self, question: str) -> dict[str, Any]:
        response = ask(question=question, session_memory=self.memory)
        self.memory = dict(response.get("session_memory", {}))
        return response

    def chat(self, question: str, max_papers: int = 3) -> dict[str, Any]:
        response = chat(question=question, session_memory=self.memory, max_papers=max_papers)
        self.memory = dict(response.get("session_memory", {}))
        return response


def run(topic: str, max_papers: int = 5) -> str:
    """Backward-compatible alias for the deep research workflow."""
    return research(topic=topic, max_papers=max_papers)
