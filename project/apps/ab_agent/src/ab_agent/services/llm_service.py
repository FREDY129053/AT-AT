import asyncio
from typing import TypeVar, Type

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)

async def structured_call(
    llm,
    prompt: ChatPromptTemplate,
    output_model: Type[T],
    variables: dict,
) -> T:
    parser = PydanticOutputParser(pydantic_object=output_model)
    chain = prompt | llm | parser

    res = await chain.ainvoke(
        {
            **variables,
            "format_instructions":
                parser.get_format_instructions(),
        }
    )
    await asyncio.sleep(5)
    return res