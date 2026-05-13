"""
Seed the agency_list table with the 10 test agencies.
Run once; safe to re-run (upserts by name).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")

from db import init_db, get_session
from db.models import AgencyList

AGENCIES = [
    # name, slug, website, country, verticals, team_size_estimate
    ("Whipsaw",            "whipsaw-inc",          "https://whipsaw.com",              "US", ["consumer electronics", "footwear"],          22),
    ("Ammunition Group",   "ammunition-group",     "https://ammunitiongroup.com",       "US", ["consumer electronics", "home goods"],         25),
    ("Bould Design",       "bould-design",         "https://boulddesign.com",           "US", ["consumer electronics", "footwear"],          15),
    ("Layer",              "layer-design",         "https://layerdesign.com",           "UK", ["consumer electronics", "furniture"],          12),
    ("Morrama",            "morrama",              "https://morrama.com",               "UK", ["consumer electronics", "home goods"],         12),
    ("Priority Designs",   "priority-designs",     "https://prioritydesigns.com",       "US", ["consumer electronics", "home goods"],         20),
    ("Fuseproject",        "fuseproject",          "https://fuseproject.com",           "US", ["consumer electronics", "furniture"],          30),
    ("Ziba Design",        "ziba",                 "https://ziba.com",                  "US", ["consumer electronics", "furniture"],         100),
    ("Map Project Office", "map-project-office",   "https://map-projectoffice.com",     "UK", ["furniture", "consumer electronics"],          15),
    ("PDD",                "pdd-innovation",       "https://pdd.com",                   "UK", ["consumer electronics", "home goods"],         50),
]

init_db()
session = get_session()

with session:
    for name, slug, website, country, verticals, size in AGENCIES:
        existing = session.query(AgencyList).filter(AgencyList.name == name).first()
        if existing:
            existing.linkedin_slug = slug
            existing.linkedin_url = f"https://www.linkedin.com/company/{slug}/"
            existing.website = website
            existing.country = country
            existing.verticals = verticals
            existing.team_size_estimate = size
            print(f"  updated: {name}")
        else:
            session.add(AgencyList(
                name=name,
                linkedin_slug=slug,
                linkedin_url=f"https://www.linkedin.com/company/{slug}/",
                website=website,
                country=country,
                verticals=verticals,
                team_size_estimate=size,
                source="manual",
            ))
            print(f"  inserted: {name}")
    session.commit()

print(f"\nDone. {len(AGENCIES)} agencies in agency_list.")
