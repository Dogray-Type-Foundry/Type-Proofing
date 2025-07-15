#!/usr/bin/env python3
# Script to extract the accented dictionary from the original prooftexts.py

import re

# Read the original file
with open(
    "/Users/josesole/local/github/Type-Proofing/prooftexts_original.py",
    "r",
    encoding="utf-8",
) as f:
    content = f.read()

# Find the start of accentedDict
start_marker = "accentedDict = {"
start_pos = content.find(start_marker)

if start_pos == -1:
    print("Could not find accentedDict definition")
    exit(1)

# Find the end by counting braces
brace_count = 0
current_pos = start_pos + len(start_marker) - 1  # Start at the opening brace
end_pos = current_pos

for i, char in enumerate(content[current_pos:], current_pos):
    if char == "{":
        brace_count += 1
    elif char == "}":
        brace_count -= 1
        if brace_count == 0:
            end_pos = i + 1
            break

# Extract the dictionary definition
dict_content = content[start_pos:end_pos]

# Write to new file
with open(
    "/Users/josesole/local/github/Type-Proofing/accented_dictionary.py",
    "w",
    encoding="utf-8",
) as f:
    f.write(
        "# Accented Dictionary - Large collection of accented characters and corresponding word lists\n"
    )
    f.write(
        "# This contains character sets for various languages with accented/diacritical marks\n\n"
    )
    f.write("# Complete dictionary extracted from original prooftexts.py\n")
    f.write(dict_content)
    f.write("\n\n")
    f.write("# Function to get words for a specific accented character\n")
    f.write("def get_accented_words(character):\n")
    f.write('    """Get word list for a specific accented character"""\n')
    f.write("    return accentedDict.get(character, [])\n\n")
    f.write("# Function to get all accented characters\n")
    f.write("def get_accented_characters():\n")
    f.write('    """Get all available accented characters"""\n')
    f.write("    return list(accentedDict.keys())\n\n")
    f.write("# Function to get random accented words\n")
    f.write("def get_random_accented_words(count=100):\n")
    f.write('    """Get a random selection of accented words"""\n')
    f.write("    import random\n")
    f.write("    all_words = []\n")
    f.write("    for word_list in accentedDict.values():\n")
    f.write("        all_words.extend(word_list)\n")
    f.write("    return random.sample(all_words, min(count, len(all_words)))\n")

print("Extracted accented dictionary successfully!")
