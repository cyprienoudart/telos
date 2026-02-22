#!/usr/bin/env python3
"""
Generate SFT training pairs from missions.jsonl.
Creates question-answer pairs for fine-tuning element identification.
Supports multi-task prompt generation.
"""
from __future__ import annotations

import json
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTPUT_PATH = "train/data/sft_pairs.jsonl"
MISSIONS_PATH = "train/data/missions.jsonl"

# Simulated user prompts for each category
USER_PROMPTS = {
    "web_development": [
        "I need a website for my {business}",
        "Can you build me a {type} website?",
        "I want to create a {type} for my {business}",
        "We need a new website redesigned from scratch",
        "I need a landing page for my {business}",
        "Help me build a professional website for my {business}",
        "I want a modern website for my company",
        "We're launching a new {business} and need a site",
        "I need a website update for my existing {business}",
        "Our {business} needs a complete web redesign",
        "We want a responsive website that looks great on mobile",
        "I'm looking for someone to build a {type} site for my {business}",
    ],
    "marketing_campaign": [
        "I want to run a marketing campaign for {product}",
        "Help me create a {type} campaign",
        "We need to promote our new {product}",
        "I want to launch an email campaign for our {product}",
        "Help me plan a marketing push for {product}",
        "We need a campaign to acquire new customers",
        "I want to run ads for our {product}",
        "We're planning a big launch campaign for {product}",
        "I need a multi-channel marketing campaign",
        "Help me create a campaign strategy to boost sales",
    ],
    "design_branding": [
        "I need a brand identity for my {business}",
        "We want to rebrand our {business}",
        "Can you design a logo and brand for {business}?",
        "I need branding for a new {business}",
        "We need a complete brand identity package",
        "Our brand needs a refresh — new logo and everything",
        "I'm starting a {business} and need branding from scratch",
        "We need brand guidelines and visual identity",
        "Help us create a cohesive brand identity",
    ],
    "content_creation": [
        "I need content for my {business}",
        "Help me create blog posts about {topic}",
        "We need social media content for {business}",
        "I want to start a content strategy for {business}",
        "We need regular content for our website",
        "Help me plan a content calendar for {business}",
        "I need video and blog content for {business}",
        "We want to create educational content about {topic}",
        "I need a content plan to build our online presence",
    ],
    "ecommerce": [
        "I want to sell {product} online",
        "Help me build an online store for {product}",
        "I need an e-commerce site for my {business}",
        "We want to launch an online shop",
        "I need a Shopify store for {product}",
        "Help me set up an online marketplace",
        "We're moving our {business} online",
        "I want to start an e-commerce business selling {product}",
        "We need an online store with payment processing",
    ],
    "mobile_app": [
        "I want to build an app for {purpose}",
        "We need a mobile app for our {business}",
        "I have an idea for an app that {purpose}",
        "Help me create an iOS and Android app",
        "We need a mobile application for {purpose}",
        "I want to build a {type} app",
        "Our {business} needs a mobile app",
        "I want to create a cross-platform app for {purpose}",
        "Help me build a native mobile app",
    ],
    "data_analytics": [
        "I need a dashboard to track {metrics}",
        "Help me visualize our {data} data",
        "We need analytics for our {business}",
        "I want a real-time dashboard for {metrics}",
        "Help me build a reporting tool",
        "We need to track our KPIs better",
        "I want to see our {data} in charts and graphs",
        "Build me a business intelligence dashboard",
    ],
    "event_campaign": [
        "We want to run a {event} campaign",
        "I want to do something special for {event}",
        "Help me plan a themed campaign for {event}",
        "We need a seasonal promotion for {event}",
        "I want to create a campaign around {event}",
        "Let's do a big push for {event}",
        "We have {event} coming up and want to make it special",
        "Plan a promotional campaign for {event}",
    ],
    "saas_product": [
        "I want to build a SaaS for {purpose}",
        "We're creating a software product that {purpose}",
        "Help me plan a SaaS platform for {purpose}",
        "I need to build a web app that solves {purpose}",
        "We want to create a subscription service for {purpose}",
        "I have an idea for a product that {purpose}",
        "Help me build a platform for {purpose}",
        "We're creating a cloud-based tool for {purpose}",
    ],
    "social_media": [
        "I need a social media strategy for my {business}",
        "Help me plan our social media presence",
        "We want to grow on Instagram and TikTok",
        "I need to manage social media for {business}",
        "How should we approach social media for {business}?",
        "We need a content plan for social media",
        "Help me create a social media calendar for {business}",
        "We want to build a strong social media brand",
    ],
    "api_backend": [
        "I need to build an API for {purpose}",
        "Help me design a backend service for {purpose}",
        "We need a RESTful API that {purpose}",
        "I want to build a microservice for {purpose}",
        "We need a backend that handles {purpose}",
        "I need to create an API endpoint for {purpose}",
        "Help me architect a backend system for {purpose}",
    ],
    "video_production": [
        "I need a video for {purpose}",
        "We want to create a promotional video for {product}",
        "Help me produce a {type} video",
        "I need a product demo video for {product}",
        "We want to make tutorial videos for {product}",
        "I need a brand video for my {business}",
        "Help me create video content for social media",
        "We need an explainer video for our {business}",
    ],
    "email_marketing": [
        "I want to set up email marketing for {business}",
        "Help me create an email newsletter for {business}",
        "We need automated email sequences",
        "I want to start sending marketing emails for {business}",
        "Help me build an email list for {business}",
        "We need email campaigns for our {business}",
        "I want to improve our email marketing strategy",
        "Set up drip campaigns and email automation for us",
        "We need a full email marketing setup",
    ],
    "chatbot_ai": [
        "I want to build a chatbot for {purpose}",
        "We need an AI assistant for our {business}",
        "Help me create a customer service bot",
        "I want an AI chatbot on our website",
        "We need a bot that handles {purpose}",
        "Help me build an AI assistant for {purpose}",
        "I want to automate customer support with AI",
        "We need a conversational AI for our {business}",
    ],
    "ux_redesign": [
        "Our website UX needs improvement",
        "Help me redesign the user experience for {product}",
        "We need to fix the UX on our {product}",
        "I want to improve the usability of our app",
        "Our users are struggling with {problem}",
        "We need a UX audit and redesign",
        "Help me make our product easier to use",
        "Our conversion rate is low — think it's a UX issue",
    ],
}

