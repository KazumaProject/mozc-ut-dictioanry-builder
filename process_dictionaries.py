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

place_output_file = "./filtered_place.txt"
names_output_file = "./filtered_names.txt"
wiki_output_file = "./filtered_wiki.txt"
neologd_output_file = "./filtered_neologd.txt"

place_output_file_not_same = "./filtered_place_not_same.txt"
names_output_file_not_same = "./filtered_names_not_same.txt"
wiki_output_file_not_same = "./filtered_wiki_not_same.txt"
neologd_output_file_not_same = "./filtered_neologd_not_same.txt"

suffix_file = os.path.join(mozc_dir, "suffix.txt")

# Read all dictionary files
dictionary_files = sorted(glob.glob(os.path.join(mozc_dir, "dictionary0[0-9].txt")))

# Store first and last strings in sets for quick lookup
first_strings_set = set()
last_strings_set = set()

kanji_conv = KanjiConv(sudachi_dict_type=SudachiDictType.FULL.value, separator="")

# Function to clean last string (remove only '(' and ')', keeping the content inside)
def clean_last_string(text):
    return text.replace("(", "").replace(")", "")

# Process dictionary files
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

# Function to convert text to Hiragana
def to_hiragana(text):
    return kanji_conv.to_hiragana(text)

# Function to extract kana characters from a string
def extract_kana(text):
    return set(re.findall(r'[ぁ-んァ-ヶー]', text))

def katakana_to_hiragana(text: str) -> str:
    """ Convert Katakana to Hiragana and remove '・' """
    text = text.replace("・", "")  # Remove middle dot
    return text.translate(str.maketrans(
        "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンァィゥェォッャュョー",
        "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんぁぃぅぇぉっゃゅょー"
    ))

# Function to filter and process files
def filter_file(input_file, output_file, not_same_output_file, clean_last=False, remove_exclamation=False, extra_filter=False, require_filter=False, skip_long_entries=False):
    filtered_lines = []
    not_same_lines = []

    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 5:
                continue  # Skip if there aren't enough fields

            first_str = parts[0]  
            last_str = clean_last_string(parts[-1]) if clean_last else parts[-1] 

            if skip_long_entries and len(first_str) > 16:
                continue

            symbol_pattern = re.compile(r'[^\wぁ-んァ-ン一-龥]')

            if symbol_pattern.search(last_str) and not symbol_pattern.search(first_str):
                continue

            if first_str.startswith("ん"):
                continue

            if remove_exclamation:
                last_str = last_str.replace("!", "")

            # Normalize strings
            first_str_cleaned = first_str.replace("・", "").strip()
            last_str_hira = katakana_to_hiragana(last_str).strip()

            # Extra filtering logic
            if extra_filter:
                if "・" in last_str or "！" in last_str or "？" in last_str:
                    continue

            # Extract kana sets
            kana_set_first = extract_kana(to_hiragana(first_str_cleaned))  
            kana_set_last = extract_kana(last_str_hira)

            if require_filter:
                if first_str_cleaned == last_str_hira:
                    continue  

                if kana_set_last - kana_set_first:
                    print(f"Possibly incorrect reading: {first_str} -> {last_str}")
                    not_same_lines.append(line.strip())  
                else:
                    # if first_str not in first_strings_set and last_str not in last_strings_set:
                    #     print(f"\033[32mCorrect reading:\033[0m \033[34m{first_str} -> {last_str}\033[0m")
                    #     filtered_lines.append(line.strip())  
                    if last_str not in last_strings_set:
                        print(f"\033[32mCorrect reading:\033[0m \033[34m{first_str} -> {last_str}\033[0m")
                        filtered_lines.append(line.strip())   
            else:
                filtered_lines.append(line.strip())  

    # Write filtered output
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(filtered_lines) + "\n")

    if not_same_lines:
        with open(not_same_output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(not_same_lines) + "\n")

    print(f"Filtered output saved to {output_file}")
    print(f"Potentially incorrect readings saved to {not_same_output_file}")

# Filter each file with the appropriate rule and generate the new output
filter_file(place_file, place_output_file, place_output_file_not_same, clean_last=True, require_filter=False, skip_long_entries=False)
filter_file(names_file, names_output_file, names_output_file_not_same, clean_last=False, require_filter=False, skip_long_entries=False)
filter_file(wiki_file, wiki_output_file, wiki_output_file_not_same, clean_last=False, remove_exclamation=True, extra_filter=True, require_filter=True, skip_long_entries=True)
filter_file(neologd_file, neologd_output_file, neologd_output_file_not_same, clean_last=False, remove_exclamation=True, extra_filter=True, require_filter=True, skip_long_entries=True)

# File paths
wiki_file = "filtered_wiki.txt"
neologd_file = "filtered_neologd.txt"

common_output = "wiki_neologd_common.txt"
only_wiki_output = "only_wiki.txt"
only_neologd_output = "only_neologd.txt"

# Load data from files into dictionaries
def load_data(file_path):
    data_dict = {}  # Store first_str as key and full line as value
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 2:
                continue  # Skip invalid lines
            first_str, last_str = parts[0], parts[-1]
            data_dict[(first_str, last_str)] = line.strip()  # Store full line
    return data_dict

# Load data
wiki_data = load_data(wiki_file)
neologd_data = load_data(neologd_file)

# Find common and unique entries
common_keys = set(wiki_data.keys()) & set(neologd_data.keys())  # Common keys (first_str, last_str)
only_wiki_keys = set(wiki_data.keys()) - set(neologd_data.keys())  # Only in wiki
only_neologd_keys = set(neologd_data.keys()) - set(wiki_data.keys())  # Only in neologd

# Write results to files
def write_data(file_path, data_dict, keys):
    with open(file_path, "w", encoding="utf-8") as f:
        for key in sorted(keys):  # Sort for consistency
            f.write(f"{data_dict[key]}\n")

write_data(common_output, wiki_data, common_keys)  # Use values from wiki.txt for common entries
write_data(only_wiki_output, wiki_data, only_wiki_keys)
write_data(only_neologd_output, neologd_data, only_neologd_keys)

print(f"Common entries saved to {common_output} (using values from wiki.txt)")
print(f"Unique wiki entries saved to {only_wiki_output}")
print(f"Unique neologd entries saved to {only_neologd_output}")
