import random
from typing import List


# TODO: Add non-binary
def get_pronouns(gender: str):
    if gender == "male":
        return {"subj": "he", "obj": "him", "poss": "his"}
    else:
        return {"subj": "she", "obj": "her", "poss": "her"}


def format_income_description(income: int):
    if income < 20000:
        return "tight budget, living paycheck to paycheck"
    elif income < 40000:
        return "modest but manageable, with careful planning"
    elif income < 70000:
        return "comfortable, allowing for some discretionary spending"
    else:
        return "solid, with room for savings and occasional luxuries"


def pick_lifestyle_items(lifestyle_list: List[str], count=3):
    if not lifestyle_list:
        return []
    k = min(count, len(lifestyle_list))
    return random.sample(lifestyle_list, k)
