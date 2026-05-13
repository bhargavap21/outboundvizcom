"""
Verify Apify API key and all four actor IDs before first production run.
Checks actor existence and build status — does NOT trigger any paid runs.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from apify_client import ApifyClient

ACTORS = {
    "LinkedIn Jobs":   os.environ.get("APIFY_ACTOR_LINKEDIN_JOBS",  "bebity/linkedin-jobs-scraper"),
    "LinkedIn Posts":  os.environ.get("APIFY_ACTOR_LINKEDIN_POSTS", "data-slayer/linkedin-company-posts-scraper"),
    "Behance":         os.environ.get("APIFY_ACTOR_BEHANCE",        "easyapi/behance-people-scraper"),
    # ArtStation omitted — no reliable actor available
}

def main():
    api_key = os.environ.get("APIFY_API_KEY", "")
    if not api_key:
        print("❌  APIFY_API_KEY is not set")
        sys.exit(1)

    client = ApifyClient(api_key)

    # Verify the API key by fetching the authenticated user
    try:
        user = client.user("me").get()
        print(f"✅  Apify auth OK  —  account: {user.get('username', 'unknown')}\n")
    except Exception as e:
        print(f"❌  Apify auth failed: {e}")
        sys.exit(1)

    all_ok = True
    for label, actor_id in ACTORS.items():
        try:
            info = client.actor(actor_id).get()
            if info is None:
                print(f"❌  {label:20s}  [{actor_id}]  — not found")
                all_ok = False
                continue

            name     = info.get("name", "?")
            username = info.get("username", "?")
            version  = (info.get("versions") or [{}])[-1].get("versionNumber", "?")
            status   = (info.get("versions") or [{}])[-1].get("buildTag", "latest")
            print(f"✅  {label:20s}  [{actor_id}]  — v{version} / {status}")

        except Exception as e:
            print(f"❌  {label:20s}  [{actor_id}]  — error: {e}")
            all_ok = False

    print()
    if all_ok:
        print("All actors verified. Ready to run signal detection.")
    else:
        print("One or more actors not found. Update the actor IDs in config/settings.py")
        print("or set the override env vars (see .env.example).")
        sys.exit(1)

if __name__ == "__main__":
    main()
