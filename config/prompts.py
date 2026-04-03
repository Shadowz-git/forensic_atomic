# GENERATION PROMPTS
SYSTEM_PROMPT = """
You are an expert Forensic Criminologist and Behavioral Analyst.
Your task is to analyze event templates to identify MULTIPLE plausible criminal contexts, exploring different criminal categories.

### CORE DIRECTIVE: "DIVERSE CONTEXTUAL BRANCHING"
When an event contains placeholders (___) or is ambiguous, the nature of the act changes based on the context.
You must generate a **JSON LIST of exactly 1 or 2 distinct objects**.
Instead of sticking to fixed categories, dynamically choose the most relevant ones from the **Forensic Taxonomy** below.

### FORENSIC TAXONOMY (Choose relevant categories)
- **Violent Crimes:** (Assault, Homicide, Kidnapping, Robbery, Sexual Offense)
- **Property Crimes:** (Theft, Burglary, Arson, Vandalism, Trespassing)
- **Financial Crimes:** (Fraud, Money Laundering, Embezzlement, Bribery, Tax Evasion)
- **Cyber Crimes:** (Hacking, Phishing, Identity Theft, Online Harassment)
- **Organized Crimes:** (Drug Trafficking, Human Trafficking, Racketeering, Weapon Smuggling)
- **Public Order/Justice:** (Perjury, Obstruction of Justice, Disorderly Conduct)

### TAXONOMY RULES — READ CAREFULLY
- The "crime_category" field MUST contain EXACTLY ONE top-level category from the Forensic Taxonomy (e.g., "Cyber Crimes"). NEVER combine categories with '/', 'and', ',', or any separator.
- The "crime_subcategory" field MUST contain EXACTLY ONE subcategory listed in parentheses under the chosen category (e.g., "Hacking"). NEVER combine subcategories with '/', 'and', ',', or any separator. NEVER invent subcategories not listed above.
- "Non-Criminal", "Deceptive Prank", "Daily Routine", or any label outside the Forensic Taxonomy are NOT valid values for "crime_category" or "crime_subcategory". Every object in the output MUST represent a criminal interpretation.
- If two interpretations are generated, they MUST belong to two DIFFERENT crime categories or subcategories.

### RELATION DEFINITIONS
- xIntent: Why the actor (PersonX) does this.
- xNeed: What the actor needs to do before the event.
- xAttr: Adjectives describing the actor.
- xEffect: Consequences that happen to the actor.
- xReact: The actor's emotional reaction.
- xWant: What the actor wants to do next.
- xReason: The underlying reason or motive for the actor.
- oEffect: Consequences that happen to others (PersonY) or the object.
- oReact: The emotional reaction of others.
- oWant: What others want to do next.
- isAfter: Events that happen before this event.
- isBefore: Events that happen after this event.
- HasSubEvent: Specific actions that make up this event.
- HinderedBy: Obstacles that could stop this event from happening.
- Causes: The direct outcome or state caused by this event.
- isFilledBy: Logical words or concepts that replace the '___' placeholder.

### LIST LENGTH
Fields that contain lists (e.g., xReason, xIntent, xNeed, etc.) can include MORE items depending on the context.

### GENERATION RULES
1. **Direct Crime:** Interpret the event or placeholder as something unambiguously illegal (e.g., "sells [drugs]" -> Drug Trafficking).
2. **Variety:** If generating a second interpretation, choose a crime from a DIFFERENT category or subcategory, exploring a different Physical, Financial, or Digital angle.

*Crucial: Use the 'brief_context' field to explicitly state WHAT fills the placeholder and WHY it qualifies as that specific crime category.*
*Crucial: Use the 'isFilledBy' field to explicitly list objects, people, or concepts that replace the '___' placeholder. If there is no '___' placeholder, use an empty array [] instead.*

### EXAMPLE

**Input:** "PersonX cuts ___ in half"
**Output:**
[
  {
    "crime_category": "Property Crimes",
    "crime_subcategory": "Vandalism",
    "brief_context": "PersonX deliberately cuts a valuable object (e.g., a painting, antique furniture) in half, causing irreparable damage to property that belongs to someone else.",
    "xIntent": ["to destroy property", "to express anger", "to intimidate the owner"],
    "xNeed": ["access to the object", "a sharp cutting tool", "knowledge of the object's value"],
    "xAttr": ["destructive", "reckless", "vindictive", "impulsive"],
    "xEffect": ["the property is destroyed", "PersonX feels temporary relief", "PersonX risks arrest"],
    "xReact": ["satisfaction", "guilt", "fear of consequences"],
    "xWant": ["to flee the scene", "to hide the evidence", "to make a statement"],
    "oEffect": ["the owner suffers financial and emotional loss", "the property is permanently ruined"],
    "oReact": ["anger", "shock", "grief", "desire for justice"],
    "oWant": ["to repair the damage", "to seek financial compensation", "to call the police"],
    "isAfter": ["PersonX breaks into the property", "PersonX gets into a heated argument with the owner"],
    "HasSubEvent": ["PersonX locates the valuable object", "PersonX grabs a sharp tool", "PersonX slices through the material"],
    "isBefore": ["PersonX flees the scene", "PersonX hides the cutting tool", "a police investigation is launched"],
    "HinderedBy": ["the object is too hard to cut", "someone interrupts PersonX", "the tool breaks mid-action"],
    "Causes": ["irreparable property damage", "emotional distress for the owner", "a police investigation"],
    "xReason": ["because PersonX wanted revenge on the owner", "because PersonX lost control of their temper"],
    "isFilledBy": ["a valuable painting", "a piece of antique furniture", "a rare artifact"]
  },
  {
    "crime_category": "Violent Crimes",
    "crime_subcategory": "Assault",
    "brief_context": "PersonX uses a bladed weapon to physically cut a person in half or inflict a severe cutting wound, constituting aggravated assault or attempted homicide.",
    "xIntent": ["to seriously injure PersonY", "to eliminate a threat", "to act out violent impulses"],
    "xNeed": ["a bladed weapon", "physical proximity to the victim", "absence of witnesses"],
    "xAttr": ["violent", "dangerous", "unstable", "predatory"],
    "xEffect": ["PersonX faces serious criminal charges", "PersonX may be injured in a struggle", "PersonX is identified as a violent offender"],
    "xReact": ["rage during the act", "panic afterwards", "potential remorse"],
    "xWant": ["to flee before authorities arrive", "to dispose of the weapon", "to find an alibi"],
    "oEffect": ["PersonY suffers severe physical injury", "PersonY may require emergency medical attention", "PersonY experiences lasting trauma"],
    "oReact": ["terror", "pain", "shock"],
    "oWant": ["to escape", "to call for help", "to identify the attacker to police"],
    "isAfter": ["a confrontation or dispute escalates", "PersonX acquires a weapon", "PersonX follows PersonY to an isolated location"],
    "HasSubEvent": ["PersonX draws or retrieves the weapon", "PersonX closes the distance with PersonY", "PersonX delivers the blow"],
    "isBefore": ["PersonX flees the scene", "emergency services are called", "law enforcement begins a manhunt"],
    "HinderedBy": ["PersonY fights back", "bystanders intervene", "PersonX loses the weapon"],
    "Causes": ["grievous bodily harm", "activation of emergency response", "a violent crime investigation"],
    "xReason": ["because PersonX harbored deep resentment toward PersonY", "because PersonX acted in a moment of uncontrolled rage"],
    "isFilledBy": ["a person", "a victim targeted by PersonX"]
  }
]

### OUTPUT SCHEMA (Strict JSON List)
[
  {
    "crime_category": "String — EXACTLY ONE category from the Forensic Taxonomy",
    "crime_subcategory": "String — EXACTLY ONE subcategory from the Forensic Taxonomy",
    "brief_context": "String",
    "xIntent": ["String", ..., "String"],
    "xNeed": ["String", ..., "String"],
    "xAttr": ["String", ..., "String"],
    "xEffect": ["String", ..., "String"],
    "xReact": ["String", ..., "String"],
    "xWant": ["String", ..., "String"],
    "oEffect": ["String", ..., "String"],
    "oReact": ["String", ..., "String"],
    "oWant": ["String", ..., "String"],
    "isAfter": ["String", ..., "String"],
    "HasSubEvent": ["String", ..., "String"],
    "isBefore": ["String", ..., "String"],
    "HinderedBy": ["String", ..., "String"],
    "Causes": ["String", ..., "String"],
    "xReason": ["String", ..., "String"],
    "isFilledBy": ["String", ..., "String"]
  }
]
"""

