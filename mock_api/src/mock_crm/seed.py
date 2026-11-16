"""Fixed fictional seed data. No randomness."""

COMPANIES = [
    ("Brightwater Logistics", "Logistics", "https://brightwater.example.com"),
    ("Harborline Foods", "Food and beverage", "https://harborline.example.com"),
    ("Pinecrest Software", "Software", "https://pinecrest.example.com"),
    ("Redfern Builders", "Construction", "https://redfern.example.com"),
    ("Silverleaf Health", "Healthcare", "https://silverleaf.example.com"),
    ("Northgate Energy", "Energy", "https://northgate.example.com"),
    ("Willow and Finch Retail", "Retail", "https://willowfinch.example.com"),
    ("Copperfield Analytics", "Consulting", "https://copperfield.example.com"),
    ("Lakeshore Education", "Education", "https://lakeshore.example.com"),
    ("Stonebridge Insurance", "Insurance", "https://stonebridge.example.com"),
]

PEOPLE = [
    "Ava Martin", "Ben Carter", "Chloe Diaz", "Daniel Evans", "Emma Foster",
    "Felix Grant", "Grace Hughes", "Henry Ito", "Isla Jensen", "Jack Kim",
    "Kara Lopez", "Liam Moore", "Mia Novak", "Noah Owens", "Olivia Park",
    "Paul Quinn", "Quinn Reed", "Rosa Singh", "Sam Turner", "Tina Usher",
    "Victor Vance", "Wendy Xu", "Yusuf Young", "Zoe Zimmer",
]  # fmt: skip

STAGES = ["lead", "qualified", "proposal", "won", "lost"]


def contacts() -> list[tuple]:
    rows = []
    for i, name in enumerate(PEOPLE):
        slug = name.lower().replace(" ", ".")
        company_id = (i % len(COMPANIES)) + 1
        rows.append((name, f"{slug}@example.com", f"555-01{i:02d}", company_id))
    return rows


def deals() -> list[tuple]:
    rows = []
    for i in range(20):
        company_id = (i % len(COMPANIES)) + 1
        contact_id = ((i * 3) % len(PEOPLE)) + 1
        kind = ["Pilot", "Renewal", "Expansion", "Rollout"][i % 4]
        title = f"{COMPANIES[company_id - 1][0]} - {kind}"
        rows.append((title, 5000.0 + i * 2500, STAGES[i % len(STAGES)], company_id, contact_id))
    return rows


def tasks() -> list[tuple]:
    rows = []
    for i in range(16):
        rows.append(
            (
                f"Follow up #{i + 1}",
                f"2026-12-{(i % 28) + 1:02d}",
                int(i % 4 == 0),
                (i % len(PEOPLE)) + 1,
                (i % len(COMPANIES)) + 1,
            )
        )
    return rows


def notes() -> list[tuple]:
    rows = []
    for i in range(18):
        rows.append(
            (
                f"Call summary {i + 1}: discussed requirements and next steps.",
                f"2026-10-{(i % 28) + 1:02d}T09:{i:02d}:00",
                (i * 2 % len(PEOPLE)) + 1,
                (i * 2 % len(COMPANIES)) + 1,
            )
        )
    return rows
