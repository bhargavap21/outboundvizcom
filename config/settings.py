import os
from dotenv import load_dotenv

load_dotenv()

# Anthropic
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL_CONTENT = "claude-sonnet-4-20250514"   # emails, DMs, learning loop
MODEL_SCORING = "claude-haiku-4-5"           # classification, scoring (high-volume)

# SendGrid
SENDGRID_API_KEY = os.environ["SENDGRID_API_KEY"]
OUTBOUND_EMAIL_FROM = os.environ["OUTBOUND_EMAIL_FROM"]

# Apify
APIFY_API_KEY = os.environ.get("APIFY_API_KEY", "")

# Apify actor IDs — verify each at https://apify.com/store before first run
# Override via env var if you want to swap to a different actor
APIFY_ACTOR_LINKEDIN_JOBS = os.environ.get(
    "APIFY_ACTOR_LINKEDIN_JOBS", "bebity/linkedin-jobs-scraper"
)
APIFY_ACTOR_LINKEDIN_POSTS = os.environ.get(
    "APIFY_ACTOR_LINKEDIN_POSTS", "apimaestro/linkedin-company-posts-scraper"
)
APIFY_ACTOR_BEHANCE = os.environ.get(
    "APIFY_ACTOR_BEHANCE", "apify/behance-scraper"
)
APIFY_ACTOR_ARTSTATION = os.environ.get(
    "APIFY_ACTOR_ARTSTATION", "apify/artstation-scraper"
)

# Max results per agency per Apify run (controls cost)
APIFY_JOBS_MAX_RESULTS = int(os.environ.get("APIFY_JOBS_MAX_RESULTS", "25"))
APIFY_POSTS_MAX_RESULTS = int(os.environ.get("APIFY_POSTS_MAX_RESULTS", "10"))
APIFY_PORTFOLIO_MAX_RESULTS = int(os.environ.get("APIFY_PORTFOLIO_MAX_RESULTS", "5"))

# Phantombuster
PHANTOMBUSTER_API_KEY = os.environ.get("PHANTOMBUSTER_API_KEY", "")
LINKEDIN_SESSION_COOKIE = os.environ.get("LINKEDIN_SESSION_COOKIE", "")

# Google News
GOOGLE_NEWS_API_KEY = os.environ.get("GOOGLE_NEWS_API_KEY", "")

# HubSpot
HUBSPOT_API_KEY = os.environ.get("HUBSPOT_API_KEY", "")

# Database
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///vizcom_gtm.db")

# Slack
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

# Rate limits (per spec)
EMAIL_DAILY_LIMIT = 40
LINKEDIN_CONNECT_DAILY_LIMIT = 20
EMAIL_SEND_HOUR_START = 8   # recipient local time
EMAIL_SEND_HOUR_END = 11

# Scheduling
SIGNAL_DETECTION_HOUR = int(os.environ.get("SIGNAL_DETECTION_HOUR", 6))

# Lead scoring thresholds
SCORE_PROCEED = 65
SCORE_WATCHLIST = 40

# Outreach suppression
DEDUP_WINDOW_DAYS = 14
COOLING_PERIOD_DAYS = 90

# LinkedIn DM sequence timing
DM_DAY_1 = 3
DM_DAY_2 = 7
DM_DAY_3 = 14
