"""
Digital Europe Programme Scraper

Digital Europe Programme supports the digital transformation of Europe's
economy and society with a budget of €7.5 billion for 2021-2027.

Focus areas: supercomputing, AI, cybersecurity, advanced digital skills,
and deployment of digital technologies.

Framework Programme ID: 43152860

Fetches grants with status: Open, Forthcoming, and Closed
(matching the website filter)
"""

from ..eu_common import EUFundingTendersPipeline


def run(limit=None):
    """
    Run Digital Europe Programme scraper.

    Fetches all Open, Forthcoming, and Closed grants (matching website).

    Args:
        limit: Optional limit for testing (processes only first N grants)
    """
    pipeline = EUFundingTendersPipeline(
        query_filters={
            "programmePeriod": "2021 - 2027",
            "frameworkProgramme": ["43152860"],  # Digital Europe Programme
            "status": [
                "31094501",  # Forthcoming
                "31094502",  # Open
                "31094503",  # Closed
            ],
        },
        source_name="digital_europe",
        out_dir="data/digital_europe",
    )
    pipeline.run(limit=limit)


if __name__ == "__main__":
    run()
