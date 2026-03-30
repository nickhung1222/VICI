"""CLI entry point for the quant research agent.

Usage:
    python main.py --topic "momentum strategy" --max-papers 5
"""

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

import agent


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Research quantitative trading strategies using academic papers from arXiv.",
    )
    parser.add_argument(
        "--topic",
        required=True,
        help='Strategy topic to research, e.g. "momentum factor Taiwan stock market"',
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=5,
        metavar="N",
        help="Maximum number of papers to analyze (default: 5)",
    )

    args = parser.parse_args()

    print(f"Starting research on: {args.topic!r}")
    print("-" * 60)

    try:
        report_path = agent.run(topic=args.topic, max_papers=args.max_papers)
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    if report_path:
        print()
        print("-" * 60)
        print(f"Report saved to: {report_path}")
    else:
        print("\nWarning: agent finished but no report was saved.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
