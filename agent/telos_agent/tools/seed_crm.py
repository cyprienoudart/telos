"""Seed Twenty CRM with demo data via REST API.

Standalone CLI tool that populates a Twenty CRM instance with realistic
companies, people, and opportunities for demo/testing purposes.

Usage:
    uv run python -m telos_agent.tools.seed_crm --base-url http://localhost:3020
"""

import argparse
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# ── Demo Data ──────────────────────────────────────────────────────────────

COMPANIES = [
    {"name": "Apex Technologies", "domain": "apextech.io", "employees": 120},
    {"name": "Lumina Fashion", "domain": "luminafashion.com", "employees": 45},
    {"name": "Granite Capital", "domain": "granitecap.com", "employees": 200},
    {"name": "Pixel & Pulse Marketing", "domain": "pixelpulse.agency", "employees": 30},
    {"name": "Verdant Health", "domain": "verdanthealth.org", "employees": 85},
    {"name": "Atlas Logistics", "domain": "atlaslogistics.co", "employees": 300},
    {"name": "Neon Studios", "domain": "neonstudios.dev", "employees": 15},
    {"name": "Cascade Financial", "domain": "cascadefin.com", "employees": 150},
    {"name": "Bloom & Grow Retail", "domain": "bloomgrow.shop", "employees": 60},
    {"name": "Stratos Consulting", "domain": "stratosconsulting.com", "employees": 95},
]

# ~15 women, ~15 men — spread across companies (index into COMPANIES list)
PEOPLE = [
    # Women
    {"first": "Sarah", "last": "Johnson", "email": "sarah.johnson@apextech.io", "phone": "+1-415-555-0101", "company": 0, "city": "San Francisco"},
    {"first": "Maria", "last": "Garcia", "email": "maria.garcia@luminafashion.com", "phone": "+1-212-555-0102", "company": 1, "city": "New York"},
    {"first": "Priya", "last": "Patel", "email": "priya.patel@granitecap.com", "phone": "+1-312-555-0103", "company": 2, "city": "Chicago"},
    {"first": "Aisha", "last": "Williams", "email": "aisha.williams@pixelpulse.agency", "phone": "+1-310-555-0104", "company": 3, "city": "Los Angeles"},
    {"first": "Elena", "last": "Kowalski", "email": "elena.kowalski@verdanthealth.org", "phone": "+1-617-555-0105", "company": 4, "city": "Boston"},
    {"first": "Yuki", "last": "Tanaka", "email": "yuki.tanaka@atlaslogistics.co", "phone": "+1-206-555-0106", "company": 5, "city": "Seattle"},
    {"first": "Fatima", "last": "Al-Rashid", "email": "fatima.alrashid@neonstudios.dev", "phone": "+1-512-555-0107", "company": 6, "city": "Austin"},
    {"first": "Olivia", "last": "Chen", "email": "olivia.chen@cascadefin.com", "phone": "+1-303-555-0108", "company": 7, "city": "Denver"},
    {"first": "Amara", "last": "Okafor", "email": "amara.okafor@bloomgrow.shop", "phone": "+1-404-555-0109", "company": 8, "city": "Atlanta"},
    {"first": "Sophie", "last": "Dubois", "email": "sophie.dubois@stratosconsulting.com", "phone": "+1-202-555-0110", "company": 9, "city": "Washington DC"},
    {"first": "Lin", "last": "Wei", "email": "lin.wei@apextech.io", "phone": "+1-415-555-0111", "company": 0, "city": "San Francisco"},
    {"first": "Isabella", "last": "Rossi", "email": "isabella.rossi@granitecap.com", "phone": "+1-312-555-0112", "company": 2, "city": "Chicago"},
    {"first": "Nadia", "last": "Petrova", "email": "nadia.petrova@atlaslogistics.co", "phone": "+1-206-555-0113", "company": 5, "city": "Seattle"},
    {"first": "Carmen", "last": "Reyes", "email": "carmen.reyes@pixelpulse.agency", "phone": "+1-310-555-0114", "company": 3, "city": "Los Angeles"},
    {"first": "Hannah", "last": "Schmidt", "email": "hannah.schmidt@verdanthealth.org", "phone": "+1-617-555-0115", "company": 4, "city": "Boston"},
    # Men
    {"first": "James", "last": "Mitchell", "email": "james.mitchell@apextech.io", "phone": "+1-415-555-0201", "company": 0, "city": "San Francisco"},
    {"first": "Carlos", "last": "Rodriguez", "email": "carlos.rodriguez@luminafashion.com", "phone": "+1-212-555-0202", "company": 1, "city": "New York"},
    {"first": "David", "last": "Kim", "email": "david.kim@granitecap.com", "phone": "+1-312-555-0203", "company": 2, "city": "Chicago"},
    {"first": "Omar", "last": "Hassan", "email": "omar.hassan@pixelpulse.agency", "phone": "+1-310-555-0204", "company": 3, "city": "Los Angeles"},
    {"first": "Ryan", "last": "O'Brien", "email": "ryan.obrien@verdanthealth.org", "phone": "+1-617-555-0205", "company": 4, "city": "Boston"},
    {"first": "Kenji", "last": "Yamamoto", "email": "kenji.yamamoto@atlaslogistics.co", "phone": "+1-206-555-0206", "company": 5, "city": "Seattle"},
    {"first": "Lucas", "last": "Martin", "email": "lucas.martin@neonstudios.dev", "phone": "+1-512-555-0207", "company": 6, "city": "Austin"},
    {"first": "Alexander", "last": "Novak", "email": "alexander.novak@cascadefin.com", "phone": "+1-303-555-0208", "company": 7, "city": "Denver"},
    {"first": "Benjamin", "last": "Taylor", "email": "benjamin.taylor@bloomgrow.shop", "phone": "+1-404-555-0209", "company": 8, "city": "Atlanta"},
    {"first": "Marcus", "last": "Hughes", "email": "marcus.hughes@stratosconsulting.com", "phone": "+1-202-555-0210", "company": 9, "city": "Washington DC"},
    {"first": "Raj", "last": "Sharma", "email": "raj.sharma@apextech.io", "phone": "+1-415-555-0211", "company": 0, "city": "San Francisco"},
    {"first": "Thomas", "last": "Andersen", "email": "thomas.andersen@granitecap.com", "phone": "+1-312-555-0212", "company": 2, "city": "Chicago"},
    {"first": "Wei", "last": "Zhang", "email": "wei.zhang@atlaslogistics.co", "phone": "+1-206-555-0213", "company": 5, "city": "Seattle"},
    {"first": "Daniel", "last": "Foster", "email": "daniel.foster@cascadefin.com", "phone": "+1-303-555-0214", "company": 7, "city": "Denver"},
    {"first": "Miguel", "last": "Santos", "email": "miguel.santos@bloomgrow.shop", "phone": "+1-404-555-0215", "company": 8, "city": "Atlanta"},
]

