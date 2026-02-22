#!/usr/bin/env python3
"""
Demo Test — Simulates the IWD campaign scenario end-to-end.
Verifies all 4 components work together and reach ≥90% coverage.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ali.input_parser import InputParser
from ali.sft_element_model import SFTElementModel
from ali.clustering import ElementClusterer
from ali.rl_question_generator import RLQuestionGenerator
from ali.qwen_extractor import QwenExtractor
from ali.context_manager import ContextManager
from ali.conversation_loop import ConversationLoop


# ─── Simulated user answers for the IWD demo ───────────────────────

DEMO_INITIAL_PROMPT = (
    "Hey, I want to do something special for International Women's Day "
    "on our Shopify store. Like a whole campaign — change the site, get some "
    "nice visuals, and send emails to our list."
)

# Pre-scripted answers keyed by element clusters/topics
DEMO_ANSWERS = {
    # Deliverables / scope
    "scope_and_deliverables": (
        "Three things: adapt the homepage for the campaign, generate AI images "
        "for the visuals, and send a promotional email to our subscribers."
    ),
    "deliverables": (
        "Three things: adapt the homepage for the campaign, generate AI images "
        "for the visuals, and send a promotional email to our subscribers."
    ),
    "campaign_objectives": (
        "Main goal is to boost sales during IWD week and celebrate women in our industry. "
        "We want to drive traffic to a featured collection."
    ),
    "campaign_goal": (
        "Main goal is to boost sales during IWD week and celebrate women in our industry."
    ),

    # Audience
    "audience_and_reach": (
        "Our customers are mostly women aged 25-45, interested in sustainable fashion. "
        "We have about 12k email subscribers and 8k Instagram followers."
    ),
    "target_audience": (
        "Our customers are mostly women aged 25-45, interested in sustainable fashion."
    ),

    # Design
    "design_and_brand": (
        "Purple and violet theme. Illustrated style — modern and bold, not photo-realistic. "
        "We already have our logo and brand colors from our designer."
    ),
    "design_direction": (
        "Purple and violet theme, illustrated style, modern and bold."
    ),
    "design_style": (
        "Purple and violet theme, illustrated style, modern and bold."
    ),

    # Content & messaging
    "content_and_messaging": (
        "The message should be about empowerment and celebrating women in sustainable fashion. "
        "Tone should be inspiring but not preachy. We need to create all the visual content."
    ),
    "key_message": (
        "Empowerment and celebrating women in sustainable fashion."
    ),
    "messaging_tone": (
        "Inspiring but not preachy, warm and celebratory."
    ),

    # Visuals
    "visual_assets_needed": (
        "We need about 5-8 AI-generated illustrations for the homepage banner, "
        "product collection headers, and the email. Modern, bold, illustrated style."
    ),
    "visual_assets": (
        "5-8 AI-generated illustrations for site and email."
    ),

    # Offer
    "offer_and_commerce": (
        "15% discount code for the featured IWD collection. The code will be WOMENSDAY15."
    ),
    "offer_promotion": (
        "15% discount code for the featured IWD collection."
    ),
    "offer_incentive": (
        "15% discount code for the featured IWD collection. Code: WOMENSDAY15."
    ),

    # Technical
    "technical_setup": (
        "It's a Shopify store, we use Klaviyo for email marketing. "
        "Homepage takeover, not a separate landing page."
    ),
    "existing_platform": (
        "Shopify store, using Klaviyo for emails."
    ),

    # Logistics
    "business_and_logistics": (
        "Campaign should go live by March 5th, run through March 10th. "
        "Budget is around 2000 euros for the whole thing."
    ),
    "timeline": (
        "March 5-10, about a week."
    ),
    "campaign_dates": (
        "March 5 through March 10."
    ),
    "budget": (
        "Around 2000 euros."
    ),
}


def find_answer(question_info: dict) -> str:
    """Find the best matching answer for a question."""
    # Try cluster name first
    cluster = question_info.get("cluster", "")
    if cluster and cluster in DEMO_ANSWERS:
        return DEMO_ANSWERS[cluster]

    # Try individual target elements
    targets = question_info.get("targets", [])
    for target in targets:
        if target in DEMO_ANSWERS:
            return DEMO_ANSWERS[target]

    # Fallback
    return "I'm not sure about that, let's figure it out later."


def run_demo():
    """Run the full IWD demo scenario."""
    print("=" * 70)
    print("🎯 TELOS ALI — IWD Campaign Demo (Automated)")
    print("=" * 70)
    print()

    # Initialize
    loop = ConversationLoop(
        missions_path="training_data/missions.jsonl",
        context_path="demo_context.md",
    )

    # Start with the user's initial prompt
    print(f"👤 User: {DEMO_INITIAL_PROMPT}")
    print()

    result = loop.start(DEMO_INITIAL_PROMPT)

    print(f"📋 Mission detected: {result['mission']}")
    print(f"📂 Category: {result['category']}")
    print(f"✅ Pre-answered from prompt: {result['pre_answered_count']}/{result['total_elements']} elements")
    print(f"📊 Initial coverage: {result['initial_coverage'] * 100:.0f}%")
    print()

    if result.get("_candidates"):
        print("   📝 Candidate questions generated:")
        for i, c in enumerate(result["_candidates"][:5], 1):
            score = c["score"]
            targets = ", ".join(c["targets"][:3])
            print(f"      {i}. [score:{score:.0f}] {c['question'][:80]}...")
            print(f"         targets: {targets}")
        print()

    if result["done"]:
        print("✨ Already done from initial input!")
        return

    # Run conversation loop
    question = result.get("first_question")
    question_info = result.get("_question_info") or {"targets": [], "question": question}

    while question and not result.get("done", False):
        turn = loop.turn_count + 1
        print(f"━━━ Turn {turn} ━━━")
        print(f"🤔 ALI asks: {question}")
        print()

        # Find simulated answer
        answer = find_answer(question_info)
        print(f"👤 User: {answer}")
        print()

        # Process
        result = loop.process_answer(answer, question_info)

        status = loop.get_status()
        print(f"   📊 Coverage: {status['coverage_pct']} ({status['answered_count']}/{status['total_elements']})")
        if result.get("resolved"):
            print(f"   ✅ Resolved: {', '.join(result['resolved'])}")
        if result.get("bonus"):
            print(f"   🎁 Bonus: {', '.join(result['bonus'])}")

        if result.get("_candidates"):
            print(f"   📝 Next candidates: {len(result['_candidates'])}")
        print()

        question = result.get("next_question")
        question_info = result.get("_question_info") or {"targets": [], "question": question or ""}

    # Final report
    print("=" * 70)
    status = loop.get_status()
    print(f"📊 FINAL COVERAGE: {status['coverage_pct']}")
    print(f"🔄 TURNS USED: {status['turn']}")
    print(f"✅ ANSWERED: {status['answered_count']}/{status['total_elements']} elements")
    print(f"❓ REMAINING: {status['undefined_count']} elements")
    print()

    # Show remaining undefined elements
    undefined = loop.sft_model.get_undefined_elements(loop.elements)
    if undefined:
        print("📋 Still undefined (low importance):")
        for e in undefined:
            print(f"   - {e['name']} (score: {e['score']}): {e['description']}")
        print()

    # Show the generated context.md
    print("=" * 70)
    print("📄 GENERATED CONTEXT.MD (for Opus):")
    print("=" * 70)
    print()
    print(loop.context_mgr.to_prompt())

    # Verify results
    print("=" * 70)
    print("🧪 VERIFICATION:")
    coverage = float(status['coverage_pct'].strip('%')) / 100
    turn_count = status['turn']

    # Get the actual category from the initial parse
    actual_category = loop.elements[0].get("name", "") if loop.elements else ""
    
    checks = [
        ("Coverage ≥ 90%", coverage >= 0.90),
        ("Turns ≤ 10", turn_count <= 10),
        ("Category is event_campaign", any(e["name"] == "event_theme" for e in loop.elements)),
        ("Context.md generated", os.path.exists("demo_context.md")),
    ]

    all_passed = True
    for check_name, passed in checks:
        icon = "✅" if passed else "❌"
        print(f"   {icon} {check_name}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("🎉 ALL CHECKS PASSED — Demo scenario works!")
    else:
        print("⚠️  Some checks failed — needs investigation.")

    return all_passed


if __name__ == "__main__":
    success = run_demo()
    sys.exit(0 if success else 1)
