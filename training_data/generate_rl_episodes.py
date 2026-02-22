#!/usr/bin/env python3
"""
Generate RL training episodes: full simulated conversations.
Each episode is a complete conversation with questions, answers, coverage tracking.
Supports multi-task scenarios.
"""
from __future__ import annotations

import json
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTPUT_PATH = "training_data/rl_episodes.jsonl"
MISSIONS_PATH = "training_data/missions.jsonl"

# Richer simulated user answer patterns
ANSWER_PATTERNS = {
    # Audience
    "target_audience": [
        "Women aged 25-45 interested in fashion and sustainability",
        "Small business owners in the service industry",
        "Tech professionals in their 30s who work remotely",
        "Parents with young children, mostly moms aged 28-40",
        "Health-conscious millennials and Gen Z",
        "College students and recent graduates",
        "B2B enterprise clients, specifically CTOs and engineering leads",
        "Local community members, families and young professionals",
        "Freelancers and independent consultants",
        "Home cooks who love experimenting with new recipes",
    ],
    "target_users": [
        "Our sales team and managers who need real-time data",
        "End consumers on mobile, primarily 18-35",
        "Freelancers and small agencies managing multiple clients",
        "Students and teachers at universities",
        "HR managers and team leads across departments",
        "Fitness enthusiasts tracking their workouts",
    ],
    "target_market": [
        "European luxury market, focus on France and Italy",
        "US small businesses with 5-50 employees",
        "Global tech startups in early stage",
        "Local service providers in the greater Montreal area",
        "North American e-commerce brands doing 1-10M revenue",
    ],
    "target_customers": [
        "Women 25-40 interested in sustainable fashion",
        "Tech-savvy professionals who value efficiency",
        "Young families with kids under 10",
        "Local community members who shop small",
        "Fitness enthusiasts who invest in quality gear",
        "Foodies who love trying new ingredients",
    ],
    "target_subscribers": [
        "Existing customers who've purchased in the last year",
        "Blog readers who want weekly tips",
        "Anyone interested in our free guides and resources",
        "Current users who want product updates",
    ],

    # Design
    "design_style": [
        "Modern and minimal with bold accent colors — think Apple meets Notion",
        "Clean and professional, corporate feel but not boring",
        "Fun and colorful, playful vibes — like Duolingo or Headspace",
        "Elegant and luxurious, like a high-end fashion brand",
        "Dark theme, futuristic feel, think cyberpunk meets minimal",
        "Warm and welcoming, earthy tones, approachable",
        "Bold and edgy, strong typography, lots of contrast",
    ],
    "design_direction": [
        "Purple and gold theme, luxurious but modern feel",
        "Bright and energetic — yellow, orange, warm gradients",
        "Clean white with blue accents, very professional",
        "Dark mode with neon accent colors, futuristic",
        "Earthy tones — olive green, terracotta, cream — natural feel",
        "Pink and coral for a feminine but professional look",
    ],
    "color_preferences": [
        "Purple and violet — our brand color is purple",
        "Blue and white, very clean and trustworthy",
        "Earth tones — olive green, terracotta, warm browns",
        "Black and gold for a premium feel",
        "Pastel colors — soft pink, mint, lavender",
        "Coral and teal, vibrant but not overwhelming",
    ],
    "existing_branding": [
        "Yes, we have a full brand guide — logo, colors, typography, the lot",
        "No, starting completely from scratch. We need everything",
        "We have a logo but need everything else built around it",
        "We have some old branding but it needs a complete refresh",
        "Just a name and a rough color idea, that's it",
    ],
    "visual_assets": [
        "We need custom illustrations and photo shoots",
        "Stock photography should work for now, plus some custom graphics",
        "We have product photos but need lifestyle imagery",
        "AI-generated images would work great for this",
        "We need icons, illustrations, and hero images",
    ],
    "visual_assets_needed": [
        "Need hero images, product shots, and social media graphics",
        "A few custom illustrations and icons for the website",
        "Photography for the campaign — studio shots and lifestyle",
        "Mainly graphics and banners, we can handle photos ourselves",
    ],

    # Technical
    "tech_platform": [
        "WordPress — we're already on it and know it well",
        "Shopify for sure, we need the e-commerce features",
        "Custom build with React and Next.js",
        "Webflow — we want to be able to update it ourselves",
        "We're open to suggestions, we don't have a strong preference",
        "Vue.js with a Python backend",
    ],
    "platform": [
        "iOS and Android, cross-platform — React Native or Flutter",
        "iOS first, we'll expand to Android later",
        "Progressive web app, don't need native",
        "Android only — our users are primarily on Android",
    ],
    "tech_stack": [
        "Python backend with FastAPI, React frontend",
        "Node.js with PostgreSQL, deployed on AWS",
        "Firebase for everything — auth, database, hosting",
        "Django and React, hosted on Heroku",
        "Next.js full stack with Vercel deployment",
    ],
    "email_platform": [
        "Mailchimp — we've used it before and like it",
        "Klaviyo for the segmentation features",
        "ConvertKit — we're creators and it fits our workflow",
        "We don't have one yet, need a recommendation",
        "SendGrid for transactional, Mailchimp for marketing",
    ],

    # Content & Messaging
    "key_message": [
        "Empowerment and innovation — we help you take control",
        "Quality at affordable prices, no compromises",
        "Making life easier through smart technology",
        "Sustainable choices for a better future",
        "Your success is our success — we're in this together",
        "Premium experience without the premium price tag",
    ],
    "messaging_tone": [
        "Professional but approachable — like a smart friend giving advice",
        "Fun and casual, like talking to your best friend about cool stuff",
        "Inspiring and motivational — we want to ignite action",
        "Technical but accessible — smart without being intimidating",
        "Warm and reassuring — we want people to feel safe and supported",
    ],
    "content_ready": [
        "We have some draft text but need professional copywriting and all images",
        "Everything needs to be created from scratch",
        "Text is mostly ready, just needs editing and polishing",
        "We have a content folder with rough ideas, needs to be organized",
        "Product descriptions are done, need everything else",
    ],
    "brand_voice": [
        "Conversational and warm — like a trusted advisor",
        "Professional and authoritative — we're the experts",
        "Playful and witty — we don't take ourselves too seriously",
        "Direct and no-nonsense — respect people's time",
    ],
    "brand_tone": [
        "Confident but humble, expert but approachable",
        "Energetic and positive, always solution-focused",
        "Thoughtful and empathetic, we genuinely care",
        "Bold and provocative, we challenge the status quo",
    ],
    "content_strategy": [
        "Mix of educational and promotional — 80/20 ratio",
        "Behind-the-scenes content, tips, and product features",
        "Customer stories and use cases",
        "Weekly industry insights and practical advice",
    ],

    # Business
    "timeline": [
        "2 weeks — tight deadline but we're flexible on scope",
        "About a month, ideally by end of next month",
        "3 months, no rush — quality over speed",
        "ASAP — we needed it yesterday honestly",
        "End of this quarter, around 6-8 weeks",
        "Flexible, whenever it's ready — we want it done right",
    ],
    "budget": [
        "Around 2000-3000 euros for this phase",
        "5-10K range, depends on what's included",
        "Under 1000 — we're bootstrapping",
        "Budget is flexible, quality matters more than cost",
        "15-20K for the full project including everything",
        "We haven't set a budget yet, what do you recommend?",
    ],
    "campaign_dates": [
        "March 8th is the key date — International Women's Day",
        "Black Friday through Cyber Monday week",
        "Starting January for Q1, running through March",
        "Need to launch by Valentine's Day",
        "Summer campaign — June through August",
    ],

    # Scope & Deliverables
    "core_features": [
        "Search with filters, user accounts, and a wishlist feature",
        "Payment processing, order management, and real-time notifications",
        "Real-time chat, file sharing, and team collaboration",
        "Dashboard with charts, export to PDF, and email reports",
        "User onboarding, subscription management, and analytics",
    ],
    "deliverables": [
        "Website redesign, email templates, and social media graphics kit",
        "Logo, business cards, brand guidelines, and social media templates",
        "Mobile app for iOS and Android with admin dashboard",
        "Landing page, 5-email welcome sequence, and lead magnet",
        "Full website with blog, 3 landing pages, and contact form",
    ],
    "campaign_channels": [
        "Email and Instagram — those are our strongest channels",
        "Facebook ads, Google ads, and email nurture sequence",
        "Organic social, influencer partnerships, and email",
        "Everything — email, social, paid ads, website banners, in-store signage",
        "TikTok and Instagram Reels primarily, with email backup",
    ],
    "email_types": [
        "Weekly newsletter plus automated welcome sequence",
        "Promotional emails for sales, plus abandoned cart recovery",
        "Monthly digest plus triggered emails based on behavior",
        "Transactional (order confirmations) plus marketing emails",
    ],
    "automation_flows": [
        "Welcome series, abandoned cart, and win-back campaigns",
        "Post-purchase follow-up and review request",
        "Lead nurture sequence over 7 days",
        "Birthday emails and anniversary discounts",
    ],
    "sending_frequency": [
        "Weekly newsletter on Tuesdays",
        "2-3 times per week during campaigns, weekly otherwise",
        "Monthly digest plus triggered emails",
        "Daily during launch week, then weekly",
    ],

    # Offers
    "offer_promotion": [
        "20% off for new customers with code WELCOME20",
        "Buy one get one free for the first 100 orders",
        "Free trial for 14 days, no credit card required",
        "Early bird pricing at 50% off until launch",
        "Free shipping on all orders during the campaign",
    ],
    "offer_incentive": [
        "15% discount code exclusive to email subscribers",
        "Free shipping on orders over 50 euros",
        "Gift with purchase — exclusive tote bag",
        "Early access to new products for loyalty members",
    ],
    "pricing_strategy": [
        "Premium pricing — we're positioning as a luxury brand",
        "Competitive pricing — matching market averages with better quality",
        "Freemium model — free basic, paid premium features",
        "Subscription tiers — starter, pro, enterprise",
    ],

    # Generic catch-all
    "_default": [
        "Yes, that sounds good. I like that direction.",
        "Let me think about that... I'd say we should keep it simple",
        "We haven't decided yet but probably something standard — I trust your judgment",
        "I'll follow your recommendation on that, you know best",
        "That's a good question. Yes, we definitely need that.",
        "Absolutely — that's important to us",
        "Not really a priority for us right now, but good to keep in mind",
        "We're flexible on that — whatever works best for the project",
    ],
}


