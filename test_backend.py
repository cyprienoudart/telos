"""
Direct backend test — calls the same Python internals the server routes use,
bypassing HTTP to avoid session loss from server restarts.

Usage:
    cd /Users/valprok/Documents/telos
    PYTHONPATH="$PWD:$PWD/agent" server/.venv/bin/python test_backend.py
"""

import sys
from pathlib import Path

# Add paths (same as server/main.py does)
ROOT = Path(__file__).resolve().parent
for p in [str(ROOT), str(ROOT / "agent")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from ali.conversation_loop import ConversationLoop

MISSIONS_PATH = str(ROOT / "train" / "data" / "missions.jsonl")
TEST_MESSAGE = (
    "We need to create a marketing campaign for International Womans Day. "
    "We have to edit the landing page and send out email campaigns to all "
    "the women in our database with a discount. Both the website and email "
    "campaign has to include a relevant AI generated image."
)

# Dense answers designed to resolve as many elements as possible per turn
ANSWERS = [
    # Turn 1: deliverables, tech, design, audience, budget, timeline
    (
        "Deliverables: 1) Updated landing page hero section at /womens-day route with "
        "AI-generated image of diverse empowered women, purple/gold theme, headline, "
        "CTA button for 20% discount code WOMENSDAY2026. 2) Email blast template for "
        "Mailchimp with the AI image, discount code, CTA to landing page. 3) Reminder "
        "and last-chance emails. Target audience: women aged 25-45, existing customers, "
        "50,000 in our CRM database. Design: modern, elegant, empowering with purple "
        "#7C3AED and gold #F59E0B. Tech: Next.js 14 TypeScript on Vercel, Mailchimp for "
        "email with API and Mandrill automation, Twenty CRM on Docker. Budget: $2,000. "
        "Timeline: landing page by Feb 28, campaign March 1-15. Brand tone: empowering, "
        "celebratory, warm. Key message: Celebrate the women who inspire us."
    ),
    # Turn 2: content, messaging, brand, SEO
    (
        "Core message: Celebrate the women who inspire us — treat yourself with 20% off. "
        "Brand voice is confident and supportive. Headline: Empower Her Day — Your Strength "
        "Deserves a Reward. Email subject: You Deserve This — 20% Off for International "
        "Womens Day. A/B test subject lines. We have brand guidelines in Figma. Content "
        "needs to be created from scratch. Content type: promotional with brand storytelling. "
        "Topics: womens empowerment, self-care, celebration. SEO: meta tags, Open Graph for "
        "social sharing, structured data. Typography: Inter font, Arial fallback. Visual "
        "style: artistic modern illustration, not stock photos."
    ),
    # Turn 3: campaign goals, channels, metrics
    (
        "Campaign goal: drive sales with 2000+ discount code redemptions generating 40K "
        "revenue. 15% revenue increase over last year. Secondary: brand awareness and "
        "customer loyalty. Campaign channels: email primary, landing page hub, social media "
        "cross-promotion on Instagram and Facebook. Social sharing buttons on landing page. "
        "Success metrics: email open rate above 25%, CTR above 5%, 2000 redemptions, 500 new "
        "signups. Campaign duration: March 1-15, 2026. Products/services: all products in "
        "our catalog eligible for the discount."
    ),
    # Turn 4: email specifics, automation, segmentation
    (
        "Email types: hero launch email March 1, reminder March 10, last-chance March 14. "
        "Automation: welcome drip for new signups, abandoned cart for clickers. Sending "
        "frequency: 3 emails over 2 weeks. Email platform: Mailchimp, fully set up with "
        "API keys and Mandrill. Segmentation: gender filter (women only), VIP customers "
        "(spent over $500) get early access Feb 28, dormant customers get re-engagement "
        "version. Target subscribers: women 25-45 professionals. Personalization with "
        "Mailchimp merge tags FNAME, LNAME. UTM tracking on all links."
    ),
    # Turn 5: design template, visual assets, responsive, accessibility
    (
        "Email template: responsive HTML, 600px wide, header with logo, AI banner full "
        "width, headline in Inter/Arial bold, body 16px, discount code box gold border "
        "purple background, CTA button purple #7C3AED white text rounded corners. Style "
        "references: Glossier and Aesop email aesthetic. AI images: 1920x1080 WebP for web, "
        "600x400 PNG for email. Artistic modern illustration with diverse women, floral "
        "elements, purple/gold palette. Mobile-first responsive design, 65% opens on mobile, "
        "min 44px touch targets, fast loading under 3 seconds. Accessibility: alt text, "
        "color contrast, semantic HTML. Plain text email fallback included."
    ),
    # Turn 6: integrations, data, pricing, offer details
    (
        "Integrations: Mailchimp API, Twenty CRM REST API, Stripe for payments, Google "
        "Analytics for tracking. Data sources: Twenty CRM for customer segments, Mailchimp "
        "for email analytics. Domain/hosting: Vercel for website, custom domain. Offer: "
        "20% off all products code WOMENSDAY2026 valid March 1-15. Pricing strategy: "
        "discount on existing prices. Payment via Stripe. No shipping changes. We want "
        "discount code validation via our REST API backend. Refer-a-friend gives both "
        "parties extra 5% off."
    ),
    # Turn 7-10: catch remaining elements
    (
        "Content strategy: the hero email has AI banner, headline, 2-3 paragraphs about "
        "the promotion, discount code in styled callout box, Shop Now CTA, product category "
        "links, social icons, unsubscribe footer. Reminder is shorter with deadline focus. "
        "Last-chance has countdown urgency. Our brand personality is sophisticated yet "
        "approachable. We want a unified visual identity across landing page, email, and "
        "social. The landing page should have the hero section, about section explaining "
        "the campaign, featured products grid, signup form for extra 5%, and social proof."
    ),
    (
        "For the landing page structure: hero with AI image and CTA, campaign story section, "
        "featured products with prices, email signup form, social sharing buttons, FAQ about "
        "the discount, footer. The page should have a countdown timer to March 15 deadline. "
        "Our existing platform setup includes Next.js app router, Tailwind CSS, and we "
        "already have a product catalog of about 200 items. The maintenance plan is to "
        "keep the landing page up through March and then archive it. Post-campaign we want "
        "to analyze metrics and document learnings."
    ),
    (
        "Color preferences: purple #7C3AED primary, gold #F59E0B accent, white #FFFFFF "
        "background, dark gray #1F2937 text. Style references: we admire the campaigns "
        "from Glossier, Aesop, and The Ordinary. Our existing backend has a REST API for "
        "product data and discount validation. We use Stripe webhooks for order confirmation "
        "emails. The AI-generated image prompt should emphasize diverse women of different "
        "ethnicities and ages in an empowering artistic style."
    ),
    (
        "Additional context: we want the marketing campaign to feel authentic and not "
        "performative. The event theme is empowerment through everyday celebration. "
        "Our promotion channel mix is 60% email, 25% landing page organic, 15% social. "
        "For campaign objectives: primary is sales conversion, secondary is list growth, "
        "tertiary is brand sentiment improvement. We track NPS scores post-campaign."
    ),
]


def run():
    print("=" * 60)
    print("TELOS BACKEND DIRECT TEST")
    print("=" * 60)

    # 1. Create conversation loop (same as SessionStore.create())
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="telos_test_"))
    context_path = tmp / "context.md"

    loop = ConversationLoop(
        missions_path=MISSIONS_PATH,
        context_path=str(context_path),
    )

    # 2. Start conversation (same as conversation.py:start_conversation)
    print("\n--- Starting conversation ---")
    result = loop.start(TEST_MESSAGE)
    print(f"Mission: {result['mission']}")
    print(f"Categories: {result['categories']}")
    print(f"Elements: {result['total_elements']}")
    print(f"Pre-answered: {result['pre_answered_count']}")
    print(f"Coverage: {result['initial_coverage']:.0%}")
    print(f"Done: {result['done']}")
    print(f"C1 source: {result.get('c1_source', 'N/A')}")

    question_info = result.get("_question_info") or {
        "targets": [],
        "question": result.get("first_question", ""),
    }

    if result.get("first_question"):
        print(f"\nFirst Q: {result['first_question']}")

    # 3. Answer loop (same as conversation.py:answer_question)
    answer_idx = 0
    while not result.get("done", False) and answer_idx < len(ANSWERS):
        question = question_info.get("question", "")
        answer = ANSWERS[answer_idx]

        print(f"\n--- Turn {answer_idx + 1} ---")
        print(f"Q: {question[:100]}...")
        print(f"A: {answer[:100]}...")

        result = loop.process_answer(answer, question_info)

        question_info = result.get("_question_info") or {
            "targets": [],
            "question": result.get("next_question", ""),
        }

        print(f"Resolved: {result['resolved']}")
        print(f"Coverage: {result['coverage']:.0%}")
        print(f"Done: {result['done']}")

        if result.get("next_question"):
            print(f"Next Q: {result['next_question'][:100]}...")

        answer_idx += 1

    # 4. Final status
    print("\n" + "=" * 60)
    status = loop.get_status()
    print(f"FINAL STATUS:")
    print(f"  Turns: {status['turn']}")
    print(f"  Coverage: {status['coverage_pct']}")
    print(f"  Answered: {status['answered_count']}/{status['total_elements']}")
    print(f"  Undefined: {status['undefined_count']}")
    print(f"  Categories: {status['categories']}")

    # 5. Save transcript (same as session.transcript = session.loop.context_mgr.to_prompt())
    transcript = loop.context_mgr.to_prompt()
    transcript_path = tmp / "transcript.md"
    transcript_path.write_text(transcript)
    print(f"\nTranscript saved: {transcript_path}")
    print(f"Context.md saved: {context_path}")

    # 6. Show context.md content
    print("\n" + "=" * 60)
    print("GENERATED CONTEXT.MD (transcript for build phase):")
    print("=" * 60)
    content = context_path.read_text()
    # Show first 2000 chars
    if len(content) > 2000:
        print(content[:2000])
        print(f"\n... ({len(content) - 2000} more chars)")
    else:
        print(content)

    # 7. Optionally trigger the build
    print("\n" + "=" * 60)
    print("NEXT STEP: To trigger the build (Ralph loop), run:")
    print(f"  PYTHONPATH=\"$PWD:$PWD/agent\" server/.venv/bin/python -c \"")
    print(f"from telos_agent.orchestrator import TelosOrchestrator")
    print(f"from pathlib import Path")
    print(f"orch = TelosOrchestrator(project_dir=Path('/tmp/telos-iwd-test'), max_iterations=5, model='opus')")
    print(f"result = orch.plan_and_execute(Path('{transcript_path}').read_text())")
    print(f"print('Success:', result.success)")
    print(f"\"")
    print("=" * 60)

    return transcript


if __name__ == "__main__":
    run()
