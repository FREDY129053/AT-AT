from pydantic import BaseModel
import json
from pathlib import Path

def write_resp_to_file(response: BaseModel, filename: str):
    dir = Path("./src/.temp/")

    with open(dir / filename, "w") as file:
        json.dump(response.model_dump_json(), file, indent=4)

    with open(dir / filename, "r") as file:
        data = file.read()

    with open(dir / filename, "w") as file:
        file.write(data[1:-1].replace('\\"', '"'))