import os
import glob
import re
import string
from kanjiconv import SudachiDictType
from kanjiconv import KanjiConv

# Define the directory paths
mozc_dir = "./mozc"
place_file = "./dic/place.txt"
names_file = "./dic/names.txt"
wiki_file = "./dic/wiki.txt"
neologd_file = "./dic/neologd.txt"

# Define output file paths
place_output_file = "./filtered_place.txt"
names_output_file = "./filtered_names.txt"
wiki_output_file = "./filtered_wiki.txt"
neologd_output_file = "./filtered_neologd.txt"

place_output_file_not_same = "./filtered_place_not_same.txt"
names_output_file_not_same = "./filtered_names_not_same.txt"
wiki_output_file_not_same = "./filtered_wiki_not_same.txt"
neologd_output_file_not_same = "./filtered_neologd_not_same.txt"

suffix_file = os.path.join(mozc_dir, "suffix.txt")

# Read all dictionary files from the Mozc directory
dictionary_files = sorted(glob.glob(os.path.join(mozc_dir, "dictionary0[0-9].txt")))

# Store first and last strings in sets for quick lookup
first_strings_set = set()
last_strings_set = set()

# Initialize KanjiConv for Hiragana conversion
kanji_conv = KanjiConv(sudachi_dict_type=SudachiDictType.FULL.value, separator="")

# Function to clean last string (remove only '(' and ')', keeping the content inside)
def clean_last_string(text):
    """Removes parentheses from a string."""
    return text.replace("(", "").replace(")", "")

# Process Mozc dictionary files to populate lookup sets
print("Processing Mozc dictionary files...")
for file in dictionary_files:
    with open(file, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                first_strings_set.add(parts[0])  # Store first string
                last_strings_set.add(parts[-1])  # Store last string as-is

# Read suffix.txt and store suffixes in a set
suffix_set = set()
if os.path.exists(suffix_file):
    with open(suffix_file, "r", encoding="utf-8") as f:
        for line in f:
            suffix = line.strip()
            if suffix:
                suffix_set.add(suffix)
print(f"Loaded {len(suffix_set)} suffixes.")

# Function to convert text to Hiragana
def to_hiragana(text):
    """Converts text to Hiragana using KanjiConv."""
    return kanji_conv.to_hiragana(text)

# Function to extract kana characters from a string
def extract_kana(text):
    """Extracts all Hiragana and Katakana characters from a string."""
    return set(re.findall(r'[ぁ-んァ-ヶー]', text))

def katakana_to_hiragana(text: str) -> str:
    """Converts Katakana to Hiragana and removes '・'."""
    text = text.replace("・", "")  # Remove middle dot
    return text.translate(str.maketrans(
        "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンァィゥェォッャュョー",
        "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんぁぃぅぇぉっゃゅょー"
    ))

# Main function to filter and process dictionary files
def filter_file(input_file, output_file, not_same_output_file, clean_last=False, remove_exclamation=False, extra_filter=False, require_filter=False, skip_long_entries=False):
    """
    Reads an input dictionary file, filters its content based on several rules,
    and writes the results to output files.
    """
    filtered_lines = []
    not_same_lines = []
    
    print(f"Processing {input_file}...")
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 5:
                continue  # Skip if there aren't enough fields

            first_str = parts[0]
            last_str = clean_last_string(parts[-1]) if clean_last else parts[-1]

            if skip_long_entries and len(first_str) > 16:
                continue

            # Skip entries where the reading contains symbols not present in the word
            symbol_pattern = re.compile(r'[^\wぁ-んァ-ン一-龥]')
            if symbol_pattern.search(last_str) and not symbol_pattern.search(first_str):
                continue

            # Skip entries starting with 'ん' as they are uncommon
            if first_str.startswith("ん"):
                continue

            if remove_exclamation:
                last_str = last_str.replace("!", "")

            # Normalize strings for comparison
            first_str_cleaned = first_str.replace("・", "").strip()
            last_str_hira = katakana_to_hiragana(last_str).strip()

            # Apply extra filtering logic for wiki and neologd
            if extra_filter:
                if "・" in last_str or "！" in last_str or "？" in last_str:
                    continue

            # Extract kana sets for reading validation
            kana_set_first = extract_kana(to_hiragana(first_str_cleaned))
            kana_set_last = extract_kana(last_str_hira)

            if require_filter:
                if first_str_cleaned == last_str_hira:
                    continue

                # Check if the reading contains kana not present in the original word's hiragana form
                if kana_set_last - kana_set_first:
                    print(f"Possibly incorrect reading: {first_str} -> {last_str}")
                    not_same_lines.append(line.strip())
                else:
                    # Add to filtered list if the reading is not already in the Mozc dictionary
                    if last_str not in last_strings_set:
                        print(f"\033[32mCorrect reading:\033[0m \033[34m{first_str} -> {last_str}\033[0m")
                        filtered_lines.append(line.strip())
            else:
                filtered_lines.append(line.strip())

    # Write filtered output
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(filtered_lines) + "\n")

    # Write potentially incorrect readings to a separate file
    if not_same_lines:
        with open(not_same_output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(not_same_lines) + "\n")

    print(f"Filtered output saved to {output_file}")
    if not_same_lines:
        print(f"Potentially incorrect readings saved to {not_same_output_file}")

# --- Main Execution ---

# Filter each source file with its specific rules
filter_file(place_file, place_output_file, place_output_file_not_same, clean_last=True)
filter_file(names_file, names_output_file, names_output_file_not_same)
filter_file(wiki_file, wiki_output_file, wiki_output_file_not_same, remove_exclamation=True, extra_filter=True, require_filter=True, skip_long_entries=True)
filter_file(neologd_file, neologd_output_file, neologd_output_file_not_same, remove_exclamation=True, extra_filter=True, require_filter=True, skip_long_entries=True)

# --- Compare Filtered Wiki and NEologd Dictionaries ---

# Define file paths for comparison
wiki_filtered_file = "filtered_wiki.txt"
neologd_filtered_file = "filtered_neologd.txt"

common_output = "wiki_neologd_common.txt"
only_wiki_output = "only_wiki.txt"
only_neologd_output = "only_neologd.txt"

def load_data(file_path):
    """Loads dictionary data into a dictionary with (word, reading) as key."""
    data_dict = {}
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 2:
                continue
            first_str, last_str = parts[0], parts[-1]
            data_dict[(first_str, last_str)] = line.strip()
    return data_dict

def write_data(file_path, data_dict, keys):
    """Writes dictionary entries to a file from a given set of keys."""
    with open(file_path, "w", encoding="utf-8") as f:
        for key in sorted(keys):
            f.write(f"{data_dict[key]}\n")

print("Comparing filtered wiki and neologd files...")
# Load the filtered data
wiki_data = load_data(wiki_filtered_file)
neologd_data = load_data(neologd_filtered_file)

# Find common and unique entries based on (word, reading) tuples
common_keys = set(wiki_data.keys()) & set(neologd_data.keys())
only_wiki_keys = set(wiki_data.keys()) - set(neologd_data.keys())
only_neologd_keys = set(neologd_data.keys()) - set(wiki_data.keys())

# Write the comparison results to files
write_data(common_output, wiki_data, common_keys)
write_data(only_wiki_output, wiki_data, only_wiki_keys)
write_data(only_neologd_output, neologd_data, only_neologd_keys)

print(f"Common entries saved to {common_output}")
print(f"Unique wiki entries saved to {only_wiki_output}")
print(f"Unique neologd entries saved to {only_neologd_output}")
print("Script finished.")