# 20 opportunities — (person_index, stage, amount, name)
# Stages: PROSPECTING, QUALIFICATION, PROPOSAL, NEGOTIATION, WON, LOST
# Won: at least 3 linked to women contacts (indices 0-14)
OPPORTUNITIES = [
    # Prospecting (4)
    (15, "PROSPECTING", 25000, "Apex Tech — Platform Upgrade"),
    (1, "PROSPECTING", 18000, "Lumina Fashion — Brand Refresh"),
    (20, "PROSPECTING", 42000, "Apex Tech — Data Migration"),
    (5, "PROSPECTING", 31000, "Atlas Logistics — Fleet Tracking"),
    # Qualification (4)
    (3, "QUALIFICATION", 15000, "Pixel & Pulse — Social Campaign"),
    (17, "QUALIFICATION", 55000, "Granite Capital — Risk Dashboard"),
    (6, "QUALIFICATION", 12000, "Neon Studios — MVP Build"),
    (24, "QUALIFICATION", 28000, "Bloom & Grow — E-commerce Relaunch"),
    # Proposal (3)
    (4, "PROPOSAL", 35000, "Verdant Health — Patient Portal"),
    (22, "PROPOSAL", 48000, "Cascade Financial — Compliance Tool"),
    (9, "PROPOSAL", 60000, "Stratos Consulting — CRM Integration"),
    # Negotiation (3)
    (16, "NEGOTIATION", 72000, "Lumina Fashion — Seasonal Campaign"),
    (10, "NEGOTIATION", 38000, "Apex Tech — API Gateway"),
    (27, "NEGOTIATION", 90000, "Atlas Logistics — Warehouse Automation"),
    # Won (4) — at least 3 linked to women
    (0, "WON", 85000, "Apex Tech — Enterprise Deal"),       # Sarah Johnson (woman)
    (2, "WON", 120000, "Granite Capital — Portfolio Platform"), # Priya Patel (woman)
    (7, "WON", 65000, "Cascade Financial — Trading Dashboard"), # Olivia Chen (woman)
    (8, "WON", 45000, "Bloom & Grow — Loyalty Program"),     # Amara Okafor (woman)
    # Lost (2)
    (19, "LOST", 22000, "Verdant Health — Telemedicine Pilot"),
    (25, "LOST", 33000, "Stratos Consulting — Audit Automation"),
]


