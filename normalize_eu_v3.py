"""
EU Funding v3 Normalizer

Converts Horizon Europe and Digital Europe raw API data into 
ailsa_shared Grant schema with 9 independently embeddable sections.

Handles:
- Horizon Europe (framework 43108390)
- Digital Europe (framework 43152860)

Section mapping:
    EU API Field             → v3 Section
    ─────────────────────────────────────────
    callTitle/summary        → summary.text
    description              → scope.text
    topicConditions          → eligibility.text
    deadlineDate/startDate   → dates
    budget                   → funding
    beneficiaryAdministration→ how_to_apply.text
    furtherInformation       → supporting_info.text
"""

import re
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple, List, Dict, Any
from pathlib import Path
from html import unescape

from ailsa_shared.models import (
    Grant,
    GrantSource,
    GrantStatus,
    GrantSections,
    SummarySection,
    EligibilitySection,
    ScopeSection,
    DatesSection,
    FundingSection,
    HowToApplySection,
    AssessmentSection,
    SupportingInfoSection,
    ContactsSection,
    ProgrammeInfo,
    ProcessingInfo,
    CompetitionType,
)

logger = logging.getLogger(__name__)

# Status code mapping
STATUS_MAP = {
    '31094501': GrantStatus.FORTHCOMING,
    '31094502': GrantStatus.OPEN,
    '31094503': GrantStatus.CLOSED,
}

# Framework programme mapping
FRAMEWORK_MAP = {
    '43108390': ('horizon_europe', 'Horizon Europe'),
    '43152860': ('digital_europe', 'Digital Europe Programme'),
}


# =============================================================================
# MAIN NORMALIZER
# =============================================================================

def normalize_eu_v3(grant_data: Dict[str, Any], source_name: str = "horizon_europe") -> Grant:
    """
    Normalize EU API grant data to v3 Grant schema.
    
    Args:
        grant_data: Dict from raw_index.json
        source_name: 'horizon_europe' or 'digital_europe'
        
    Returns:
        Grant with all sections populated
    """
    meta = grant_data.get('metadata', {})
    
    # Get first value from metadata arrays
    def get_first(key: str, default: str = '') -> str:
        val = meta.get(key, [default])
        if isinstance(val, list):
            return val[0] if val else default
        return val or default
    
    # Build grant_id
    reference = grant_data.get('reference', '')
    identifier = get_first('identifier')
    external_id = identifier or reference
    
    source = GrantSource.HORIZON_EUROPE if source_name == 'horizon_europe' else GrantSource.DIGITAL_EUROPE
    grant_id = f"{source.value}_{external_id}".replace('-', '_').lower()
    
    # Get title
    title = get_first('callTitle') or get_first('caName') or grant_data.get('summary', '')
    
    # Get URL
    url = get_first('url') or grant_data.get('url', '')
    
    # Parse dates
    opens_at = _parse_date(get_first('startDate'))
    deadline_dates = meta.get('deadlineDate', [])
    closes_at = _parse_latest_deadline(deadline_dates)
    
    # Determine status
    status_code = get_first('status')
    status = STATUS_MAP.get(status_code, GrantStatus.UNKNOWN)
    is_active = status == GrantStatus.OPEN
    
    # Parse funding
    budget_str = get_first('budget')
    total_pot_eur, total_pot_display = _parse_budget(budget_str)
    
    # Get text content (strip HTML)
    description = _strip_html(get_first('description'))
    further_info = _strip_html(get_first('furtherInformation'))
    beneficiary_admin = _strip_html(get_first('beneficiaryAdministration'))
    topic_conditions = _strip_html(get_first('topicConditions'))
    destination_desc = _strip_html(get_first('destinationDescription'))
    
    # Build summary from call title + summary
    summary_text = grant_data.get('summary', '') or description[:500]
    
    # Build sections
    grant_sections = GrantSections(
        summary=_build_summary_section(summary_text, title, identifier),
        eligibility=_build_eligibility_section(topic_conditions, description),
        scope=_build_scope_section(description, destination_desc, meta),
        dates=_build_dates_section(opens_at, closes_at, deadline_dates, meta),
        funding=_build_funding_section(total_pot_eur, total_pot_display, meta),
        how_to_apply=_build_how_to_apply_section(beneficiary_admin, url),
        assessment=_build_assessment_section(beneficiary_admin, further_info),
        supporting_info=_build_supporting_info_section(further_info, meta),
        contacts=_build_contacts_section(meta),
    )
    
    # Build programme info
    framework_id = get_first('frameworkProgramme')
    programme_info = _build_programme_info(framework_id, identifier, meta)
    
    # Build tags
    tags = _build_tags(source_name, status, meta)
    
    # Create Grant
    grant = Grant(
        grant_id=grant_id,
        source=source,
        external_id=external_id,
        title=title,
        url=url,
        status=status,
        is_active=is_active,
        sections=grant_sections,
        programme=programme_info,
        tags=tags,
        raw=None,
        processing=ProcessingInfo(
            scraped_at=_parse_date(get_first('esDA_IngestDate')),
            normalized_at=_now(),
            sections_extracted=['description', 'furtherInformation', 'beneficiaryAdministration'],
            schema_version="3.0",
        ),
        created_at=_now(),
        updated_at=_now(),
    )
    
    return grant