# Multi-task prompt templates
MULTI_TASK_PROMPTS = [
    "I need a website update and email marketing setup for my {business}",
    "We want a new website plus a social media strategy for {business}",
    "Help me build an online store and run a marketing campaign for {product}",
    "I need branding, a website, and email marketing for my new {business}",
    "We want to build an app and set up a marketing campaign for {purpose}",
    "I need a website redesign and content strategy for my {business}",
    "Help me with video production and social media for promoting {product}",
    "We need a chatbot plus email automation for our {business}",
    "I want to build a SaaS and create content marketing for {purpose}",
    "We need UX improvements and a marketing campaign for our {product}",
]

MULTI_TASK_CATEGORIES = [
    ["web_development", "email_marketing"],
    ["web_development", "social_media"],
    ["ecommerce", "marketing_campaign"],
    ["design_branding", "web_development", "email_marketing"],
    ["mobile_app", "marketing_campaign"],
    ["web_development", "content_creation"],
    ["video_production", "social_media"],
    ["chatbot_ai", "email_marketing"],
    ["saas_product", "content_creation"],
    ["ux_redesign", "marketing_campaign"],
]

# Fill-in values for template variables
BUSINESSES = [
    "bakery", "restaurant", "fitness studio", "consulting firm", "law firm",
    "photography studio", "dental clinic", "real estate agency", "salon",
    "tech startup", "clothing brand", "coffee shop", "gym", "school",
    "nonprofit", "architecture firm", "travel agency", "pet shop",
    "accounting firm", "yoga studio", "craft brewery", "flower shop",
    "cleaning service", "tutoring center", "music school",
]
PRODUCTS = [
    "handmade candles", "organic skincare", "fitness equipment", "online courses",
    "supplements", "children's clothing", "artisan jewelry", "home decor",
    "meal kits", "sustainable fashion", "tech accessories", "subscription boxes",
    "custom furniture", "athletic wear", "natural cosmetics", "plant-based food",
]
EVENTS = [
    "International Women's Day", "Valentine's Day", "Christmas", "Black Friday",
    "Easter", "Halloween", "New Year", "Summer Sale", "Back to School",
    "Mother's Day", "Father's Day", "Earth Day", "Cyber Monday",
    "Spring Collection Launch", "Anniversary Sale",
]
PURPOSES = [
    "scheduling appointments", "managing inventory", "tracking fitness goals",
    "learning languages", "managing projects", "automating workflows",
    "connecting freelancers with clients", "tracking expenses",
    "managing recipes", "organizing events", "finding parking",
    "team collaboration", "customer onboarding", "tracking habits",
]
TOPICS = [
    "health and wellness", "technology trends", "sustainable living",
    "personal finance", "cooking and recipes", "travel destinations",
    "fashion and style", "parenting tips", "productivity hacks",
    "digital marketing", "entrepreneurship",
]
METRICS = [
    "sales performance", "user engagement", "marketing ROI",
    "customer acquisition", "revenue growth", "website traffic",
    "customer satisfaction", "conversion rates",
]
TYPES = ["portfolio", "corporate", "landing page", "marketplace", "blog",
         "explainer", "testimonial", "how-to", "social", "comparison"]
