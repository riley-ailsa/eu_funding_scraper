# Understanding "Duplicate" IDs in EU Funding Data

## The Issue

Previously, the scraper appeared to have duplicate IDs:
- Digital Europe: 310 total records → 194 unique IDs (116 "duplicates")
- Example: "DIGITAL-2023-SKILLS-04-BOOSTINGDIGIT" appeared 29 times

## The Reality: Cascading Grants

These are **NOT duplicates** - they represent a hierarchical funding structure:

### Call Hierarchy

```
Parent Call (metadata.identifier)
└── Topic/Opportunity 1 (callccm2Id: 10381) - Code4Portugal
└── Topic/Opportunity 2 (callccm2Id: 11067) - Coding Education Italy
└── Topic/Opportunity 3 (callccm2Id: 10703) - Small Grants Ireland
└── ... (up to 29 opportunities)
```

### Example: DIGITAL-2023-SKILLS-04-BOOSTINGDIGIT

This **parent call** funded **20 separate opportunities**:
- Code4Portugal (callccm2Id: 10381)
- Coding Education Grants Italy (callccm2Id: 11067)
- Small Grants for Coding Ireland (callccm2Id: 10703)
- Code4Spain (callccm2Id: 10704)
- And 16 more country-specific or topic-specific sub-calls

Each opportunity:
- ✅ Has a unique `callccm2Id` (e.g., 10381, 11067)
- ✅ Has a unique `reference` (e.g., "10381COMPETITIVE_CALLen")
- ✅ Has a different title/content (e.g., "Code4Portugal")
- ✅ Has different deadlines, budgets, eligibility
- ❌ Shares the same parent call identifier

## Why This Happens

This is a **Financial Support to Third Parties (FSTP)** model:

1. EU awards one large grant to a consortium
2. The consortium creates multiple sub-calls across different countries/regions
3. Each sub-call is a separate funding opportunity
4. All share the same parent call identifier for administrative tracking

## The Fix

Changed from using `metadata.identifier` (parent call) to `callccm2Id` (unique opportunity):

**Before:**
```python
# Used metadata.identifier - NOT unique across opportunities
call_id = metadata.get("identifier")[0]  # "DIGITAL-2023-SKILLS-04-BOOSTINGDIGIT"
```

**After:**
```python
# Use callccm2Id - unique per opportunity
call_id = metadata.get("callccm2Id")[0]  # "10381", "11067", etc.
```

## Results

After the fix:
- ✅ Horizon Europe: 3,424 opportunities (matches website exactly)
- ✅ Digital Europe: 310 opportunities (matches website exactly)
- ✅ No validation warnings
- ✅ All opportunities properly tracked as separate entities

## Impact on Users

This means when you search EU funding opportunities, you'll see:
- **20 separate opportunities** for coding education across Europe
- Each with different eligibility (country-specific)
- Each with different deadlines and budgets
- But all part of the same strategic initiative

This is the **correct behavior** - users need to see all 20 opportunities, not just one parent call.
