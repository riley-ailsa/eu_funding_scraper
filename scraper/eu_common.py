from __future__ import annotations
from typing import Dict, Any, List, Optional
import requests
import json
import re
from datetime import datetime

from .base import FundingBodyPipeline, NormalizedGrant

# CORRECT API endpoint
BASE_API_URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"

TOPIC_URL_TEMPLATE = (
    "https://ec.europa.eu/info/funding-tenders/opportunities/"
    "portal/screen/opportunities/topic-details/{call_id}"
)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AskAilsaScraper/1.0)",
}


class EUFundingTendersPipeline(FundingBodyPipeline):
    """
    Shared pipeline for EU Funding & Tenders Portal.
    Handles both Horizon Europe and Digital Europe Programme.

    Uses the EC Search API with POST requests and Elasticsearch-style queries.
    """

    def __init__(
        self,
        query_filters: Dict[str, Any],  # Changed from base_params
        source_name: str,
        out_dir: str,
        delay: float = 0.8
    ):
        self._query_filters = query_filters
        self._source_name = source_name
        super().__init__(out_dir=out_dir, delay=delay)

    @property
    def source_name(self) -> str:
        return self._source_name

    def _build_query(self) -> Dict[str, Any]:
        """
        Build Elasticsearch-style query from filters.

        Example filters:
        {
            "type": ["1", "2"],  # Call types
            "status": ["31094501"],  # Open calls
            "programmePeriod": "2021 - 2027",
            "frameworkProgramme": ["43108390"],  # Horizon Europe
        }
        """
        must_clauses = []

        for key, value in self._query_filters.items():
            if isinstance(value, list):
                # Multiple values = "terms" query
                must_clauses.append({"terms": {key: value}})
            else:
                # Single value = "term" query
                must_clauses.append({"term": {key: value}})

        return {
            "bool": {
                "must": must_clauses
            }
        }

    def fetch_index(self) -> List[Dict[str, Any]]:
        """
        Fetch all grants from the EU API with pagination.
        Uses POST requests with multipart form data.
        """
        all_items: List[Dict[str, Any]] = []
        page = 1

        # Build query once
        query = self._build_query()

        # Sort configuration
        sort = {"field": "sortStatus", "order": "ASC"}

        # Languages
        languages = ["en"]

        while True:
            self.logger.info(f"Fetching index page {page}...")

            # API parameters
            params = {
                "apiKey": "SEDIA",
                "text": "***",  # Wildcard to get all
                "pageSize": "100",  # Max per page
                "pageNumber": str(page)
            }

            try:
                # POST request with multipart form data
                resp = requests.post(
                    BASE_API_URL,
                    params=params,
                    files={
                        "query": ("blob", json.dumps(query), "application/json"),
                        "languages": ("blob", json.dumps(languages), "application/json"),
                        "sort": ("blob", json.dumps(sort), "application/json"),
                    },
                    headers=DEFAULT_HEADERS,
                    timeout=40,
                )
                resp.raise_for_status()

                self.audit.log_event("api_request", {
                    "url": BASE_API_URL,
                    "page": page,
                    "status_code": resp.status_code,
                    "response_size": len(resp.content)
                })

                data = resp.json()

            except requests.RequestException as e:
                self.logger.error(f"API request failed on page {page}: {e}")
                self.audit.log_event("api_error", {
                    "page": page,
                    "error": str(e)
                })
                raise

            # Extract results
            results = data.get("results", [])
            if not results:
                self.logger.info(f"No more results at page {page}. Stopping.")
                break

            all_items.extend(results)

            # Check pagination
            total_results = data.get("totalResults", 0)
            total_pages = (total_results + 99) // 100  # Ceiling division

            self.logger.info(
                f"Page {page}/{total_pages}: "
                f"fetched {len(results)} items (total: {len(all_items)}/{total_results})"
            )

            page += 1

            # Safety check
            if page > 500:  # Reasonable limit
                self.logger.warning("Hit safety limit of 500 pages. Stopping.")
                break

        return all_items

    def extract_ids(self, index_records: List[Dict[str, Any]]) -> List[str]:
        """
        Extract unique grant IDs from index records.

        Uses reference as the unique identifier. This is the actual unique ID
        for each funding opportunity. Both callccm2Id and metadata.identifier
        can be shared across multiple opportunities (e.g., cascading grants, FSTP programs).

        API results structure:
        {
            "reference": "10381COMPETITIVE_CALLen",  # ALWAYS unique per opportunity
            "content": "Title",
            "metadata": {
                "callccm2Id": ["10381"],  # Can be shared (parent call)
                "identifier": ["DIGITAL-..."],  # Can be shared (parent call)
                ...
            },
            "url": "..."
        }
        """
        ids: List[str] = []

        for item in index_records:
            # Use reference as the primary unique ID (always unique per opportunity)
            reference = item.get("reference")
            if reference:
                call_id = reference
            else:
                # Fallback to callccm2Id if reference is missing
                metadata = item.get("metadata", {})
                call_ccm2_id = metadata.get("callccm2Id")
                if call_ccm2_id:
                    if isinstance(call_ccm2_id, list) and len(call_ccm2_id) > 0:
                        call_id = call_ccm2_id[0]
                    else:
                        call_id = call_ccm2_id
                else:
                    # Last resort: use metadata.identifier (but this can duplicate)
                    identifier_field = metadata.get("identifier")
                    if identifier_field:
                        if isinstance(identifier_field, list) and len(identifier_field) > 0:
                            call_id = identifier_field[0]
                        else:
                            call_id = identifier_field
                    else:
                        call_id = None

            if call_id:
                ids.append(str(call_id))

        self.logger.info(f"Extracted {len(ids)} IDs from {len(index_records)} records")

        return ids

    def fetch_detail_html(self, grant_id: str) -> str:
        """
        Fetch the HTML detail page for a specific grant.
        """
        url = TOPIC_URL_TEMPLATE.format(call_id=grant_id)

        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=40)
            resp.raise_for_status()

            self.audit.log_event("detail_fetch", {
                "grant_id": grant_id,
                "url": url,
                "status_code": resp.status_code,
                "size": len(resp.text)
            })

            return resp.text

        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch detail for {grant_id}: {e}")
            self.audit.log_event("detail_fetch_error", {
                "grant_id": grant_id,
                "url": url,
                "error": str(e)
            })
            raise

    def normalize(
        self,
        grant_id: str,
        index_record: Dict[str, Any],
        html: Optional[str],
    ) -> NormalizedGrant:
        """
        Normalize EU grant data into standard format.

        API record structure:
        {
            "identifier": "CALL-ID",
            "content": "Title",
            "metadata": {
                "status": "Open",
                "programme": "...",
                "deadlines": [...],
                ...
            },
            "url": "..."
        }
        """
        # Extract metadata
        metadata = index_record.get("metadata", {})

        # Extract title - API uses "content" field for the title
        title = index_record.get("content", "")

        # Fallback to other title fields if content is empty
        if not title:
            # callTitle is an array
            call_title = metadata.get("callTitle")
            if call_title:
                title = call_title[0] if isinstance(call_title, list) else call_title
            else:
                title = metadata.get("title") or metadata.get("titleEn") or ""

        title = self._clean_title(title)

        # Extract status
        status = metadata.get("status")

        # Extract programme
        programme = (
            metadata.get("programme")
            or metadata.get("programmeName")
            or metadata.get("fundingProgramme")
        )

        # Extract dates - metadata fields are usually arrays
        open_date = None
        close_date = None

        # Try deadlineDate first (common field, usually an array)
        deadline_date_field = metadata.get("deadlineDate")
        if deadline_date_field:
            if isinstance(deadline_date_field, list) and len(deadline_date_field) > 0:
                close_date = self._parse_date(deadline_date_field[0])
            else:
                close_date = self._parse_date(deadline_date_field)

        # Try opening date
        opening_date_field = metadata.get("openingDate") or metadata.get("startDate")
        if opening_date_field:
            if isinstance(opening_date_field, list) and len(opening_date_field) > 0:
                open_date = self._parse_date(opening_date_field[0])
            else:
                open_date = self._parse_date(opening_date_field)

        # Fallback to deadlines array if present
        if not close_date or not open_date:
            deadlines = metadata.get("deadlines", [])
            if deadlines and isinstance(deadlines, list) and len(deadlines) > 0:
                first_deadline = deadlines[0]
                if isinstance(first_deadline, dict):
                    if not open_date:
                        open_date = self._parse_date(first_deadline.get("startDate"))
                    if not close_date:
                        close_date = self._parse_date(first_deadline.get("date"))

        # Generate URL
        url = TOPIC_URL_TEMPLATE.format(call_id=grant_id)

        return NormalizedGrant(
            id=f"{self.source_name}:{grant_id}",
            source=self.source_name,
            title=title,
            url=url,
            status=str(status) if status is not None else None,
            programme=str(programme) if programme is not None else None,
            call_id=grant_id,
            open_date=open_date,
            close_date=close_date,
            raw=index_record,
        )

    def _clean_title(self, title: str) -> str:
        """Clean grant titles - remove excess whitespace, fix encoding issues."""
        if not title:
            return ""

        # Remove excess whitespace
        title = re.sub(r'\s+', ' ', title)
        title = title.strip()

        # Remove common encoding artifacts
        title = title.replace('\u00a0', ' ')  # Non-breaking space
        title = title.replace('\u200b', '')   # Zero-width space

        # Remove leading/trailing punctuation
        title = title.strip('- \t')

        return title

    def _parse_date(self, date_str: Optional[str]) -> Optional[str]:
        """Parse and normalize date strings to ISO format."""
        if not date_str:
            return None

        # If already in ISO format, validate and return
        try:
            if 'T' in date_str:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                return dt.isoformat()
        except ValueError:
            pass

        # Try common EU date formats
        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.date().isoformat()
            except ValueError:
                continue

        # If we can't parse it, log warning and return original
        self.logger.warning(f"Could not parse date: {date_str}")
        return date_str
