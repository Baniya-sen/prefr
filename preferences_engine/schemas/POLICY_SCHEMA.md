# =========================================
# Preference Policy Schema — V1.3
# Status: Locked
# =========================================

# -----------------------------------------
# OVERVIEW
# -----------------------------------------
# One preference = one YAML file
# Filename = {id}.yaml
# All files stored in: preferences_engine/policies/
#
# This schema defines:
# - Structure
# - Field meanings
# - Scoring system
# - Evaluation rules
#
# Runtime is deterministic.
# No LLM is used for scoring or evaluation.


# =========================================
# REQUIRED FIELDS
# =========================================

id: <string>
# - snake_case
# - globally unique
# - immutable once created

title: <string>
# - 1–100 characters
# - human-readable name

body: >
  <instruction text>
# - 1–500 characters
# - plain language
# - imperative tone
# - no variables, no templates
#
# Rules:
# - Must describe a general decision preference
# - Must be domain-level, not implementation-level
# - Must not reference personal setups, hardware, environments, or configurations
# - Must not reference specific tools, services, or technologies
# - Must not include examples
# - Must be reusable across contexts
# - Must express intent, not execution details

applies_to:
  - <domain_string>
# - at least 1 domain required
# - OR logic (any match activates)


# =========================================
# SCORING FIELDS
# =========================================

priority: <integer 0-100>
# STATIC (manual)
# Represents how strongly this preference defines user's decision style
#
# Guidelines:
# 85–95 → Core identity
# 70–85 → Strong preference
# 50–70 → Situational
# 30–50 → Weak / experimental

confidence: <float 0.0-1.0>
# DYNAMIC (derived from evidence)
# Represents how certain we are this preference is correct

primary_domain: <domain_string>
# Optional
# The single domain this policy is most specifically targeted at.
# When the classifier detects this domain, the policy gets a +20 score bonus.
# This distinguishes "specifically for X" from "merely applicable to X".
# Should be set at creation time.
# Must be a valid domain string from the Domain Registry.


# =========================================
# EXCEPTIONS
# =========================================

exceptions:
  - <preference_id>
# Optional
#
# Exceptions are NOT logic.
# Exceptions are INFORMATION.
#
# Every string in exceptions is another preference ID.
# These are injected into the LLM context alongside the preference body.
# The LLM decides what to do with them.
#
# Rules:
# - Each entry must be a valid preference ID
# - Must not reference self
# - Used by the main LLM to understand edge cases and overrides
# - No scoring impact
# - No dampening logic


# =========================================
# RELATIONSHIPS
# =========================================

related:
  - <preference_id>
# Optional
#
# Definition:
# Preferences with similar or overlapping decision intent
#
# Rules:
# - No hierarchy
# - No direction
# - No scoring impact
# - Used only for grouping / deduplication


# =========================================
# EVIDENCE
# =========================================

evidence:
  positive: <integer>
  negative: <integer>
  representative_observations:
    - <obs_id>
  summary: <string>

# Rules:
# - positive >= 0
# - negative >= 0
# - confidence MUST be derived from these values


# =========================================
# METADATA
# =========================================

created_by: manual | reflection
created_at: YYYY-MM-DD
updated_at: YYYY-MM-DD
last_reviewed: YYYY-MM-DD


# =========================================
# DOMAIN REGISTRY (LOCKED)
# =========================================

# Valid values for applies_to:

# software
# infrastructure
# databases
# productivity
# media
# photography
# finance
# health
# travel
# learning
# hardware
# automation
# security
# development


# =========================================
# SCORING SYSTEM (LOCKED)
# =========================================

# Final score calculation:

# score = priority + (confidence * 100) + bonus

# Range:
# 0 → 220

# No other fields influence score

# Bonus:
# +20 if primary_domain matches classifier domains


# =========================================
# CONFIDENCE CALCULATION (LOCKED)
# =========================================

# confidence = (positive + 1) / (positive + negative + 2)

# Properties:
# - stable for low data
# - prevents division by zero
# - naturally balances conflicting evidence


# =========================================
# DEFAULT VALUES
# =========================================

# For manual policies:
# confidence = 0.7 (initial)

# For reflection-created policies:
# confidence = 0.5 (initial)

# If no evidence:
# positive = 0
# negative = 0


# =========================================
# EVALUATION RULES (ENGINE BEHAVIOR)
# =========================================

# 1. Activation
# A preference is considered only if:
# applies_to intersects classifier domains


# 2. Scoring
# score = priority + (confidence * 100)


# 3. Ranking
# Sort all candidates by score (descending)


# 4. Deduplication (using related)
# Do NOT select more than 2 preferences
# from the same related group


# 5. Minimum Threshold
# Discard preferences where:
#
# score < 100


# 6. Final Selection
# Select top N preferences (recommended: 3–5)


# =========================================
# VALIDATION RULES
# =========================================

# id:
# - snake_case
# - unique
# - immutable

# title:
# - required
# - max 100 chars

# body:
# - required
# - max 500 chars
# - plain text only

# applies_to:
# - at least 1 domain
# - must exist in domain registry

# exceptions:
# - each entry must be a valid preference ID
# - must not reference self

# related:
# - each entry must reference valid existing preference id
# - must not reference self

# evidence:
# - positive, negative must be integers >= 0

# confidence:
# - must match calculation formula
# - should not be manually edited after initialization


# =========================================
# INJECTION
# =========================================

# When a preference is selected, inject into Hermes context:
#
# <preference id="{id}">
# {body}
# {exceptions as informational note}
# </preference>
#
# Example injection:
# <preference id="local_first">
# Prefer solutions that run locally on user-controlled machines...
#
# Note: This preference has exceptions: company_projects
# </preference>


# =========================================
# NON-GOALS (V1)
# =========================================

# - No clusters
# - No tags
# - No semantic matching
# - No embeddings
# - No runtime learning
# - No rule language
# - No hierarchy between preferences


# =========================================
# DESIGN PRINCIPLES
# =========================================

# - Runtime is deterministic
# - Reflection handles learning
# - Preferences are independent signals
# - Exceptions are information, not logic
# - LLM decides how to handle exceptions
# - Simplicity over flexibility
# - Debuggability over intelligence