# =============================================================================
# SECTION BUILDERS
# =============================================================================

def _build_summary_section(summary_text: str, title: str, identifier: str) -> SummarySection:
    """Build summary section."""
    # Combine title context with summary
    text = summary_text
    if not text and title:
        text = title
    
    return SummarySection(
        text=text,
        project_acronym=identifier.split('-')[0] if identifier else None,
        extracted_at=_now(),
    )


def _build_eligibility_section(topic_conditions: str, description: str) -> EligibilitySection:
    """Build eligibility section."""
    # Use topic conditions if available, otherwise extract from description
    text = topic_conditions
    if not text:
        # Try to extract eligibility from description
        text = _extract_eligibility_from_desc(description)
    
    # Standard EU eligibility
    who_can_apply = ['Legal entities from EU Member States', 'Associated countries']
    
    return EligibilitySection(
        text=text,
        who_can_apply=who_can_apply,
        geographic_scope="EU + Associated Countries",
        partnership_required=True,  # Most EU grants require consortia
        partnership_details="Consortium typically required with partners from multiple countries",
        extracted_at=_now(),
    )


def _build_scope_section(description: str, destination_desc: str, meta: Dict) -> ScopeSection:
    """Build scope section with themes."""
    # Combine description and destination
    text = description
    if destination_desc and destination_desc not in text:
        text = f"{text}\n\n{destination_desc}" if text else destination_desc
    
    # Extract themes from keywords and tags
    themes = _extract_themes(meta)
    
    # Extract TRL if mentioned
    trl_min, trl_max, trl_range = _extract_trl(text)
    
    # Get topic code
    topic_code = meta.get('identifier', [''])[0] if meta.get('identifier') else None
    
    # Get action type
    action_type = None
    types_of_action = meta.get('typesOfAction', [])
    if types_of_action:
        action_type = types_of_action[0] if isinstance(types_of_action[0], str) else None
    
    return ScopeSection(
        text=text,
        themes=themes,
        trl_min=trl_min,
        trl_max=trl_max,
        trl_range=trl_range,
        topic_code=topic_code,
        action_type=action_type,
        extracted_at=_now(),
    )


def _build_dates_section(
    opens_at: Optional[datetime],
    closes_at: Optional[datetime],
    deadline_dates: List[str],
    meta: Dict
) -> DatesSection:
    """Build dates section."""
    # Parse all deadline dates
    parsed_deadlines = [_parse_date(d) for d in deadline_dates if d]
    parsed_deadlines = [d for d in parsed_deadlines if d]
    
    # Get deadline model
    deadline_model = meta.get('deadlineModel', [''])[0] if meta.get('deadlineModel') else None
    
    # Extract deadline time
    deadline_time = None
    if deadline_dates:
        # Extract time from first deadline
        first_deadline = deadline_dates[0]
        time_match = re.search(r'T(\d{2}:\d{2})', first_deadline)
        if time_match:
            deadline_time = time_match.group(1) + " Brussels time"
    
    # Duration
    duration = meta.get('duration', [''])[0] if meta.get('duration') else None
    duration_min, duration_max, duration_text = _parse_duration(duration)
    
    return DatesSection(
        opens_at=opens_at,
        closes_at=closes_at,
        deadline_time=deadline_time,
        timezone="Europe/Brussels",
        deadline_dates=parsed_deadlines,
        deadline_model=deadline_model,
        project_duration=duration_text,
        project_duration_months_min=duration_min,
        project_duration_months_max=duration_max,
        extracted_at=_now(),
    )


