import json
from typing import List, Optional, Any
from pydantic import BaseModel, Field, field_validator
from core.logger import log


class AtomicEntry(BaseModel):
    event: str
    crime_category: str = Field(..., description="Primary category")
    crime_subcategory: str = Field(..., description="Specific subcategory")
    brief_context: Optional[str] = Field(None, description="Context needed for this interpretation")

    # Original 9 ATOMIC relations
    xIntent: List[str] = Field(default_factory=list)
    xNeed: List[str] = Field(default_factory=list)
    xAttr: List[str] = Field(default_factory=list)
    xEffect: List[str] = Field(default_factory=list)
    xReact: List[str] = Field(default_factory=list)
    xWant: List[str] = Field(default_factory=list)
    oEffect: List[str] = Field(default_factory=list)
    oReact: List[str] = Field(default_factory=list)
    oWant: List[str] = Field(default_factory=list)

    # New ATOMIC 2020 event-centered relations
    isAfter: List[str] = Field(default_factory=list)
    HasSubEvent: List[str] = Field(default_factory=list)
    isBefore: List[str] = Field(default_factory=list)
    HinderedBy: List[str] = Field(default_factory=list)
    Causes: List[str] = Field(default_factory=list)
    xReason: List[str] = Field(default_factory=list)
    isFilledBy: List[str] = Field(default_factory=list)

    @field_validator('crime_category')
    @classmethod
    def standardize_category(cls, v):
        """Standardize the Non-Criminal category"""
        v_lower = v.lower().strip()
        if v_lower in ["no crime", "not a crime", "innocent", "legal", "none"]:
            return "Non-Criminal"
        return v.strip()

    # MAGIC PRE-VALIDATOR: Fixes LLM type hallucinations before they crash
    @field_validator(
        'xIntent', 'xWant', 'oReact', 'xReact', 'oWant', 'xEffect', 'oEffect', 'xNeed', 'xAttr',
        'isAfter', 'HasSubEvent', 'isBefore', 'HinderedBy', 'Causes', 'xReason', 'isFilledBy',
        mode='before'
    )
    @classmethod
    def force_list(cls, v: Any):
        """
        If the LLM returns an empty string or 'none' instead of a list,
        convert it to an empty list to prevent Pydantic crash.
        """
        if isinstance(v, str):
            v_clean = v.strip().lower()
            if v_clean == "" or v_clean in ["none", "null", "n/a"]:
                return []
            # If it's a string with content, wrap it in a list
            return [v]
        if v is None:
            return []
        return v

    @field_validator(
        'xIntent', 'xWant', 'oReact', 'xReact', 'oWant', 'xEffect', 'oEffect', 'xNeed', 'xAttr',
        'isAfter', 'HasSubEvent', 'isBefore', 'HinderedBy', 'Causes', 'xReason', 'isFilledBy'
    )
    @classmethod
    def check_content_quality(cls, v, info):
        """
        Validates that list items are not empty, not too short, and do not contain AI filler words.
        """
        if not v:
            return v  # Empty lists are acceptable (especially for isFilledBy when there is no ___)

        # Accept strings with at least 3 characters
        cleaned = [item.strip() for item in v if len(item.strip()) >= 3]

        # Anti-filler filter (useless AI words)
        forbidden = [
            "i don't know", "depends on context", "as an ai", "unknown",
            "n/a", "not applicable", "i cannot", "ai model", "sorry", "illegal"
        ]

        final_list = []
        for item in cleaned:
            if not any(bad in item.lower() for bad in forbidden):
                final_list.append(item)

        return final_list


def validate_llm_output(json_data: Any, original_event: str) -> Optional[dict]:
    """
    Validates the raw dictionary from the LLM against the AtomicEntry schema.
    Returns the validated dictionary or None if validation fails.
    """

    # 1. Check for the "NOT POSSIBLE" logic you implemented
    if isinstance(json_data, str):
        if "not possible" in json_data.lower():
            log.warning(f"Impossible to create a criminal context for '{original_event}'")
            return None
        else:
            log.warning(f"Validation failed for '{original_event}': Expected dictionary, got string.")
            return None
    elif isinstance(json_data, list) and len(json_data) > 0 and isinstance(json_data[0], str) and "not possible" in json_data[0].lower():
        log.warning(f"Impossible to create a criminal context for '{original_event}'")
        return None

    # If the LLM returned ["NOT POSSIBLE"] as a list (per new prompt logic)
    if isinstance(json_data, list) and len(json_data) > 0 and isinstance(json_data[0], str):
        if "not possible" in json_data[0].lower():
            log.warning(f"Impossible to create a criminal context for '{original_event}'")
            return None

    # 2. Prevent crash if the LLM generated a list instead of a dict
    if not isinstance(json_data, dict):
        log.warning(f"Validation failed for '{original_event}': Expected dictionary, got {type(json_data).__name__}")
        return None

    try:
        # Copy the data and enforce the event name
        data_to_validate = json_data.copy()
        data_to_validate['event'] = original_event

        # Validate against the Pydantic schema
        entry = AtomicEntry(**data_to_validate)
        return entry.model_dump()
    except Exception as e:
        log.warning(f"Validation failed for '{original_event}': {e}")
        return None