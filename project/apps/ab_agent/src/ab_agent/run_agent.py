import asyncio
import base64
import json
import random
from pathlib import Path

from . import logger, rabbit_temp
from .agent import Agent
from .environment import WebAgentEnv


class AgentPolicy:
    def __init__(self, persona, intent, output=None):
        self.agent = Agent(persona, intent)
        self.slow_loop_task = None

    async def slow_loop(self):
        while True:
            try:
                logger.info("REFLECTING...")
                await self.agent.reflect()
                await asyncio.sleep(5)

                logger.info("WONDERING...")
                await self.agent.wonder()
                await asyncio.sleep(5)

                logger.info("MEMORY UPDATE...")
                await self.agent.memory.update(self.agent.id)
                await asyncio.sleep(5)
            except Exception as e:
                logger.info(f"SLOW LOOP FAILED: {e}")

    async def forward(self, playwright_env):
        observation = await playwright_env.observation()
        observation_str = json.dumps(observation)
        available_actions = observation.get("clickable_elements")

        mem = await self.agent.memory.get_all_items()
        if len(mem) != 0:  # make parallel
            await asyncio.gather(
                self.agent.feedback(observation["html"]),
                self.agent.perceive(observation["html"]),
            )
        else:
            await self.agent.perceive(observation["html"])

        if self.slow_loop_task is None:
            self.slow_loop_task = asyncio.create_task(self.slow_loop())

        logger.info("PLANNING...")
        await self.agent.plan()
        await asyncio.sleep(5)

        logger.info("ACTING...")
        action = await self.agent.act(observation)
        await asyncio.sleep(5)

        return json.dumps(action)

    async def get_formatted_memories(self) -> str:
        """
        Return all memories of the agent as a single formatted string.

        Returns:
            str: Formatted memory trace.
        """
        mems = await self.agent.memory.get_all_items()
        if not mems:
            return ""
        return "\n".join(self.agent.format_memories(mems))

    async def close(self):
        if self.slow_loop_task is not None:
            self.slow_loop_task.cancel()
            self.slow_loop_task = None


async def run_agent(steps, *, trace: bool = False, headless: bool = True):
    env = WebAgentEnv()
    TRACE_DIR = Path("./temp/trace")
    SIMP_HTML_DIR = TRACE_DIR / "simp_html"
    RAW_HTML_DIR = TRACE_DIR / "raw_html"
    OBS_TRACE_DIR = TRACE_DIR / "observation_trace"
    SIMP_HTML_DIR.mkdir(parents=True, exist_ok=True)
    RAW_HTML_DIR.mkdir(parents=True, exist_ok=True)
    OBS_TRACE_DIR.mkdir(parents=True, exist_ok=True)

    persona = "Background:\nThey are non-binary, between the ages of 25 and 34. They have an associate degree and live in Portland, Oregon, with a partner and a small rescue dog. They work part-time as a freelance graphic designer and supplement their income with gig-economy delivery work. They enjoy thrifting, photography, and attending local music shows. They follow sustainable living practices, are politically engaged, and view technology skeptically but appreciate tools that support creativity and community connection.\n\nFinancial Situation:\nTheir income is variable and sometimes unpredictable, so they prioritize building an emergency fund and tracking monthly expenses. They budget carefully for essentials and allocate a modest portion of earnings to savings and creative projects. They are open to affordable credit options but avoid high-interest debt.\n\nShopping Habits:\nThey shop online a few times per week, frequently browsing marketplaces and independent maker sites. Average monthly online spend is around $120–$200, with purchases including vintage clothing, art supplies, tech accessories, and eco-friendly household goods. They value ethical brands, transparent sourcing, and products with minimal packaging. They read reviews but also rely on community recommendations from social platforms. They enjoy discovering new small brands and are comfortable returning items that don't meet expectations.\n\nProfessional Life:\nTheir freelance design work is flexible and project-based; they juggle client deadlines with personal creative work. They cultivate a portfolio online and use networking at local events to find clients. They are motivated to grow into a sustainable creative practice and are exploring part-time remote roles to increase income stability.\n\nPersonal Style:\nThey have an eclectic, gender-neutral aesthetic that mixes thrifted finds with modern basics. Their routine includes morning coffee and a short photo walk, work sessions split between a home studio and local co-working spaces, and evenings spent editing photos, making zines, or attending shows. They prioritize mental health with regular therapy and community meetups."
    intent = 'Go to the "Playwright Test Agents" page in the documentation'

    task_to_use = {
        "sites": ["docs"],
        "task_id": 1,
        "require_login": False,
        # "start_url": "https://www.google.com/search?q=%D1%87%D1%82%D0%BE",
        # "start_url": "https://playwright.dev/",
        "start_url": "https://playwright.dev/docs/intro",
        "intent": intent,
    }

    policy = AgentPolicy(persona, intent)
    await env.setup(task_to_use, headless)

    steps_taken = 0
    max_steps = steps

    obs = await env.observation()

    logger.info("Initial observation ready")
    action_trace = []
    while steps_taken < max_steps:
        if trace:
            with open(TRACE_DIR / "observation_trace.jsonl", "a") as f:
                json.dump(obs, f)

        if obs.get("tabs"):
            current_url = obs["tabs"][0].get("url")
            logger.info(f"Current url: {current_url}")

        if trace:
            with open(SIMP_HTML_DIR / f"simp_html_{steps_taken}.html", "w") as f:
                f.write(obs["html"])

            with open(RAW_HTML_DIR / f"raw_html_{steps_taken}.html", "w") as f:
                assert env.page is not None
                f.write(await env.page.content())
        
        action = await policy.forward(env)
        action_trace.append(action)

        # targets = [
        #     "docs",
        #     "system_mode",
        #     "search_k",
        #     "docs",
        #     "system_mode",
        #     "search_k",
        #     "docs",

        #     "getting_started",
        #     "installation",
        #     "writing_tests",
        #     "generating_tests",
        #     "running_and_debuggin",
        #     "trace_viewer",
        #     "setting_up_ci",
        #     "getting_started_vs_c",
        #     "release_notes",
        #     "canary_releases",
        #     "playwright_test",
        #     "agents",
        #     "annotations",
        #     "command_line",
        #     "configuration",
        #     "configuration_use",
        #     "emulation"
        # ]

        # target = random.choice(targets)

        # action = "{\"action\": \"click\", \"target\": \"" + target  + "\", \"description\": \"Clicking\" }"
        # action_trace.append(action)

        # if steps_taken == 0:
        #     photo = await env.screenshot()
        #     image_data = base64.b64decode(photo)
        #     with open("./page_photo.png", 'wb') as f:
        #         f.write(image_data)

        if trace:
            with open(TRACE_DIR / "action_trace.json", "w") as f:
                json.dump(action_trace, f, indent=2)

            with open(
                OBS_TRACE_DIR / f"observation_trace_{steps_taken}.txt",
                "w",
            ) as f:
                f.write(policy.agent.observation)

            with open(TRACE_DIR / "memory_trace.json", "w") as f:
                mems = await policy.agent.memory.get_all_items()
                json.dump(policy.agent.format_memories(mems), f)

        logger.info(f"Taking action {action}")
        logger.info(f"Action: {steps_taken + 1} out of {max_steps}")
        obs = await env.step(str(action))
        
        log = {}

        await asyncio.sleep(5)
        steps_taken += 1

        if obs.get("terminated"):
            action = json.loads(action)
            if action['action'] == 'terminate':
                log['trajectory_flag'] = action['type']
                log['trajectory_steps'] = steps_taken
                rabbit_temp(log)
            break
