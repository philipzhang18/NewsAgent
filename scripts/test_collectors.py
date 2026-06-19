#!/usr/bin/env python3
"""Test all news collectors and print diagnostics."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.services.data_collection_service import data_collection_service
from src.utils.async_helpers import run_async


async def main():
    print("=" * 60)
    print("News Agent — Collector Diagnostics")
    print("=" * 60)
    print(f"Configured sources: {len(data_collection_service.sources)}")
    for s in data_collection_service.sources:
        print(f"  - {s.name} ({s.source_type.value}) active={s.is_active}")

    print("\n--- Per-source connection tests ---")
    results = await data_collection_service.run_diagnostics()
    for r in results:
        status = "OK" if r.get("success") else "FAIL"
        print(f"[{status}] {r.get('source_name')}: {r.get('message') or r.get('error', '')}")
        if r.get("improvement"):
            print(f"       Improvement: {r['improvement']}")

    print("\n--- Full collection run ---")
    result = await data_collection_service.collect_all(save_to_db=True)
    print(json.dumps({
        "total_collected": result.get("total_collected"),
        "rss": result.get("rss_articles"),
        "newsapi": result.get("newsapi_articles"),
        "twitter": result.get("twitter_articles"),
        "reddit": result.get("reddit_articles"),
        "exa": result.get("exa_articles"),
        "saved": result.get("saved_to_db"),
        "processed": result.get("processed_count"),
    }, indent=2))

    if result.get("diagnostics"):
        print("\n--- Collection diagnostics ---")
        for d in result["diagnostics"]:
            print(f"  {d.get('source_name')}: success={d.get('success')} count={d.get('articles_collected')}")
            if d.get("improvement"):
                print(f"    -> {d['improvement']}")


if __name__ == "__main__":
    run_async(main())