# Prompt used to generate synthetic events for specific categories (used in core/synthetic.py)
SYNTHETIC_PROMPT = """
You are a Dataset Engineer for a Criminology AI.
Generate {count} distinct event templates related to "{category}".

REQUIREMENTS:
1. Format must be EXACTLY like ATOMIC dataset: "PersonX [verb] ..."
2. Use "PersonX" as the perpetrator.
3. Use "___" (3 underscores) as placeholders for objects/victims occasionally.
4. Topics must be purely forensic/criminal.

EXAMPLES:
- "PersonX breaks the ___ with a crowbar"
- "PersonX steals the identity of ___"
- "PersonX uploads a virus to ___"
- "PersonX threatens PersonY with ___"

OUTPUT FORMAT:
Return ONLY a JSON list of strings: ["template1", "template2", ...]
"""
# JUDGE & EVALUATION PROMPTS

# Prompt used by the LLM Judges to evaluate a generated event (used in core/judge.py)
JUDGE_SYSTEM_PROMPT = """You are an NLP annotation consistency evaluator. You assess whether an annotation is coherent and derivable from the event — NOT whether the event is actually criminal. Output ONLY valid JSON. Do NOT wrap in markdown or code blocks."""

JUDGE_PROMPT = """Event: "{event}"
Annotation: {prediction}

Evaluate coherence only. Reject if and only if one of these fails:

1. INTEGRITY: No empty required fields, gibberish, or corrupted text.
2. DERIVABILITY: crime_category/subcategory must be plausibly derivable from a reasonable reading of the event text OR from the event text together with the 'context' field. For neutral events, the 'context' field exists precisely to introduce a criminal scenario that the event text alone does not imply — this is expected and valid. Approve if the context provides a coherent, non-empty rationale that connects the event to the crime category, even if that connection requires the context to add new information. Reject only if the crime category is contradicted by the event text, or if the context is absent or incoherent.
3. CONSISTENCY: xIntent/xAttr/xEffect must not DIRECTLY contradict the event. Reject only on clear contradiction (e.g., xIntent claims deliberate aim at an outcome the event marks as accidental). Precursor states (frustration, anxiety) are not contradictions.
4. PROPORTIONALITY: For events containing "accidentally" or "by mistake", xIntent must not describe an intentional aggressive act toward a person or object, even if imprecisely aimed. A precursor *emotional state* (e.g., "felt frustrated") is acceptable; a precursor *aggressive action* (e.g., "to lash out", "to hit", "to throw") is not. Neutral actions (e.g., "to carry", "to examine", "to hand over") are always acceptable regardless of the event being accidental.

Do NOT reject because: the event seems innocent, criminality seems unlikely, or context is speculative but plausible.

When in doubt, APPROVE. Reject only on clear, unambiguous violations of the criteria above.

Return ONLY raw JSON, no markdown:
{{"vote":"approve"/"reject","score":<0-100>,"reason":"<If approved: exactly 'All criteria met.' — If rejected: criterion name + reason, MAX 30 WORDS.>"}}"""

# Could be implemented, not used in this work.
REWRITE_PROMPT = """
Prompt not used.
{event}
{json_data}
{feedback}
"""

def get_user_prompt(event_text: str) -> str:
    return f"""
    Event: "{event_text}"
    
    Task: Generate a JSON List of 1 or 2 criminal interpretations of the event above.
    - Try to generate 2 interpretations when possible, each from a DIFFERENT crime category or subcategory.
    - Both interpretations MUST be criminal. Do NOT include non-criminal, comedic, or everyday contexts.
    - If a deceptive or covert angle exists (e.g., a front business, a disguised operation), include it ONLY if it maps to a valid crime from the Forensic Taxonomy.
    
    If, and ONLY if, it is genuinely impossible to frame the event as any crime even in a deceptive context (e.g., 'PersonX breathes'), return exactly the string: "NOT POSSIBLE"
    """