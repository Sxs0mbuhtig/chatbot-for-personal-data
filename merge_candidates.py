import json

def merge_approved_candidates(approved_ids: list):
    with open("staging/etymology_note_candidates.json", "r", encoding="utf-8") as f:
        candidates = json.load(f)

    with open("production/etymology_note.json", "r", encoding="utf-8") as f:
        master = json.load(f)

    existing_ids = {item["id"] for item in master}

    for candidate in candidates:
        if candidate["id"] in approved_ids and candidate["id"] not in existing_ids:
            master.append(candidate)

    with open("production/etymology_note.json", "w", encoding="utf-8") as f:
        json.dump(master, f, ensure_ascii=False, indent=2)

    print(f"Successfully merged {len(approved_ids)} new variant entries into production!")
