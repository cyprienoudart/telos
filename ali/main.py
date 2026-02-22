#!/usr/bin/env python3
"""
TELOS — Project Understanding Agent
Run this to start a conversation with the TELOS question agent.

Usage:
    python3 -m ali.main
    python3 -m ali.main "I want to build a website for my bakery"
    python3 -m ali.main --context output.md "Help me create a mobile app"
"""
from __future__ import annotations

import sys
import os

# Ensure the project root is in the path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ali.conversation_loop import ConversationLoop


def main():
    args = sys.argv[1:]

    # Parse optional flags
    context_path = "context.md"
    initial_text = None

    i = 0
    while i < len(args):
        if args[i] == "--context" and i + 1 < len(args):
            context_path = args[i + 1]
            i += 2
        elif args[i] == "--help" or args[i] == "-h":
            print(__doc__)
            sys.exit(0)
        elif not args[i].startswith("-"):
            initial_text = args[i]
            i += 1
        else:
            i += 1

    # Welcome
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║            🎯 TELOS — Project Understanding            ║")
    print("║                                                        ║")
    print("║  Tell me about your project and I'll ask the right     ║")
    print("║  questions to understand exactly what you need.        ║")
    print("║                                                        ║")
    print("║  Type 'quit' or 'done' at any time to end.             ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    # Get initial text if not provided as argument
    if not initial_text:
        print("📝 What project do you need help with?")
        print("   (Describe it in a few sentences — the more detail, the better)")
        print()
        try:
            initial_text = input("👤 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye!")
            sys.exit(0)

        if not initial_text:
            print("Please describe your project to get started.")
            sys.exit(1)

    # Initialize and start
    loop = ConversationLoop(
        missions_path="training_data/missions.jsonl",
        context_path=context_path,
    )

    result = loop.start(initial_text)

    # Show what TELOS detected
    categories = result.get("categories", [result["category"]])
    cat_display = ", ".join(c.replace("_", " ").title() for c in categories)

    print()
    print(f"   📋 Mission: {result['mission']}")
    print(f"   📂 {'Categories' if len(categories) > 1 else 'Category'}: {cat_display}")
    print(f"   ✅ Pre-understood: {result['pre_answered_count']}/{result['total_elements']} elements")
    print(f"   📊 Coverage: {result['initial_coverage'] * 100:.0f}%")
    print()

    if result["done"]:
        print("✨ I already have enough from your description! No questions needed.")
        print(f"📄 Context saved to: {context_path}")
        print()
        print(loop.context_mgr.to_prompt())
        return

    # Conversation loop
    question = result.get("first_question")
    question_info = result.get("_question_info") or {"targets": [], "question": question}

    print("─" * 58)
    print("  I have a few questions to make sure I understand everything.")
    print("─" * 58)
    print()

    while question:
        status = loop.get_status()
        progress = "█" * int(status["coverage"] * 20) + "░" * (20 - int(status["coverage"] * 20))
        print(f"   [{progress}] {status['coverage_pct']} coverage")
        print()
        print(f"🤔 TELOS: {question}")
        print()

        try:
            user_answer = input("👤 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 Ending conversation. Saving what we have...")
            break

        if not user_answer:
            continue

        if user_answer.lower() in ("quit", "exit", "done", "go", "stop", "q"):
            print("\n✨ Got it! Saving everything we discussed.")
            break

        # Process answer
        result = loop.process_answer(user_answer, question_info)

        if result.get("resolved"):
            n = len(result["resolved"])
            print(f"\n   ✅ Got it! Understood {n} thing{'s' if n > 1 else ''}.")
        if result.get("bonus"):
            n = len(result["bonus"])
            print(f"   🎁 Bonus — you also answered {n} extra thing{'s' if n > 1 else ''}!")
        print()

        if result.get("done"):
            print("✨ I have everything I need!")
            break

        question = result.get("next_question")
        question_info = result.get("_question_info") or {"targets": [], "question": question or ""}

    # Final output
    status = loop.get_status()
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                    📊 Summary                          ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print(f"║  Coverage: {status['coverage_pct']:>5}                                     ║")
    print(f"║  Questions asked: {status['turn']:>2}                                      ║")
    print(f"║  Elements resolved: {status['answered_count']:>2}/{status['total_elements']:<2}                                  ║")
    print(f"║  Context saved to: {context_path:<34}   ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    # Show remaining undefined (if any)
    undefined = loop.sft_model.get_undefined_elements(loop.elements)
    if undefined:
        print("📋 We can figure these out later:")
        for e in undefined[:5]:
            print(f"   • {e['description']}")
        print()

    # Show context.md
    print("═" * 58)
    print("📄 Generated Project Brief:")
    print("═" * 58)
    print()
    print(loop.context_mgr.to_prompt())


if __name__ == "__main__":
    main()
