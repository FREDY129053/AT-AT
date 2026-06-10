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
    # Add summary and replace desc for rationale
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