def get_answer(element_name: str) -> str:
    """Get a simulated answer for an element."""
    if element_name in ANSWER_PATTERNS:
        return random.choice(ANSWER_PATTERNS[element_name])
    return random.choice(ANSWER_PATTERNS["_default"])


def generate_episode(mission: dict) -> dict:
    """Generate a single conversation episode."""
    elements = [
        {**e, "status": "undefined", "value": None}
        for e in mission["elements"]
    ]

    # Simulate: pre-answer 1-4 elements from initial prompt
    num_pre = random.randint(1, min(4, len(elements)))
    pre_answered_idx = random.sample(range(len(elements)), num_pre)
    for idx in pre_answered_idx:
        elements[idx]["status"] = "answered"
        elements[idx]["value"] = get_answer(elements[idx]["name"])

    # Calculate initial coverage
    total_score = sum(e["score"] for e in elements)
    answered_score = sum(e["score"] for e in elements if e["status"] == "answered")

    # Simulate conversation turns
    turns = []
    turn_num = 0
    max_turns = random.randint(4, 8)

    while turn_num < max_turns:
        coverage = answered_score / total_score if total_score > 0 else 1.0
        if coverage >= 0.90:
            break

        # Pick undefined elements sorted by score
        undefined = [e for e in elements if e["status"] == "undefined"]
        if not undefined:
            break

        undefined.sort(key=lambda e: e["score"], reverse=True)

        # Pick 1-3 elements to target (cluster question)
        num_targets = min(random.randint(1, 3), len(undefined))
        targets = undefined[:num_targets]

        # Simulate question and answer
        question_targets = [t["name"] for t in targets]
        answer = get_answer(targets[0]["name"])

        # Mark as answered
        for t in targets:
            t["status"] = "answered"
            t["value"] = get_answer(t["name"])
            answered_score += t["score"]

        turn_num += 1
        turns.append({
            "turn": turn_num,
            "targets": question_targets,
            "answer": answer,
            "coverage_after": answered_score / total_score,
            "elements_resolved": len(question_targets),
        })

    final_coverage = answered_score / total_score if total_score > 0 else 1.0

    return {
        "category": mission["category"],
        "task": mission["task"],
        "total_elements": len(elements),
        "pre_answered": num_pre,
        "turns": turns,
        "final_coverage": round(final_coverage, 3),
        "total_turns": len(turns),
        "reward": round(final_coverage * 100 - len(turns) * 5, 1),
    }


