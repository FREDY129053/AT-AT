import hashlib
import random
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional

from ab_agent.services.population_gen.gen_helpers import format_income_description, get_pronouns, pick_lifestyle_items
from ab_agent.services.population_gen.locations import LOCATIONS
from ab_agent.services.population_gen.names import MENS, WOMENS
from ab_agent.services.population_gen.persona_cluster_ds import PERSONA_CLUSTERS

####################################################
##########       SECTION GENERATION       ##########
####################################################
def generate_background(
    name: str,
    age: int,
    gender: str,
    job: Optional[str],
    education: str,
    lifestyle: List[str],
    cluster_key: str,
    city: str,
    state: str,
) -> str:
    pronoun = get_pronouns(gender)
    job_str = job if job else "person"

    intros = [
        f"{name} is a {age}-year-old {job_str} living in {city}, {state}.",
        f"Meet {name}, a {age}-year-old {job_str} from {city}, {state}.",
        f"{name}, {age}, works as a {job_str} and calls {city}, {state} home.",
    ]

    background = random.choice(intros)

    match cluster_key:
        case "young_professional":
            exp = max(0, age - 22)
            background += f" After earning {pronoun['poss']} {education} degree, {pronoun['subj']} dove into the {job_str} field and has accumulated about {exp} years of experience. {pronoun['subj'].capitalize()} is passionate about {lifestyle[0] if lifestyle else 'professional growth'} and {lifestyle[1] if len(lifestyle) > 1 else 'networking'}."
        case "teen_student":
            background += f" {pronoun['subj'].capitalize()} is still in school and lives with {pronoun['poss']} family. Outside of classes, {pronoun['subj']} enjoys {lifestyle[0] if lifestyle else 'hanging out with friends'} and {lifestyle[1] if len(lifestyle) > 1 else 'playing video games'}."
        case "poor_worker":
            background += f" Despite working long hours, often taking overtime or a second job, {pronoun['subj']} struggles to make ends meet. {pronoun['subj'].capitalize()} relies on public transport and is resourceful with DIY repairs."
        case "middle_class_parent":
            background += f" As a parent, {pronoun['subj']} juggles a busy family life with {pronoun['poss']} career. Weekends are often filled with {lifestyle[0] if lifestyle else 'kids’ activities'} and {lifestyle[1] if len(lifestyle) > 1 else 'home improvement projects'}."
        case "retired":
            background += f" After decades in the workforce, {pronoun['subj']} now enjoys a well-earned retirement. {pronoun['subj'].capitalize()} spends time on {lifestyle[0] if lifestyle else 'gardening'} and cherishes moments with grandchildren."
        case "college_student":
            background += f" {pronoun['subj'].capitalize()} is currently pursuing a degree while working part-time as a {job if job != 'part-time' else 'student worker'}. Between exams and social life, {pronoun['subj']} is navigating the challenges of {lifestyle[0] if lifestyle else 'campus life'}."
        case "unemployed":
            background += f" {pronoun['subj'].capitalize()} is actively seeking employment and spends most days sending out applications, attending interviews, and taking online courses to improve {pronoun['poss']} skills."
        case _:
            background += f" {pronoun['subj'].capitalize()} leads a life centered around {lifestyle[0] if lifestyle else 'daily routines'}."

    return background


def generate_financial_situation(
    income: int, lifestyle: List[str], cluster_key: str, gender: str
) -> str:
    p = get_pronouns(gender)
    income_desc = format_income_description(income)
    text = f"{p['subj'].capitalize()} has an annual income of around ${income:,}, which means a {income_desc}."

    if "budgeting" in lifestyle or cluster_key == "poor_worker":
        text += f" {p['subj'].capitalize()} meticulously tracks every expense and relies on discount stores."
    if "saving for college" in lifestyle:
        text += (
            f" A portion of {p['poss']} earnings goes into a college fund for the kids."
        )
    if "student loan payments" in lifestyle:
        text += f" Monthly student loan payments take a significant chunk, but {p['subj']} is slowly paying them down."
    if "side hustles" in lifestyle or cluster_key == "unemployed":
        text += f" To supplement {p['poss']} income, {p['subj']} takes on freelance gigs or odd jobs."
    if "travel" in lifestyle:
        text += (
            f" {p['subj'].capitalize()} sets aside money for travel whenever possible."
        )
    if "investing" not in lifestyle and income > 70000:
        text += f" With a stable income, {p['subj']} is starting to build a small investment portfolio."

    if not any(x in text for x in [".", "!", "?"][-1]):
        text += f" {p['subj'].capitalize()} tries to keep {p['poss']} finances under control and avoid unnecessary debt."

    return text


