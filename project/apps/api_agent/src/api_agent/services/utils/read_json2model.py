import json
from pathlib import Path
from pydantic import BaseModel

def json2model[T: BaseModel](filename: str, model: type[T]) -> T:
    dir = Path("./src/.temp/")

    with open(dir / filename, 'r') as file:
        data = json.load(file)

    return model.model_validate(data)
