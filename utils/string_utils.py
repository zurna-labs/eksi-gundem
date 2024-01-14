import re


def split_entry_count_from_title(title):
    match = re.search(r'(.*?)(\d+)$', title)
    if match:
        text = match.group(1).strip()
        number = int(match.group(2))
        return text, number
    else:
        return title, None