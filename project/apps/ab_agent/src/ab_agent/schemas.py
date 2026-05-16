from pydantic import BaseModel, ConfigDict, Field


class PerceiveResult(BaseModel):
    observations: list[str] = Field(
        description="A single, fully detailed paragraph describing everything on the current page as list",
        examples=[
            [
                "<a single, fully detailed paragraph describing everything on the current page>"
            ],
        ],
        default_factory=list,
    )


class PlanningResult(BaseModel):
    rationale: str = Field(description="String representation of the plan")
    plan: str = Field(description="String representation of the plan")
    next_step: str = Field(description="String representation of the next step")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "summary": 'Initial plan (at timestep 0) for intent ("Buy a jacket")',
                    "rationale": "I need to start by searching for jackets to find options that match my preferences.",
                    "plan": "1. (next) Search for jackets in the search bar\n2. Browse the search results and filter if needed\n3. View product details for jackets that look promising\n4. Select a jacket that meets my preferences and budget\n5. Add the selected jacket to cart\n6. Proceed to checkout\n7. Complete the purchase",
                    "next_step": "Search for jackets in the search bar",
                },
                {
                    "summary": "After searching for jackets, the plan is updated based on available search results",
                    "rationale": "I can see several jacket options in the search results. I need to view the details of promising products to make a decision.",
                    "plan": "1. (next) View product details for 'Women's Winter Puffer Jacket - Black'\n2. Check if this jacket meets my size and style preferences\n3. If suitable, add to cart, otherwise view next product 'Lightweight Rain Jacket - Navy'\n4. Continue viewing products until I find one that matches my needs\n5. Add the selected jacket to cart\n6. Proceed to checkout\n7. Complete the purchase",
                    "next_step": "View product details for 'Women's Winter Puffer Jacket - Black'",
                },
            ]
        }
    )


class GenerateActionResult(BaseModel):
    actions: list[dict] = Field(description="One valid action as list")


class ReflectResult(BaseModel):
    insights: list[str] = Field(description="List of all insights")


class WonderResult(BaseModel):
    thoughts: list[str] = Field(description="List of all thoughts")


class ActionFeedbackResult(BaseModel):
    thoughts: list[str] = Field(
        description="An evaluation of whether the action was successful or any feedback or observations that may inform the next action."
    )


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
