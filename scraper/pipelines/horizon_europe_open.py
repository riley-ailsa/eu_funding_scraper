"""
Horizon Europe Programme Scraper - OPEN GRANTS ONLY

Horizon Europe is the EU's key funding programme for research and innovation
with a budget of €95.5 billion for 2021-2027.

Framework Programme ID: 43108390

This version ONLY fetches grants with status: Open
"""

from ..eu_common import EUFundingTendersPipeline


def run(limit=None):
    """
    Run Horizon Europe scraper for OPEN grants only.

    Args:
        limit: Optional limit for testing (processes only first N grants)
    """
    pipeline = EUFundingTendersPipeline(
        query_filters={
            "programmePeriod": "2021 - 2027",
            "frameworkProgramme": ["43108390"],  # Horizon Europe
            "status": [
                "31094502",  # Open ONLY
            ],
        },
        source_name="horizon_europe",
        out_dir="data/horizon_europe",
    )
    pipeline.run(limit=limit)


if __name__ == "__main__":
    run()