def _build_funding_section(
    total_pot_eur: Optional[int],
    total_pot_display: Optional[str],
    meta: Dict
) -> FundingSection:
    """Build funding section."""
    # Get budget overview for more details
    budget_overview = _strip_html(meta.get('budgetOverview', [''])[0] if meta.get('budgetOverview') else '')
    
    # Build text
    text_parts = []
    if total_pot_display:
        text_parts.append(f"Total budget: {total_pot_display}")
    if budget_overview:
        text_parts.append(budget_overview)
    
    return FundingSection(
        text="\n".join(text_parts) if text_parts else None,
        total_pot_eur=total_pot_eur,
        total_pot_display=total_pot_display,
        currency="EUR",
        competition_type=CompetitionType.GRANT,
        extracted_at=_now(),
    )


def _build_how_to_apply_section(beneficiary_admin: str, url: str) -> HowToApplySection:
    """Build how to apply section."""
    return HowToApplySection(
        text=beneficiary_admin,
        portal_name="EU Funding & Tenders Portal",
        portal_url="https://ec.europa.eu/info/funding-tenders/opportunities/portal/",
        apply_url=url,
        registration_required=True,
        extracted_at=_now(),
    )


def _build_assessment_section(beneficiary_admin: str, further_info: str) -> AssessmentSection:
    """Build assessment section."""
    # EU standard criteria
    criteria = ['Excellence', 'Impact', 'Implementation']
    
    # Try to extract from text
    combined = f"{beneficiary_admin} {further_info}".lower()
    if 'evaluat' in combined:
        # Likely has evaluation info
        pass
    
    return AssessmentSection(
        text=_extract_assessment_text(further_info),
        criteria=criteria,
        extracted_at=_now(),
    )


def _build_supporting_info_section(further_info: str, meta: Dict) -> SupportingInfoSection:
    """Build supporting info section."""
    # Get links
    links = meta.get('links', [])
    
    return SupportingInfoSection(
        text=further_info,
        extracted_at=_now(),
    )


def _build_contacts_section(meta: Dict) -> ContactsSection:
    """Build contacts section."""
    # EU portal helpdesk
    return ContactsSection(
        helpdesk_email="ec-funding-enquiries@ec.europa.eu",
        helpdesk_url="https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/support/helpdesks",
        extracted_at=_now(),
    )


def _build_programme_info(framework_id: str, identifier: str, meta: Dict) -> ProgrammeInfo:
    """Build programme info."""
    source_key, framework_name = FRAMEWORK_MAP.get(framework_id, ('unknown', 'Unknown Framework'))
    
    # Extract call info
    call_id = meta.get('callIdentifier', [''])[0] if meta.get('callIdentifier') else None
    call_title = meta.get('callTitle', [''])[0] if meta.get('callTitle') else None
    
    # Get destination/cluster
    destination = meta.get('destination', [''])[0] if meta.get('destination') else None
    
    return ProgrammeInfo(
        name=framework_name,
        funder="European Commission",
        framework_programme=framework_name,
        call_id=call_id,
        call_title=call_title,
        code=identifier,
    )


# =============================================================================
# PARSING HELPERS
# =============================================================================

