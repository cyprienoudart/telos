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

import re
import sys
import os

# Ensure the project root is in the path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ali.conversation_loop import ConversationLoop

# Patterns that mean "skip this question"
SKIP_PATTERNS = re.compile(
    r"^("
    r"no\s*idea|idk|i\s*don'?t\s*know|not\s*sure|skip|pass|next"
    r"|i\s*have\s*no\s*idea|no\s*clue|don'?t\s*know"
    r"|i'?m\s*not\s*sure|whatever|doesn'?t?\s*matter"
    r"|i\s*don'?t\s*care|no\s*preference|none|nah|n/?a"
    r")$",
    re.IGNORECASE,
)


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
        elif args[i] in ("--help", "-h"):
            print(__doc__)
            sys.exit(0)
        elif not args[i].startswith("-"):
            initial_text = args[i]
            i += 1
        else:
            i += 1

    # # Welcome
    # print()
    # print("🎯 TELOS — Tell me about your project and I'll figure out what you need.")
    # print()

    # Get initial text if not provided as argument
    if not initial_text:
        try:
            initial_text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            # print("\nGoodbye!")
            sys.exit(0)

        if not initial_text:
            # print("Please describe your project to get started.")
            sys.exit(1)

    # Initialize and start
    loop = ConversationLoop(
        missions_path="train/data/missions.jsonl",
        context_path=context_path,
    )

    result = loop.start(initial_text)

    if result["done"]:
        # print("\nTELOS: I already have everything I need from your description!")
        # print(f"\n📄 Saved to {context_path}")
        return

    # Conversation loop
    question = result.get("first_question")
    question_info = result.get("_question_info") or {"targets": [], "question": question}

    while question:
        print(f"\nTELOS: {question}\n")

        try:
            user_answer = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_answer:
            continue

        if user_answer.lower() in ("quit", "exit", "done", "stop", "q"):
            break

        # Skip if user doesn't know / no idea
        if SKIP_PATTERNS.match(user_answer.strip()):
            result = loop.process_answer("", question_info)
        else:
            result = loop.process_answer(user_answer, question_info)

        if result.get("done"):
            # print("\nTELOS: That's everything I needed, thank you!")
            break

        question = result.get("next_question")
        question_info = result.get("_question_info") or {"targets": [], "question": question or ""}

    # # Done
    # print(f"\n📄 Saved to {context_path}")


if __name__ == "__main__":
    main()
