"""
Horizon Europe Programme Scraper

Horizon Europe is the EU's key funding programme for research and innovation
with a budget of €95.5 billion for 2021-2027.

Framework Programme ID: 43108390

Fetches grants with status: Open, Forthcoming, and Closed
(matching the website filter)
"""

from ..eu_common import EUFundingTendersPipeline


def run(limit=None):
    """
    Run Horizon Europe scraper.

    Fetches all Open, Forthcoming, and Closed grants (matching website).

    Args:
        limit: Optional limit for testing (processes only first N grants)
    """
    pipeline = EUFundingTendersPipeline(
        query_filters={
            "programmePeriod": "2021 - 2027",
            "frameworkProgramme": ["43108390"],  # Horizon Europe
            "status": [
                "31094501",  # Forthcoming
                "31094502",  # Open
                "31094503",  # Closed
            ],
        },
        source_name="horizon_europe",
        out_dir="data/horizon_europe",
    )
    pipeline.run(limit=limit)


if __name__ == "__main__":
    run()