def generate_multi_task_episode(missions: list[dict]) -> dict:
    """Generate a multi-task episode combining 2 categories."""
    selected = random.sample(missions, min(2, len(missions)))

    # Merge elements from both categories
    all_elements = []
    seen_names = set()
    for mission in selected:
        for e in mission["elements"]:
            if e["name"] not in seen_names:
                all_elements.append({**e, "status": "undefined", "value": None})
                seen_names.add(e["name"])

    # Pre-answer a few
    num_pre = random.randint(2, min(6, len(all_elements)))
    pre_answered_idx = random.sample(range(len(all_elements)), num_pre)
    for idx in pre_answered_idx:
        all_elements[idx]["status"] = "answered"
        all_elements[idx]["value"] = get_answer(all_elements[idx]["name"])

    total_score = sum(e["score"] for e in all_elements)
    answered_score = sum(e["score"] for e in all_elements if e["status"] == "answered")

    turns = []
    turn_num = 0
    max_turns = random.randint(5, 10)

    while turn_num < max_turns:
        coverage = answered_score / total_score if total_score > 0 else 1.0
        if coverage >= 0.90:
            break

        undefined = [e for e in all_elements if e["status"] == "undefined"]
        if not undefined:
            break

        undefined.sort(key=lambda e: e["score"], reverse=True)
        num_targets = min(random.randint(1, 3), len(undefined))
        targets = undefined[:num_targets]
        question_targets = [t["name"] for t in targets]
        answer = get_answer(targets[0]["name"])

        for t in targets:
            t["status"] = "answered"
            t["value"] = get_answer(t["name"])
            answered_score += t["score"]

        turn_num += 1
        turns.append({
            "turn": turn_num,
            "targets": question_targets,
            "answer": answer,
            "coverage_after": answered_score / total_score,
            "elements_resolved": len(question_targets),
        })

    final_coverage = answered_score / total_score if total_score > 0 else 1.0

    return {
        "category": "+".join(m["category"] for m in selected),
        "task": " + ".join(m["task"] for m in selected),
        "total_elements": len(all_elements),
        "pre_answered": num_pre,
        "turns": turns,
        "final_coverage": round(final_coverage, 3),
        "total_turns": len(turns),
        "reward": round(final_coverage * 100 - len(turns) * 5, 1),
        "multi_task": True,
    }


