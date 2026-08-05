import json

d = json.load(open("data/ground_truth/rules_ground_truth.json", encoding="utf-8"))

for program in ["AIT", "IT"]:
    print(f"\n========== {program} ==========")
    rules = d["programs"][program]
    for c in rules:
        has_content = bool(c.get("values")) or bool(c.get("summary"))
        print(f"{c['category']:35s} present={c['present']!s:6s} has_values_or_summary={has_content}")

for program in ["AIT", "IT"]:
    rules = {c["category"]: c for c in d["programs"][program]}
    print(f"\n========== {program} (categories with content) ==========")
    for cat, c in rules.items():
        if c.get("values") or c.get("summary"):
            print(json.dumps(c, ensure_ascii=False, indent=2))        