def generate_shopping_habits(
    lifestyle: List[str], cluster_key: str, gender: str, income: int
) -> str:
    p = get_pronouns(gender)
    interests = []

    keyword_map = {
        "gaming": ["video games", "gaming peripherals", "collectibles"],
        "tech gadgets": ["the latest gadgets", "smart home devices", "electronics"],
        "music": ["vinyl records", "concert tickets", "musical instruments"],
        "fitness": ["sportswear", "gym equipment", "protein supplements"],
        "travel": ["luggage", "travel accessories", "souvenirs"],
        "parenting": ["kids' clothes", "toys", "baby gear"],
        "home improvement": ["tools", "home decor", "DIY supplies"],
        "cooking": ["kitchen gadgets", "gourmet ingredients", "cookware"],
        "art": ["art supplies", "prints", "craft materials"],
        "books": ["books", "e-readers"],
        "fashion": ["clothing", "accessories", "shoes"],
        "outdoors": ["camping gear", "hiking boots"],
    }

    for kw, items in keyword_map.items():
        if any(kw in ls for ls in lifestyle):
            interests.extend(items)

    if not interests:
        if cluster_key == "teen_student":
            interests = ["trendy clothes", "fast food", "video games"]
        elif cluster_key == "young_professional":
            interests = ["coffee shop visits", "workout gear", "smart casual wear"]
        elif cluster_key == "middle_class_parent":
            interests = ["groceries in bulk", "family‑size products", "kids' stuff"]
        elif cluster_key == "retired":
            interests = "gardening supplies, books, and gifts for grandchildren".split(
                ", "
            )
        elif cluster_key == "poor_worker":
            interests = ["essential groceries", "budget brands", "second-hand items"]
        elif cluster_key == "college_student":
            interests = ["textbooks", "snacks", "cheap furniture"]
        elif cluster_key == "unemployed":
            interests = ["absolute necessities", "discount items"]
        else:
            interests = ["everyday essentials"]

    text = f"When it comes to shopping, {p['subj']} tends to focus on {', '.join(interests[:2])}."
    if income > 50000:
        text += f" {p['subj'].capitalize()} doesn't mind splurging on quality items, especially if they last."
    else:
        text += f" Price is a major factor, so {p['subj']} often hunts for sales or buys second-hand."

    if "online" in str(lifestyle) or cluster_key in [
        "young_professional",
        "teen_student",
    ]:
        text += f" {p['subj'].capitalize()} prefers online shopping for the convenience and reads reviews thoroughly before buying."
    else:
        text += f" {p['subj'].capitalize()} likes to see products in person and often visits local stores."

    return text


def generate_professional_life(job, cluster_key, gender, lifestyle):
    p = get_pronouns(gender)
    if not job or job == "unemployed":
        return f"{p['subj'].capitalize()} is currently not employed and spends weekdays searching for job openings, updating {p['poss']} resume, and networking online."

    # Generic start
    text = f"As a {job}, {p['subj']} typically works"

    if cluster_key == "young_professional":
        text += f" in a modern office or remotely, juggling multiple projects and tight deadlines. {p['subj'].capitalize()} frequently collaborates with cross-functional teams and attends networking events."
    elif cluster_key == "poor_worker":
        text += f" long shifts, often involving physical labor. The work can be exhausting, but {p['subj']} appreciates the steady paycheck."
    elif cluster_key == "middle_class_parent":
        text += f" a standard 9-to-5 schedule, though {p['subj']} occasionally brings work home to accommodate family needs."
    elif cluster_key == "retired":
        if "part-time work" in job:
            text += f" a few days a week at a {job} role, which keeps {p['obj']} engaged without the stress of a full-time career."
        else:
            return f"{p['subj'].capitalize()} is fully retired and fills {p['poss']} days with {lifestyle[0] if lifestyle else 'leisure activities'}."
    elif cluster_key == "college_student":
        text += f" part-time while attending classes. {p['subj'].capitalize()} balances coursework, study groups, and shifts at {job}."
    elif cluster_key == "teen_student":
        text += f" after school and on weekends. The job helps {p['obj']} earn some spending money and gain work experience."
    else:
        text += f" in a typical {cluster_key.replace('_', ' ')} setting."

    if "home office" in lifestyle:
        text += f" {p['subj'].capitalize()} has set up a comfortable home office to stay productive."
    if "coworking" in lifestyle:
        text += f" {p['subj'].capitalize()} enjoys the buzz of coworking spaces and often works from there."
    if "deadlines" in lifestyle or "stress" in lifestyle:
        text += f" Meeting deadlines can be stressful, but {p['subj']} thrives under pressure."

    return text