# ── API helpers ────────────────────────────────────────────────────────────

def _headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def create_company(client: httpx.Client, base_url: str, api_key: str, data: dict) -> str:
    """Create a company, return its ID."""
    payload = {
        "name": {"firstName": data["name"], "lastName": ""},
        "domainName": {"primaryLinkUrl": data["domain"]},
        "employees": data["employees"],
    }
    resp = client.post(f"{base_url}/rest/companies", headers=_headers(api_key), json=payload)
    resp.raise_for_status()
    return resp.json()["data"]["id"]


def create_person(client: httpx.Client, base_url: str, api_key: str, data: dict, company_id: str) -> str:
    """Create a person linked to a company, return their ID."""
    payload = {
        "name": {"firstName": data["first"], "lastName": data["last"]},
        "emails": {"primaryEmail": data["email"]},
        "phones": {"primaryPhoneNumber": data["phone"]},
        "city": data["city"],
        "companyId": company_id,
    }
    resp = client.post(f"{base_url}/rest/people", headers=_headers(api_key), json=payload)
    resp.raise_for_status()
    return resp.json()["data"]["id"]


def create_opportunity(
    client: httpx.Client, base_url: str, api_key: str,
    name: str, stage: str, amount: int, person_id: str, company_id: str,
) -> str:
    """Create an opportunity linked to a person and company, return its ID."""
    payload = {
        "name": name,
        "stage": stage,
        "amount": {"amountMicros": amount * 1_000_000, "currencyCode": "USD"},
        "pointOfContactId": person_id,
        "companyId": company_id,
    }
    resp = client.post(f"{base_url}/rest/opportunities", headers=_headers(api_key), json=payload)
    resp.raise_for_status()
    return resp.json()["data"]["id"]


# ── Main ───────────────────────────────────────────────────────────────────

def seed(base_url: str, api_key: str) -> dict:
    """Seed the CRM and return a summary dict."""
    summary = {"companies": [], "people": [], "opportunities": []}

    with httpx.Client(timeout=30.0) as client:
        # 1. Companies
        company_ids = []
        for comp in COMPANIES:
            cid = create_company(client, base_url, api_key, comp)
            company_ids.append(cid)
            summary["companies"].append({"id": cid, "name": comp["name"]})
            print(f"  Company: {comp['name']} → {cid}")

        # 2. People
        person_ids = []
        for person in PEOPLE:
            pid = create_person(client, base_url, api_key, person, company_ids[person["company"]])
            person_ids.append(pid)
            summary["people"].append({
                "id": pid,
                "name": f"{person['first']} {person['last']}",
                "email": person["email"],
                "company": COMPANIES[person["company"]]["name"],
            })
            print(f"  Person:  {person['first']} {person['last']} → {pid}")

        # 3. Opportunities
        for person_idx, stage, amount, name in OPPORTUNITIES:
            person = PEOPLE[person_idx]
            company_idx = person["company"]
            oid = create_opportunity(
                client, base_url, api_key,
                name=name, stage=stage, amount=amount,
                person_id=person_ids[person_idx],
                company_id=company_ids[company_idx],
            )
            summary["opportunities"].append({
                "id": oid,
                "name": name,
                "stage": stage,
                "amount": amount,
                "contact": f"{person['first']} {person['last']}",
            })
            print(f"  Opp:     {name} ({stage}, ${amount:,}) → {oid}")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed Twenty CRM with demo data (companies, people, opportunities)",
    )
    parser.add_argument(
        "--base-url", default="http://localhost:3020",
        help="Twenty CRM base URL (default: http://localhost:3020)",
    )
    parser.add_argument(
        "--api-key", default=None,
        help="Twenty API key (default: read from TWENTY_API_KEY env var)",
    )
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("TWENTY_API_KEY")
    if not api_key:
        print("Error: TWENTY_API_KEY not set. Pass --api-key or export TWENTY_API_KEY.", file=sys.stderr)
        sys.exit(1)

    print(f"Seeding CRM at {args.base_url} ...")
    try:
        summary = seed(args.base_url, api_key)
    except httpx.HTTPStatusError as e:
        print(f"HTTP error: {e.response.status_code} — {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except httpx.ConnectError:
        print(f"Connection failed. Is Twenty CRM running at {args.base_url}?", file=sys.stderr)
        sys.exit(1)

    print(f"\nDone! Created {len(summary['companies'])} companies, "
          f"{len(summary['people'])} people, {len(summary['opportunities'])} opportunities.")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
