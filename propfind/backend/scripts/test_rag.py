"""
test_rag.py — Automated RAG verification: 10 answerable + 10 out-of-scope queries.
Run from propfind/backend/:  python scripts/test_rag.py
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.WARNING)

ANSWERABLE = [
    "Show me 2 BHK apartments in Noida available for rent",
    "What properties are available near metro in Dwarka?",
    "Find PG accommodation with food included in Gurgaon",
    "What is the average rent for 1 BHK in Indirapuram?",
    "Are there any independent houses for sale in Greater Noida?",
    "Show me properties in Hauz Khas under ₹60,000/month",
    "What amenities does a typical apartment in Cyber City have?",
    "Find 3 BHK builder floor in Rohini",
    "What's the cheapest PG accommodation in Noida?",
    "Show properties with gym and swimming pool",
]

OUT_OF_SCOPE = [
    "What is the capital of France?",
    "Who is the current Prime Minister of India?",
    "Recommend a good restaurant near Connaught Place",
    "How do I file my income tax returns?",
    "What's the latest news in cricket?",
    "Show me hotels in Shimla",
    "What is the weather in Delhi today?",
    "Can you help me find a job?",
    "Tell me a joke",
    "Who won the 2024 elections?",
]

EXPECTED_EMPTY_RESPONSE = "I couldn't find any properties matching that in our current listings."


def run_tests():
    from app.rag.pipeline import rag_query

    print("=" * 60)
    print("PropFind RAG Test Suite")
    print("=" * 60)

    pass_count = 0
    fail_count = 0

    print("\n📋 ANSWERABLE QUERIES (expect relevant property info):")
    for i, q in enumerate(ANSWERABLE, 1):
        result = rag_query(q, n_results=5)
        answer = result["answer"]
        sources = result["source_count"]
        passed = sources > 0 and EXPECTED_EMPTY_RESPONSE not in answer
        status = "✅ PASS" if passed else "❌ FAIL"
        if passed:
            pass_count += 1
        else:
            fail_count += 1
        print(f"  {i:2}. [{status}] [{sources} sources] {q[:60]}...")
        if not passed:
            print(f"       → {answer[:100]}")

    print("\n📋 OUT-OF-SCOPE QUERIES (expect graceful refusal):")
    for i, q in enumerate(OUT_OF_SCOPE, 1):
        result = rag_query(q, n_results=5)
        answer = result["answer"]
        sources = result["source_count"]
        # A graceful response means: either no sources found, or answer contains refusal phrase
        passed = sources == 0 or EXPECTED_EMPTY_RESPONSE in answer or "couldn't find" in answer.lower()
        status = "✅ PASS" if passed else "⚠️  WARN"
        if passed:
            pass_count += 1
        else:
            fail_count += 1
        print(f"  {i:2}. [{status}] [{sources} sources] {q[:60]}...")

    print("\n" + "=" * 60)
    print(f"Results: {pass_count} passed, {fail_count} failed out of {len(ANSWERABLE) + len(OUT_OF_SCOPE)} tests")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