def generate_personal_style(cluster_key: str, gender: str, lifestyle: List[str]) -> str:
    p = get_pronouns(gender)

    cluster_styles = {
        "teen_student": [
            "casual and trendy",
            "hoodies and sneakers",
            "graphic tees and jeans",
        ],
        "poor_worker": [
            "practical and durable",
            "work boots and jeans",
            "comfortable, no-frills clothing",
        ],
        "young_professional": [
            "smart casual",
            "blazers and chinos",
            "minimalist and polished",
        ],
        "middle_class_parent": [
            "comfortable yet presentable",
            "jeans and a nice top",
            "practical for school runs",
        ],
        "retired": [
            "relaxed and comfortable",
            "sweaters and walking shoes",
            "easy-care fabrics",
        ],
        "college_student": [
            "laid-back and eclectic",
            "campus wear",
            "thrifted finds and band tees",
        ],
        "unemployed": ["simple and utilitarian", "whatever is clean and affordable"],
    }

    base_style = cluster_styles.get(cluster_key, ["versatile and practical"])
    text = f"{p['subj'].capitalize()} has a {random.choice(base_style)} fashion sense."

    if "edgy" in lifestyle or "art" in str(lifestyle):
        text += f" {p['subj'].capitalize()} loves bold patterns, graphic prints, and making a statement with accessories."
    if "fitness" in lifestyle:
        text += f" Athletic wear makes up a good part of {p['poss']} wardrobe, even outside the gym."
    if "outdoors" in lifestyle:
        text += f" Functionality matters – {p['subj']} often wears durable, weather-resistant clothing."
    if "minimalist" in lifestyle:
        text += f" {p['subj'].capitalize()} prefers a minimalist wardrobe with neutral colors and timeless pieces."

    shoes = random.choice(
        ["sneakers", "boots", "comfortable flats", "loafers", "sandals"]
    )
    text += f" On {p['poss']} feet, you'll usually find {shoes}."

    return text


####################################################
##########        PERSON GENERATION       ##########
####################################################
def generate_persona(cluster_key=None):
    if cluster_key is None:
        cluster_key = random.choice(list(PERSONA_CLUSTERS.keys()))

    cluster = PERSONA_CLUSTERS[cluster_key]

    age = random.randint(*cluster["age"])
    education = random.choice(cluster["education"])
    income = random.randint(*cluster["income"])
    job = random.choice(cluster.get("jobs", [""])) or None  # handle empty jobs list
    lifestyle = pick_lifestyle_items(cluster.get("lifestyle", []), count=4)

    gender = random.choice(["male", "female"])
    name = random.choice(MENS if gender == "male" else WOMENS)

    city, state = random.choice(LOCATIONS)

    sections = {
        "Persona": name,
        "Background": "\n"
        + generate_background(
            name, age, gender, job, education, lifestyle, cluster_key, city, state
        ),
        "Demographics": "",
        "Age": age,
        "Gender": gender,
        "Education": education,
        "Financial Situation": "\n"
        + generate_financial_situation(income, lifestyle, cluster_key, gender),
        "Shopping Habits": "\n"
        + generate_shopping_habits(lifestyle, cluster_key, gender, income),
        "Professional Life": "\n"
        + generate_professional_life(job, cluster_key, gender, lifestyle),
        "Personal Style": "\n"
        + generate_personal_style(cluster_key, gender, lifestyle),
    }

    output = []
    for title, content in sections.items():
        output.append(f"{title}: {content}\n")

    return (
        "\n".join(output).strip(),
        cluster_key,
        uuid.UUID(int=random.Random().getrandbits(128)),
    )


####################################################
##########          SPLIT ON GROUPS       ##########
####################################################
@dataclass
class Person:
    description: str
    group: str
    id: uuid.UUID


COUNT = 6
persons = []
for i in range(COUNT):
    desc, group, id = generate_persona()
    persons.append(Person(desc, group, id))


grouped = defaultdict(list)
for person in persons:
    grouped[person.group].append(person)


def get_hash(s: str) -> int:
    h = hashlib.md5(s.encode("utf-8")).digest()
    return int.from_bytes(h, "big")


def split_array(persons):
    items = [(get_hash(str(p.id)), p) for p in persons]
    items.sort(key=lambda x: x[0])
    A, B = [], []
    for i, (_, p) in enumerate(items):
        (A if (i % 2 == 0) else B).append(p)

    return A, B


A: List[Person] = []
B: List[Person] = []
for persons in grouped.values():
    a_part, b_part = split_array(persons)
    A.extend(a_part)
    B.extend(b_part)


def rebalance_min_moves(A: list, B: list):
    diff = len(A) - len(B)
    if abs(diff) <= 1:
        return A, B
    if diff > 0:
        move = diff // 2 if diff % 2 == 0 else (diff + 1) // 2
        B.extend(A[-move:])
        del A[-move:]
    else:
        move = (-diff) // 2 if (-diff) % 2 == 0 else ((-diff) + 1) // 2
        A.extend(B[-move:])
        del B[-move:]
    return A, B


A, B = rebalance_min_moves(A, B)

len_a, len_b = len(A), len(B)
print(f"Count of people in A = {len_a}")
print(f"Count of people in B = {len_b}")

for i in range(len(A)):
    print(f"Group from A is '{A[i].group}'")
print("--------------------------------")
for i in range(len(B)):
    print(f"Group from B is '{B[i].group}'")

# with open('output_file.txt', 'w') as f:
#     f.write(generate_persona())
