import pandas as pd
import os
import re

# Expanded list of word roots.
# Regex will capture all inflections (e.g., “attack” -> “attacks,” “attacked”).
FORENSIC_ROOTS = [
    # VIOLENCE
    "kill", "murder", "hurt", "attack", "hit", "beat", "fight", "shoot", "stab",
    "threat", "force", "abuse", "assault", "damage", "destroy", "burn", "fire",
    "punch", "slap", "strangle", "choke", "kick", "wound", "injure",

    # PROPERTY
    "steal", "thief", "rob", "burglar", "break", "enter", "trespass", "smash",
    "vandal", "loot", "shoplift", "snatch", "pickpocket",

    # FINANCIAL CRIMES / FRAUD
    "fraud", "scam", "fake", "deceive", "trick", "lie", "bribe", "money",
    "bank", "account", "credit", "tax", "launder", "embezzle", "forg",

    # CYBER
    "hack", "password", "phish", "malware", "virus", "access", "download",
    "upload", "online", "email", "data", "file",

    # LEGAL / POLICE
    "illegal", "law", "prison", "jail", "arrest", "cop", "police", "court",
    "sue", "guilt", "suspect", "victim", "witness", "flee", "escape",

    # TRAFFICKING / DRUGS / WEAPONS
    "drug", "cocaine", "heroin", "weed", "pill", "dealer", "trafficking",
    "weapon", "gun", "knife", "bomb", "pistol", "rifle", "poison",

    # AMBIGUOUS ACTIONS
    "take", "grab", "get", "obtain", "open", "lock", "hide", "conceal",
    "follow", "watch", "track", "push", "pull", "drag", "throw", "drop",
    "cut", "slice", "sell", "buy", "pay", "use", "give"
]

# Let's compile a single optimized Regex.
PATTERN = re.compile(r'\b(' + '|'.join(map(re.escape, FORENSIC_ROOTS)) + r')', re.IGNORECASE)


def is_forensic_candidate(event: str) -> bool:
    """
    Check if the event contains a forensic root using Regex.
    Much more permissive than the set intersection.
    """
    if not isinstance(event, str):
        return False

    # Search for the pattern in the text
    return bool(PATTERN.search(event))


def run_filtering(input_path: str, output_path: str):
    print(f"Start forensic filtering using Regex on: {input_path}")

    if not os.path.exists(input_path):
        print("Input file not found.")
        return 0

    df = pd.read_csv(input_path)
    col_name = 'event' if 'event' in df.columns else df.columns[0]
    total_rows = len(df)

    # Apply filter
    print("Analysis in progress (may take a few seconds)...")
    filtered_df = df[df[col_name].apply(is_forensic_candidate)]

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    filtered_df.to_csv(output_path, index=False)

    kept = len(filtered_df)
    print(f"Filtering completed.")
    print(f"Original total: {total_rows}")
    print(f"Forensic events held: {kept} ({kept / total_rows:.1%})")
    print(f"Saved in: {output_path}")

    return kept