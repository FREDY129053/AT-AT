import time

from pydantic import BaseModel, ConfigDict, Field


class MemoryItem:
    def __init__(self, content, timestamp=int(time.time())):
        self.kind = self.__class__.__name__.lower()
        self.content = content
        self.timestamp = timestamp
        self.importance = 0.0

    def __json__(self):
        return {
            "kind": self.kind,
            "content": self.content,
            "timestamp": self.timestamp,
            "importance": self.importance,
        }


class Observation(MemoryItem):
    # original: str

    def __init__(self, content, original):
        super().__init__(content)
        self.original = original


class Reflection(MemoryItem):
    def __init__(self, content):
        super().__init__(content)


class Plan(MemoryItem):
    # next_step: str

    def __init__(self, content, next_step):
        super().__init__(content)
        self.next_step = next_step


class Action(MemoryItem):
    # raw_action: dict

    def __init__(self, content, raw_action):
        super().__init__(content)
        self.raw_action = raw_action


class Thought(MemoryItem):
    def __init__(self, content):
        super().__init__(content)


class MemoryImportanceResult(BaseModel):
    rationale: str = Field(description="Rationale for the score")
    score: int = Field(description="Score from 1 to 10", max_digits=2, min_length=1)

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "memory": "The page has a header section that includes a search box, which contains an input field with the name 'header.search_box.search_input' that is currently empty and has no placeholder text.",
                    "rationale": "This memory is extremely importance because I want to find a product and I will use the search box to find it",
                    "score": 9,
                },
                {
                    "memory": "I really need to find a jacket that’s comfortable but also looks professional for conferences. Maybe something in red to keep that energy up?",
                    "rationale": "This memory is not important, as it only repeats information that I already know, for example, my preferences.",
                    "score": 3,
                },
                {
                    "memory": "The final product showcased is '20 PCS Balls Cake Topper Mini Balloons Cake Topper', which has a 62% rating and is available for $9.49 with an 'Add to Cart' button.",
                    "rationale": "This memory is not important for the intent of finding a jacket, as it relates to an unrelated product that does not aid in achieving the persona's goal.",
                    "score": 1,
                },
            ]
        }
    )