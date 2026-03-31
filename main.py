"""CLI entry point for the quant research agent.

Usage:
    python main.py --mode research --topic "momentum strategy" --max-papers 5
    python main.py --mode ask --question "What does the knowledge base say about S&P 500 market timing?"
    python main.py --mode chat
"""

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

import agent


def _print_answer(result: dict) -> None:
    print(result["answer"])
    if result.get("research_triggered"):
        report_path = result.get("report_path")
        if report_path:
            print(f"\nResearch workflow triggered. Report saved to: {report_path}")
        else:
            print("\nResearch workflow triggered.")
    if result.get("citations"):
        print("\nCitations:")
        for citation in result["citations"]:
            title = citation.get("title", "Untitled source")
            source_type = citation.get("source_type", "unknown")
            locator = citation.get("locator") or citation.get("url") or citation.get("arxiv_id", "")
            print(f"- [{source_type}] {title} :: {locator}")
    freshness_note = result.get("freshness_note")
    if freshness_note:
        print(f"\nFreshness note: {freshness_note}")


def _run_chat_loop() -> int:
    session = agent.ResearchSession()
    print("Interactive chat mode. Type 'exit' or 'quit' to leave.")
    print("-" * 60)

    while True:
        try:
            question = input("> ").strip()
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print("\nExiting chat.")
            return 0

        if not question:
            continue
        if question.lower() in {"exit", "quit", ":q"}:
            return 0

        try:
            result = session.chat(question)
        except ValueError as e:
            print(f"Configuration error: {e}", file=sys.stderr)
            return 1

        print()
        _print_answer(result)
        print("\n" + "-" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Research or query quantitative trading strategy knowledge.",
    )
    parser.add_argument(
        "--mode",
        choices=("research", "ask", "chat"),
        default="research",
        help="Run a deep research workflow, ask one question, or enter interactive chat mode (default: research)",
    )
    parser.add_argument(
        "--topic",
        help='Strategy topic to research, e.g. "momentum factor Taiwan stock market"',
    )
    parser.add_argument(
        "--question",
        help='Question to answer in ask mode, e.g. "Which papers support S&P 500 valuation timing?"',
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=5,
        metavar="N",
        help="Maximum number of papers to analyze (default: 5)",
    )

    args = parser.parse_args()

    if args.mode == "research" and not args.topic:
        parser.error("--topic is required when --mode research")
    if args.mode == "ask" and not args.question:
        parser.error("--question is required when --mode ask")
    if args.mode == "chat":
        raise SystemExit(_run_chat_loop())

    label = args.topic if args.mode == "research" else args.question
    print(f"Starting {args.mode} on: {label!r}")
    print("-" * 60)

    try:
        if args.mode == "research":
            result = agent.research(topic=args.topic, max_papers=args.max_papers)
        else:
            result = agent.ask(question=args.question)
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    print()
    print("-" * 60)

    if args.mode == "research":
        if result:
            print(f"Report saved to: {result}")
        else:
            print("\nWarning: agent finished but no report was saved.", file=sys.stderr)
            sys.exit(1)
    else:
        _print_answer(result)


if __name__ == "__main__":
    main()
