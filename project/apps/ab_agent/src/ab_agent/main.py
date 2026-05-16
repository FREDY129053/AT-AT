import asyncio

from . import logger

from .run_agent import run_agent

async def amain():
    logger.info("AB TESTER START")
    await run_agent(7, trace=True, headless=True)

def main():
    asyncio.run(amain())