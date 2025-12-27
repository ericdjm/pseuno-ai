"""
Prompt Variants Package

Each variant file registers itself when imported.
To add a new variant:
1. Create a new file (e.g., v5_my_variant.py)
2. Define your prompts using specs from app.prompts.specs
3. Call register_variant() with your variant config
4. Add the import below

That's it! The variant will appear in the UI automatically.
"""

# Import all variants to trigger registration
# Add new variants here in the order you want them to appear
from app.prompts.variants import v1_baseline
from app.prompts.variants import v2_max_mode
from app.prompts.variants import v3_two_step
from app.prompts.variants import v4_lyric_profile
from app.prompts.variants import v5_hybrid

# List of all variant modules (for documentation)
ALL_VARIANTS = [
    v1_baseline,
    v2_max_mode,
    v3_two_step,
    v4_lyric_profile,
    v5_hybrid,
]