def _now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse EU API date string."""
    if not date_str:
        return None
    
    try:
        # Handle ISO format with timezone
        if '+' in date_str:
            date_str = date_str.split('+')[0]
        if 'T' in date_str:
            # Remove milliseconds
            date_str = re.sub(r'\.\d+', '', date_str)
            return datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S')
        return datetime.strptime(date_str, '%Y-%m-%d')
    except (ValueError, TypeError):
        return None


def _parse_latest_deadline(deadline_dates: List[str]) -> Optional[datetime]:
    """Get the latest deadline from a list of dates."""
    if not deadline_dates:
        return None
    
    parsed = []
    for d in deadline_dates:
        dt = _parse_date(d)
        if dt:
            parsed.append(dt)
    
    if parsed:
        return max(parsed)
    return None


def _parse_budget(budget_str: str) -> Tuple[Optional[int], Optional[str]]:
    """Parse budget string to EUR amount.
    
    EU API is inconsistent - some values are raw euros (80000000),
    others are in millions (2.01, 15). We detect based on magnitude:
    - Values < 1000 are assumed to be in millions
    - Values >= 1000 are assumed to be raw euros
    """
    if not budget_str:
        return None, None
    
    try:
        raw_amount = float(budget_str)
        
        # Detect if value is in millions vs raw euros
        # Assumption: No EU grant has a budget less than €1000 raw
        # So values < 1000 are actually millions
        if raw_amount < 1000:
            # Value is in millions
            amount = int(raw_amount * 1_000_000)
            display = f"€{raw_amount:.1f} million" if raw_amount >= 1 else f"€{int(raw_amount * 1000)}k"
        else:
            # Value is raw euros
            amount = int(raw_amount)
            if amount >= 1_000_000:
                display = f"€{amount/1_000_000:.1f} million"
            elif amount >= 1_000:
                display = f"€{amount:,}"
            else:
                display = f"€{amount}"
        
        return amount, display
    except (ValueError, TypeError):
        return None, budget_str


def _parse_duration(duration_str: Optional[str]) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """Parse duration string."""
    if not duration_str:
        return None, None, None
    
    # Pattern: X to Y months
    pattern = r'(\d+)\s*(?:to|-)\s*(\d+)\s*months?'
    match = re.search(pattern, duration_str.lower())
    if match:
        min_m = int(match.group(1))
        max_m = int(match.group(2))
        return min_m, max_m, f"{min_m}-{max_m} months"
    
    # Pattern: X months
    pattern = r'(\d+)\s*months?'
    match = re.search(pattern, duration_str.lower())
    if match:
        months = int(match.group(1))
        return months, months, f"{months} months"
    
    return None, None, duration_str


def _strip_html(html: str) -> str:
    """Strip HTML tags and clean text."""
    if not html:
        return ''
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', html)
    # Unescape HTML entities
    text = unescape(text)
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def _extract_eligibility_from_desc(description: str) -> str:
    """Extract eligibility info from description."""
    # Look for eligibility-related content
    patterns = [
        r'(eligib[^\n.]*\.)',
        r'(who can apply[^\n]*)',
        r'(legal entit[^\n.]*\.)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return ''


def _extract_themes(meta: Dict) -> List[str]:
    """Extract themes from keywords and tags."""
    themes = []
    
    # Get keywords
    keywords = meta.get('keywords', [])
    if keywords:
        themes.extend([k for k in keywords[:5] if isinstance(k, str)])
    
    # Get tags
    tags = meta.get('tags', [])
    if tags:
        themes.extend([t for t in tags[:5] if isinstance(t, str)])
    
    # Get focus area
    focus = meta.get('focusArea', [])
    if focus:
        themes.extend([f for f in focus[:3] if isinstance(f, str)])
    
    # Deduplicate
    seen = set()
    unique = []
    for t in themes:
        t_lower = t.lower()
        if t_lower not in seen:
            seen.add(t_lower)
            unique.append(t)
    
    return unique[:10]  # Limit to 10


def _extract_trl(text: str) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """Extract TRL from text."""
    pattern = r'trl\s*(\d)\s*[-–to]+\s*(\d)'
    match = re.search(pattern, text.lower())
    
    if match:
        trl_min = int(match.group(1))
        trl_max = int(match.group(2))
        return trl_min, trl_max, f"TRL {trl_min}-{trl_max}"
    
    return None, None, None


def _extract_assessment_text(text: str) -> Optional[str]:
    """Extract assessment/evaluation text."""
    patterns = [
        r'(evaluat[^\n]*)',
        r'(assessment[^\n]*)',
        r'(selection[^\n]*criteria[^\n]*)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None


def _build_tags(source_name: str, status: GrantStatus, meta: Dict) -> List[str]:
    """Build tags for filtering."""
    tags = [source_name]
    
    # Status
    tags.append(status.value)
    
    # EU specific
    tags.append("eu_funding")
    
    # Framework
    if source_name == 'horizon_europe':
        tags.append("research_innovation")
    elif source_name == 'digital_europe':
        tags.append("digital")
    
    # Destination/cluster
    destination = meta.get('destination', [])
    if destination and isinstance(destination[0], str):
        dest_tag = destination[0].lower().replace(' ', '_')[:30]
        tags.append(dest_tag)
    
    return tags


# =============================================================================
# BATCH PROCESSING
# =============================================================================

def normalize_eu_batch(
    grants_data: List[Dict[str, Any]],
    source_name: str = "horizon_europe"
) -> List[Grant]:
    """
    Normalize a batch of EU grants.
    
    Args:
        grants_data: List of grant dicts from raw_index.json
        source_name: 'horizon_europe' or 'digital_europe'
        
    Returns:
        List of normalized Grants
    """
    grants = []
    
    for i, data in enumerate(grants_data):
        try:
            grant = normalize_eu_v3(data, source_name)
            grants.append(grant)
        except Exception as e:
            ref = data.get('reference', 'Unknown')
            logger.error(f"Failed to normalize {ref}: {e}")
    
    return grants


def load_and_normalize(
    horizon_path: str = "data/horizon_europe/raw_index.json",
    digital_path: str = "data/digital_europe/raw_index.json"
) -> List[Grant]:
    """
    Load grants from both Horizon Europe and Digital Europe and normalize.
    
    Args:
        horizon_path: Path to Horizon Europe raw_index.json
        digital_path: Path to Digital Europe raw_index.json
        
    Returns:
        Combined list of normalized Grants
    """
    all_grants = []
    
    # Horizon Europe
    horizon_file = Path(horizon_path)
    if horizon_file.exists():
        with open(horizon_file) as f:
            horizon_data = json.load(f)
        horizon_grants = normalize_eu_batch(horizon_data, "horizon_europe")
        all_grants.extend(horizon_grants)
        print(f"Loaded {len(horizon_grants)} Horizon Europe grants")
    
    # Digital Europe
    digital_file = Path(digital_path)
    if digital_file.exists():
        with open(digital_file) as f:
            digital_data = json.load(f)
        digital_grants = normalize_eu_batch(digital_data, "digital_europe")
        all_grants.extend(digital_grants)
        print(f"Loaded {len(digital_grants)} Digital Europe grants")
    
    return all_grants


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import sys
    
    # Default paths
    horizon_path = sys.argv[1] if len(sys.argv) > 1 else "data/horizon_europe/raw_index.json"
    digital_path = sys.argv[2] if len(sys.argv) > 2 else "data/digital_europe/raw_index.json"
    
    print(f"Loading EU grants...")
    grants = load_and_normalize(horizon_path, digital_path)
    
    print(f"\n{'='*60}")
    print(f"NORMALIZED {len(grants)} EU GRANTS")
    print(f"{'='*60}")
    
    # Summary stats
    open_count = sum(1 for g in grants if g.status == GrantStatus.OPEN)
    closed_count = sum(1 for g in grants if g.status == GrantStatus.CLOSED)
    forthcoming_count = sum(1 for g in grants if g.status == GrantStatus.FORTHCOMING)
    
    print(f"\nStatus: {open_count} open, {forthcoming_count} forthcoming, {closed_count} closed")
    
    # Source breakdown
    horizon_count = sum(1 for g in grants if g.source == GrantSource.HORIZON_EUROPE)
    digital_count = sum(1 for g in grants if g.source == GrantSource.DIGITAL_EUROPE)
    print(f"Sources: {horizon_count} Horizon Europe, {digital_count} Digital Europe")
    
    # Section coverage
    print(f"\nSection coverage:")
    print(f"  Summary:     {sum(1 for g in grants if g.sections.summary.text)}/{len(grants)}")
    print(f"  Eligibility: {sum(1 for g in grants if g.sections.eligibility.text)}/{len(grants)}")
    print(f"  Scope:       {sum(1 for g in grants if g.sections.scope.text)}/{len(grants)}")
    print(f"  Dates:       {sum(1 for g in grants if g.sections.dates.closes_at)}/{len(grants)}")
    print(f"  Funding:     {sum(1 for g in grants if g.sections.funding.total_pot_eur)}/{len(grants)}")
    print(f"  How to Apply:{sum(1 for g in grants if g.sections.how_to_apply.text)}/{len(grants)}")
    
    # Sample output
    print(f"\n{'='*60}")
    print("SAMPLE OPEN GRANTS:")
    print(f"{'='*60}")
    
    open_grants = [g for g in grants if g.status == GrantStatus.OPEN][:5]
    for grant in open_grants:
        print(f"\n{grant.title[:60]}")
        print(f"  ID: {grant.grant_id}")
        print(f"  Budget: {grant.sections.funding.total_pot_display}")
        print(f"  Deadline: {grant.sections.dates.closes_at}")
        print(f"  Themes: {grant.sections.scope.themes[:3]}")
