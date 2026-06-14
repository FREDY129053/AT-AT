import asyncio
import time
import uuid

from importlib.resources import files

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_mistralai.chat_models import ChatMistralAI
from langchain_huggingface.embeddings import HuggingFaceEndpointEmbeddings
from langgraph.store.memory import InMemoryStore

from .schemas import MemoryImportanceResult

pkg = files('ab_agent')

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
    original: str

    def __init__(self, content, original):
        super().__init__(content)
        self.original = original


class Reflection(MemoryItem):
    def __init__(self, content):
        super().__init__(content)


class Plan(MemoryItem):
    next_step: str

    def __init__(self, content, next_step):
        super().__init__(content)
        self.next_step = next_step


class Action(MemoryItem):
    raw_action: dict

    def __init__(self, content, raw_action):
        super().__init__(content)
        self.raw_action = raw_action


class Thought(MemoryItem):
    def __init__(self, content):
        super().__init__(content)


hf_embeddings = HuggingFaceEndpointEmbeddings(
    huggingfacehub_api_token="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",
    task="feature-extraction",
    model="mixedbread-ai/mxbai-embed-large-v1",
)


class Memory:
    memory_prompt = PromptTemplate.from_template((pkg / 'prompts' / "memory_importance.j2").read_text(), template_format="jinja2")
    json_parser = JsonOutputParser(pydantic_object=MemoryImportanceResult)

    def __init__(self, agent_id):
        self.store = InMemoryStore(index={"embed": hf_embeddings, "dims": 512})
        self.namespace = (agent_id, "memories")

        self.llm = ChatMistralAI(
            model_name="mistral-medium-2508",
            temperature=0,
            api_key="CuqdoMUEoJJc3EDnwldZLCi1zmP0qSE8" # type: ignore
        )

    async def add(self, item: MemoryItem) -> str:
        key = str(uuid.uuid4())
        ts = int(time.time())

        item.timestamp = ts

        # await self.store.aput(self.namespace, key, item.__dict__)

        for attempt in range(5):
            try:
                await self.store.aput(self.namespace, key, item.__dict__)
            except Exception:
                if attempt == 4:
                    raise
                await asyncio.sleep(2 ** attempt)
            
        return key


    async def update(self, key: str):
        stored = await self.store.aget(self.namespace, key)
        if stored is None:
            return None

        item = stored.value
        chat_prompt = ChatPromptTemplate.from_messages(
            [("system", self.memory_prompt.template), ("user", item["content"])]
        )

        res = await (chat_prompt | self.llm | self.json_parser).ainvoke({
            "format_instructions": self.json_parser.get_format_instructions(),
        })

        importance = float(getattr(res, "score", 0.0))
        item["importance"] = importance

        for attempt in range(5):
            try:
                await self.store.aput(self.namespace, key, item)
            except Exception:
                if attempt == 4:
                    raise
                await asyncio.sleep(2 ** attempt)

        return importance

    async def get(self, memory_id: str):
        item = await self.store.aget(self.namespace, memory_id)
        return item
    
    async def get_all_items(self):
        return await self.store.asearch(self.namespace)        

    async def _search(self, query: str, limit: int = 5) -> list:
        results = await self.store.asearch(self.namespace, query=query, limit=limit)
        return results

    async def retrieve(
        self, query: str, limit: int = 5, trigger_update: bool = False
    ) -> list:
        # TODO: better retrieve
        res = await self._search(query, limit)

        if trigger_update:
            keys = [h.key for h in res]
            await asyncio.gather(*(self.update(k) for k in keys))

        updated = await self._search(query, limit)

        return updated