def generate_rl_episodes():
    """Generate RL training episodes."""
    missions = []
    with open(MISSIONS_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                missions.append(json.loads(line))

    episodes = []

    # 30 single-task episodes per category
    for mission in missions:
        for _ in range(30):
            episode = generate_episode(mission)
            episodes.append(episode)

    # 50 multi-task episodes
    for _ in range(50):
        episode = generate_multi_task_episode(missions)
        episodes.append(episode)

    # Write output
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        for ep in episodes:
            f.write(json.dumps(ep) + "\n")

    # Stats
    single_eps = [e for e in episodes if not e.get("multi_task")]
    multi_eps = [e for e in episodes if e.get("multi_task")]
    avg_coverage = sum(e["final_coverage"] for e in episodes) / len(episodes)
    avg_turns = sum(e["total_turns"] for e in episodes) / len(episodes)
    avg_reward = sum(e["reward"] for e in episodes) / len(episodes)

    print(f"✅ Generated {len(episodes)} RL episodes")
    print(f"   Single-task: {len(single_eps)}, Multi-task: {len(multi_eps)}")
    print(f"📄 Saved to: {OUTPUT_PATH}")
    print(f"📊 Avg coverage: {avg_coverage * 100:.1f}%")
    print(f"📊 Avg turns: {avg_turns:.1f}")
    print(f"📊 Avg reward: {avg_reward:.1f}")
    return episodes


if __name__ == "__main__":
    generate_rl_episodes()
