from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import json
import time
import logging
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

@dataclass
class NormalizedGrant:
    id: str
    source: str
    title: str
    url: str
    status: Optional[str] = None
    programme: Optional[str] = None
    call_id: Optional[str] = None
    open_date: Optional[str] = None
    close_date: Optional[str] = None
    raw: Dict[str, Any] = None

    def __post_init__(self):
        if self.raw is None:
            self.raw = {}


class AuditLogger:
    """Tracks all operations with detailed logging"""

    def __init__(self, out_dir: Path):
        self.out_dir = out_dir
        self.log_file = out_dir / "audit_log.jsonl"
        self.stats = defaultdict(int)

    def log_event(self, event_type: str, details: Dict[str, Any]):
        """Append event to audit log"""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "details": details
        }
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
        self.stats[event_type] += 1

    def get_summary(self) -> Dict[str, Any]:
        """Return summary statistics"""
        return dict(self.stats)


class CheckpointManager:
    """Manages checkpoint state for crash recovery"""

    def __init__(self, out_dir: Path):
        self.checkpoint_file = out_dir / "checkpoint.json"
        self.state = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.checkpoint_file.exists():
            return json.loads(self.checkpoint_file.read_text(encoding='utf-8'))
        return {
            "completed_ids": [],
            "failed_ids": [],
            "last_index_fetch": None,
            "phase": "init"
        }

    def save(self):
        """Write checkpoint to disk"""
        self.checkpoint_file.write_text(
            json.dumps(self.state, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )

    def mark_completed(self, grant_id: str):
        if grant_id not in self.state["completed_ids"]:
            self.state["completed_ids"].append(grant_id)
        self.save()

    def mark_failed(self, grant_id: str):
        if grant_id not in self.state["failed_ids"]:
            self.state["failed_ids"].append(grant_id)
        self.save()

    def set_phase(self, phase: str):
        self.state["phase"] = phase
        self.state["last_updated"] = datetime.now(timezone.utc).isoformat()
        self.save()

    def is_completed(self, grant_id: str) -> bool:
        return grant_id in self.state["completed_ids"]


class DataValidator:
    """Validates data quality at each stage"""

    @staticmethod
    def validate_index_record(record: Dict[str, Any], source: str) -> List[str]:
        """Returns list of validation errors"""
        errors = []

        # Check for ID field - EU API uses callccm2Id, reference, or metadata.identifier
        metadata = record.get("metadata", {})
        has_id = (
            metadata.get("callccm2Id") or
            record.get("reference") or
            metadata.get("identifier") or
            record.get("callId") or
            record.get("id") or
            record.get("identifier") or
            record.get("code")
        )
        if not has_id:
            errors.append("Missing ID field")

        # Check for title - EU API uses content, callTitle, or metadata.title
        has_title = (
            record.get("content") or
            metadata.get("callTitle") or
            metadata.get("title") or
            record.get("title") or
            record.get("titleEn")
        )
        if not has_title:
            errors.append("Missing title field")

        return errors

    @staticmethod
    def validate_html(html: str, grant_id: str) -> List[str]:
        """Validate fetched HTML"""
        errors = []

        if not html or len(html) < 100:
            errors.append(f"HTML too short ({len(html)} chars)")

        if "error" in html.lower() and "404" in html:
            errors.append("HTML contains 404 error")

        return errors

    @staticmethod
    def validate_normalized(grant: NormalizedGrant) -> List[str]:
        """Validate normalized grant"""
        errors = []

        if not grant.title or len(grant.title.strip()) == 0:
            errors.append("Empty title")

        if not grant.url:
            errors.append("Missing URL")

        # Check date format if present
        for date_field, date_value in [
            ("open_date", grant.open_date),
            ("close_date", grant.close_date)
        ]:
            if date_value:
                try:
                    # Basic ISO format check
                    if 'T' in date_value:
                        datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                except ValueError:
                    errors.append(f"Invalid {date_field} format: {date_value}")

        return errors


class FundingBodyPipeline(ABC):
    """
    Base class for all funding body scrapers.
    Implements checkpoint recovery, audit logging, and validation.
    """

    def __init__(self, out_dir: str, delay: float = 0.5, max_retries: int = 3):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.max_retries = max_retries

        # Initialize subsystems
        self.audit = AuditLogger(self.out_dir)
        self.checkpoint = CheckpointManager(self.out_dir)
        self.validator = DataValidator()
        self.logger = logging.getLogger(self.source_name)

    @abstractmethod
    def fetch_index(self) -> List[Dict[str, Any]]:
        """Fetch all 'index' records (API results, listing pages, etc.)."""
        ...

    @abstractmethod
    def extract_ids(self, index_records: List[Dict[str, Any]]) -> List[str]:
        """Extract stable IDs from fetched index records."""
        ...

    @abstractmethod
    def fetch_detail_html(self, grant_id: str) -> str:
        """Fetch HTML for a single opportunity / topic."""
        ...

    @abstractmethod
    def normalize(
        self,
        grant_id: str,
        index_record: Dict[str, Any],
        html: Optional[str],
    ) -> NormalizedGrant:
        """Turn raw data into a NormalizedGrant."""
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        ...

    def _retry_with_backoff(self, func, *args, **kwargs):
        """Execute function with exponential backoff retry"""
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                wait_time = (2 ** attempt) * self.delay
                self.logger.warning(
                    f"Attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {wait_time:.1f}s..."
                )
                time.sleep(wait_time)

    def run(self, limit: Optional[int] = None):
        """
        Run the complete pipeline with checkpoint recovery.

        Args:
            limit: If set, only process this many grants (for testing)
        """
        start_time = datetime.now(timezone.utc)
        self.logger.info(f"Starting {self.source_name} pipeline")
        self.audit.log_event("pipeline_start", {"source": self.source_name})

        try:
            # Phase 1: Fetch index
            self._run_fetch_index()

            # Phase 2: Fetch details and normalize
            self._run_fetch_and_normalize(limit=limit)

            # Phase 3: Validate output
            self._run_validation()

            # Success
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            summary = {
                "source": self.source_name,
                "duration_seconds": duration,
                "audit_summary": self.audit.get_summary()
            }
            self.logger.info(f"Pipeline completed successfully in {duration:.1f}s")
            self.audit.log_event("pipeline_complete", summary)

            # Write summary
            (self.out_dir / "run_summary.json").write_text(
                json.dumps(summary, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )

        except Exception as e:
            self.logger.error(f"Pipeline failed: {e}", exc_info=True)
            self.audit.log_event("pipeline_error", {"error": str(e)})
            raise

    def _run_fetch_index(self):
        """Phase 1: Fetch index with validation"""
        self.checkpoint.set_phase("fetch_index")
        self.logger.info("Phase 1: Fetching index...")

        index_records = self._retry_with_backoff(self.fetch_index)

        # Validate records
        validation_errors = []
        for i, record in enumerate(index_records):
            errors = self.validator.validate_index_record(record, self.source_name)
            if errors:
                validation_errors.append({
                    "record_index": i,
                    "errors": errors,
                    "record_sample": str(record)[:200]
                })

        if validation_errors:
            self.logger.warning(
                f"Found {len(validation_errors)} records with validation issues"
            )
            (self.out_dir / "index_validation_errors.json").write_text(
                json.dumps(validation_errors, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )

        # Save raw index
        (self.out_dir / "raw_index.json").write_text(
            json.dumps(index_records, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )

        self.audit.log_event("index_fetched", {
            "count": len(index_records),
            "validation_errors": len(validation_errors)
        })
        self.logger.info(f"Fetched {len(index_records)} index records")

    def _run_fetch_and_normalize(self, limit: Optional[int] = None):
        """Phase 2: Fetch details and normalize with checkpoint recovery"""
        self.checkpoint.set_phase("fetch_and_normalize")
        self.logger.info("Phase 2: Fetching details and normalizing...")

        # Load index
        index_records = json.loads(
            (self.out_dir / "raw_index.json").read_text(encoding='utf-8')
        )

        # Extract IDs
        id_list = self.extract_ids(index_records)

        # Build ID to record mapping using the same extraction logic
        # We need to match the IDs returned by extract_ids()
        id_to_record = {}
        for r in index_records:
            # Use the same logic as extract_ids() to ensure matching
            # Use reference as the primary unique ID (always unique per opportunity)
            reference = r.get("reference")
            if reference:
                rid = reference
            else:
                # Fallback to callccm2Id if reference is missing
                metadata = r.get("metadata", {})
                call_ccm2_id = metadata.get("callccm2Id")
                if call_ccm2_id:
                    if isinstance(call_ccm2_id, list) and len(call_ccm2_id) > 0:
                        rid = call_ccm2_id[0]
                    else:
                        rid = call_ccm2_id
                else:
                    # Last resort: use metadata.identifier (but this can duplicate)
                    identifier_field = metadata.get("identifier")
                    if identifier_field:
                        if isinstance(identifier_field, list) and len(identifier_field) > 0:
                            rid = identifier_field[0]
                        else:
                            rid = identifier_field
                    else:
                        # Final fallback to other common ID fields
                        rid = (
                            r.get("callId") or r.get("id") or
                            r.get("identifier") or r.get("code")
                        )

            if rid:
                id_to_record[str(rid)] = r

        # Apply limit for testing
        if limit:
            id_list = id_list[:limit]
            self.logger.info(f"Limited to {limit} grants for testing")

        # Filter out already completed
        pending_ids = [
            gid for gid in id_list
            if not self.checkpoint.is_completed(gid)
        ]

        if len(pending_ids) < len(id_list):
            self.logger.info(
                f"Resuming from checkpoint: {len(pending_ids)}/{len(id_list)} remaining"
            )

        # Process each grant
        html_dir = self.out_dir / "html"
        html_dir.mkdir(exist_ok=True)
        normalized: List[Dict[str, Any]] = []

        for i, gid in enumerate(id_list, 1):
            # Load already completed grants
            if self.checkpoint.is_completed(gid):
                self.logger.debug(f"Skipping completed: {gid}")
                continue

            self.logger.info(f"[{i}/{len(id_list)}] Processing {gid}")

            try:
                # Fetch HTML
                html_path = html_dir / f"{gid}.html"
                if html_path.exists():
                    html = html_path.read_text(encoding='utf-8')
                    self.audit.log_event("html_cached", {"grant_id": gid})
                else:
                    html = self._retry_with_backoff(self.fetch_detail_html, gid)

                    # Validate HTML
                    html_errors = self.validator.validate_html(html, gid)
                    if html_errors:
                        self.logger.warning(
                            f"HTML validation issues for {gid}: {html_errors}"
                        )

                    html_path.write_text(html, encoding='utf-8')
                    self.audit.log_event("html_fetched", {
                        "grant_id": gid,
                        "size_bytes": len(html)
                    })
                    time.sleep(self.delay)

                # Normalize
                record = id_to_record.get(gid, {})
                grant = self.normalize(gid, record, html)

                # Validate normalized
                norm_errors = self.validator.validate_normalized(grant)
                if norm_errors:
                    self.logger.warning(
                        f"Normalization validation issues for {gid}: {norm_errors}"
                    )
                    self.audit.log_event("validation_warning", {
                        "grant_id": gid,
                        "errors": norm_errors
                    })

                normalized.append(asdict(grant))
                self.checkpoint.mark_completed(gid)
                self.audit.log_event("grant_processed", {"grant_id": gid})

            except Exception as e:
                self.logger.error(f"Failed to process {gid}: {e}", exc_info=True)
                self.checkpoint.mark_failed(gid)
                self.audit.log_event("grant_failed", {
                    "grant_id": gid,
                    "error": str(e)
                })
                # Continue with next grant
                continue

        # Save normalized output
        (self.out_dir / "normalized.json").write_text(
            json.dumps(normalized, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )

        self.logger.info(
            f"Normalized {len(normalized)} grants "
            f"({len(self.checkpoint.state['failed_ids'])} failed)"
        )

    def _run_validation(self):
        """Phase 3: Final validation and anomaly detection"""
        self.checkpoint.set_phase("validation")
        self.logger.info("Phase 3: Running final validation...")

        normalized = json.loads(
            (self.out_dir / "normalized.json").read_text(encoding='utf-8')
        )

        issues = {
            "empty_titles": [],
            "missing_dates": [],
            "suspicious_data": []
        }

        for grant in normalized:
            grant_id = grant.get("id", "unknown")

            # Check for empty titles
            if not grant.get("title") or len(grant["title"].strip()) < 5:
                issues["empty_titles"].append(grant_id)

            # Check for missing dates
            if not grant.get("open_date") and not grant.get("close_date"):
                issues["missing_dates"].append(grant_id)

            # Check for suspicious patterns (titles with weird characters, etc.)
            title = grant.get("title", "")
            if any(char in title for char in ['�', '\x00']):
                issues["suspicious_data"].append({
                    "grant_id": grant_id,
                    "issue": "encoding_problems",
                    "title_sample": title[:100]
                })

        # Write validation report
        validation_report = {
            "total_grants": len(normalized),
            "issues_found": {k: len(v) for k, v in issues.items()},
            "details": issues
        }

        (self.out_dir / "validation_report.json").write_text(
            json.dumps(validation_report, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )

        self.logger.info(f"Validation complete. Found {sum(len(v) for v in issues.values())} issues")
        self.audit.log_event("validation_complete", validation_report)
