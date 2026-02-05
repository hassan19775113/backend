#!/usr/bin/env python3
"""
Hilfsskript zum Generieren eines Django Secret Keys für Vercel Deployment
"""

import secrets
import string


def generate_secret_key(length=50):
    """Generiert einen sicheren Secret Key für Django"""
    chars = string.ascii_letters + string.digits + "!@#$%^&*(-_=+)"
    return "".join(secrets.choice(chars) for _ in range(length))


if __name__ == "__main__":
    secret_key = generate_secret_key()
    print("\n" + "=" * 70)
    print("DJANGO SECRET KEY FÜR VERCEL DEPLOYMENT")
    print("=" * 70)
    print(f"\n{secret_key}\n")
    print("=" * 70)
    print("\n📋 Kopieren Sie diesen Key und fügen Sie ihn in Vercel hinzu:")
    print("   Vercel Dashboard → Settings → Environment Variables")
    print("   Name: DJANGO_SECRET_KEY")
    print(f"   Value: {secret_key}")
    print("\n⚠️  WICHTIG: Teilen Sie diesen Key niemals öffentlich!")
    print("=" * 70 + "\n")
