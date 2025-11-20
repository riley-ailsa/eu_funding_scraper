"""
Digital Europe Programme (DIGITAL) Scraper - OPEN GRANTS ONLY

Framework Programme ID: 43252197

This version ONLY fetches grants with status: Open
"""

from ..eu_common import EUFundingTendersPipeline


def run(limit=None):
    """
    Run Digital Europe scraper for OPEN grants only.

    Args:
        limit: Optional limit for testing (processes only first N grants)
    """
    pipeline = EUFundingTendersPipeline(
        query_filters={
            "programmePeriod": "2021 - 2027",
            "frameworkProgramme": ["43252197"],  # Digital Europe
            "status": [
                "31094502",  # Open ONLY
            ],
        },
        source_name="digital_europe",
        out_dir="data/digital_europe",
    )
    pipeline.run(limit=limit)


if __name__ == "__main__":
    run()
