from pathlib import Path
from typing import Literal
from langchain_core.prompts import PromptTemplate


BASE_DIR = "./src/api_agent/prompts/"
PromptFormat = Literal['jinja2', 'mustache', 'f-string']

def get_template(dir: str, filename: str) -> str:
    with open(Path(dir) / filename, "r") as f:
        return f.read()
    
def get_prompt(template: str, format: PromptFormat) -> PromptTemplate:
    return PromptTemplate.from_template(template=template, template_format=format)

def get_prompt_from_file(dir: str, filename: str, format: PromptFormat) -> PromptTemplate:
    return get_prompt(get_template(dir, filename), format)