DATA = ["sales", "marketing", "customer", "product", "financial", "operational"]
PROBLEMS = ["checkout", "navigation", "onboarding", "search", "account settings",
            "mobile experience", "form submission"]


def fill_template(template: str) -> str:
    """Fill a template with random values."""
    result = template
    result = result.replace("{business}", random.choice(BUSINESSES))
    result = result.replace("{product}", random.choice(PRODUCTS))
    result = result.replace("{event}", random.choice(EVENTS))
    result = result.replace("{purpose}", random.choice(PURPOSES))
    result = result.replace("{topic}", random.choice(TOPICS))
    result = result.replace("{metrics}", random.choice(METRICS))
    result = result.replace("{type}", random.choice(TYPES))
    result = result.replace("{data}", random.choice(DATA))
    result = result.replace("{problem}", random.choice(PROBLEMS))
    return result


def generate_sft_pairs():
    """Generate SFT training pairs."""
    # Load missions
    missions = []
    with open(MISSIONS_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                missions.append(json.loads(line))

    pairs = []
    mission_map = {m["category"]: m for m in missions}

    # Single-task pairs: 25 per category
    for mission in missions:
        category = mission["category"]
        elements = mission["elements"]
        templates = USER_PROMPTS.get(category, [])

        for _ in range(25):
            if templates:
                prompt = fill_template(random.choice(templates))
            else:
                prompt = f"I need help with {mission['task'].lower()}"

            element_output = [
                {
                    "name": elem["name"],
                    "score": elem["score"],
                    "description": elem["description"],
                }
                for elem in elements
            ]

            pairs.append({
                "input": prompt,
                "category": category,
                "categories": [category],
                "output": element_output,
            })

    # Multi-task pairs
    for i, prompt_template in enumerate(MULTI_TASK_PROMPTS):
        cats = MULTI_TASK_CATEGORIES[i % len(MULTI_TASK_CATEGORIES)]
        for _ in range(10):
            prompt = fill_template(prompt_template)

            # Merge elements from all categories
            seen = {}
            for cat in cats:
                if cat in mission_map:
                    for elem in mission_map[cat]["elements"]:
                        if elem["name"] not in seen or elem["score"] > seen[elem["name"]]["score"]:
                            seen[elem["name"]] = elem

            element_output = [
                {"name": e["name"], "score": e["score"], "description": e["description"]}
                for e in sorted(seen.values(), key=lambda x: x["score"], reverse=True)
            ]

            pairs.append({
                "input": prompt,
                "category": cats[0],
                "categories": cats,
                "output": element_output,
            })

    # Write output
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        for pair in pairs:
            f.write(json.dumps(pair) + "\n")

    single = [p for p in pairs if len(p.get("categories", [])) <= 1]
    multi = [p for p in pairs if len(p.get("categories", [])) > 1]
    print(f"✅ Generated {len(pairs)} SFT training pairs")
    print(f"   Single-task: {len(single)}, Multi-task: {len(multi)}")
    print(f"📄 Saved to: {OUTPUT_PATH}")
    print(f"📊 Categories: {len(missions)}")
    return pairs


if __name__ == "__main__":
    generate_sft_pairs()
