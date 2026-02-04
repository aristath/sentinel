#!/usr/bin/env python3
"""
Verification script for Advanced Quantitative Finance Integration.
Run this to check installation and data availability.
"""

import asyncio
import sys

import aiosqlite


async def verify_setup():
    """Verify advanced analytics setup."""
    print("=" * 70)
    print("   ADVANCED ANALYTICS VERIFICATION")
    print("=" * 70)
    print()

    all_good = True

    # 1. Check dependencies
    print("1. Checking dependencies...")
    try:
        import hmmlearn
        import sklearn

        print(f"   ✓ hmmlearn: {hmmlearn.__version__}")
        print(f"   ✓ scikit-learn: {sklearn.__version__}")
    except ImportError as e:
        print(f"   ✗ Missing dependency: {e}")
        all_good = False
    print()

    # 2. Check database tables
    print("2. Checking database tables...")
    try:
        db = await aiosqlite.connect("data/sentinel.db")

        tables = ["regime_states", "regime_models", "correlation_matrices"]

        for table in tables:
            cursor = await db.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
            count = (await cursor.fetchone())[0]
            print(f"   ✓ {table}: {count} records")
            if count == 0 and table in ["correlation_matrices", "regime_models"]:
                all_good = False
                print("     ⚠ No data - run first-time setup jobs!")

        await db.close()
    except Exception as e:
        print(f"   ✗ Database error: {e}")
        all_good = False
    print()

    # 3. Check settings
    print("3. Checking settings...")
    try:
        db = await aiosqlite.connect("data/sentinel.db")
        db.row_factory = aiosqlite.Row

        settings = [
            "use_regime_adjustment",
            "use_cleaned_correlation",
        ]

        for setting in settings:
            cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (setting,))
            row = await cursor.fetchone()
            value = row["value"] if row else "NOT SET"
            print(f"   • {setting}: {value}")

        await db.close()
    except Exception as e:
        print(f"   ✗ Settings error: {e}")
    print()

    # 4. Summary
    print("=" * 70)
    if all_good:
        print("   ✓ All systems operational!")
        print("   • Dependencies installed")
        print("   • Database tables created")
        print("   • Data populated")
    else:
        print("   ⚠ Some issues detected")
        print("   • Run first-time setup if data is missing")
        print("   • Check installation if dependencies missing")
    print("=" * 70)

    return all_good


if __name__ == "__main__":
    result = asyncio.run(verify_setup())
    sys.exit(0 if result else 1)
