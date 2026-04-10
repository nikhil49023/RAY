#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from agents.monitoring import (
    query_groq_credit,
    query_sarvam_credit,
    read_usage,
    summarize_usage,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Show usage summary and provider credit status where available.")
    parser.add_argument("--limit", type=int, default=2000, help="How many recent usage records to include")
    parser.add_argument("--json", action="store_true", help="Print output as JSON")
    args = parser.parse_args()

    records = read_usage(limit=args.limit)
    usage = summarize_usage(records)
    credits = {
        "groq": query_groq_credit(),
        "sarvam": query_sarvam_credit(),
    }

    output = {
        "usage_summary": usage,
        "credit_status": credits,
    }

    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=True))
        return

    print("=" * 90)
    print("USAGE SUMMARY")
    print("=" * 90)
    print(f"Total calls tracked: {usage['total_calls']}")

    print("\nBy provider:")
    for provider, stats in usage["providers"].items():
        print(
            f"  - {provider:<12} calls={stats['calls']:<5} "
            f"input_tokens={stats['input_tokens']:<8} "
            f"output_tokens={stats['output_tokens']:<8} total_tokens={stats['total_tokens']}"
        )

    print("\nBy model:")
    for model, stats in usage["models"].items():
        print(
            f"  - {model:<45} calls={stats['calls']:<5} "
            f"input_tokens={stats['input_tokens']:<8} "
            f"output_tokens={stats['output_tokens']:<8} total_tokens={stats['total_tokens']}"
        )

    print("\n" + "=" * 90)
    print("CREDIT STATUS")
    print("=" * 90)
    for provider, info in credits.items():
        status = info.get("status")
        if status == "ok":
            remaining = info.get("limit_remaining")
            if remaining is not None:
                print(f"  - {provider}: ok, remaining={remaining}")
            else:
                print(f"  - {provider}: ok ({info.get('note', 'no remaining credit metric exposed')})")
        else:
            print(f"  - {provider}: {status} ({info.get('note', info.get('detail', 'no details'))})")


if __name__ == "__main__":
    main()
