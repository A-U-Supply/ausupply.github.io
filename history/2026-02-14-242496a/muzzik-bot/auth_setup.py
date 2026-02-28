#!/usr/bin/env python3
"""One-time OAuth setup helper. Run locally to get a YouTube refresh token.

Usage:
    pip install google-auth-oauthlib requests
    python auth_setup.py --client-id YOUR_ID --client-secret YOUR_SECRET
"""

import argparse
import urllib.parse

import requests


SCOPES = ["https://www.googleapis.com/auth/youtube"]
# For Desktop/installed apps, Google pre-authorizes this redirect
REDIRECT_URI = "http://127.0.0.1"


def main():
    parser = argparse.ArgumentParser(description="Get YouTube OAuth refresh token")
    parser.add_argument("--client-id", required=True, help="OAuth client ID")
    parser.add_argument("--client-secret", required=True, help="OAuth client secret")
    args = parser.parse_args()

    # Build the authorization URL
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": args.client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    })

    print("\n1. Open this URL in your browser:\n")
    print(auth_url)
    print("\n2. Log in and grant permission.")
    print("3. Your browser will redirect to a page that WON'T LOAD (that's fine).")
    print("4. Copy the FULL URL from your browser's address bar and paste it below.\n")

    redirect_url = input("Paste the URL here: ").strip()

    # Extract the authorization code from the redirected URL
    parsed = urllib.parse.urlparse(redirect_url)
    params = urllib.parse.parse_qs(parsed.query)

    if "code" not in params:
        print(f"\nError: No authorization code found in URL.")
        if "error" in params:
            print(f"Error from Google: {params['error'][0]}")
        return

    code = params["code"][0]

    # Exchange the code for tokens
    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code,
        "client_id": args.client_id,
        "client_secret": args.client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    })

    if resp.status_code != 200:
        print(f"\nError exchanging code for tokens: {resp.text}")
        return

    tokens = resp.json()
    refresh_token = tokens.get("refresh_token")

    if not refresh_token:
        print(f"\nNo refresh token in response: {tokens}")
        return

    print("\n--- Save this refresh token as a GitHub secret (YOUTUBE_REFRESH_TOKEN) ---")
    print(refresh_token)
    print("------------------------------------------------------------------------\n")


if __name__ == "__main__":
    main()
