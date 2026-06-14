from ab_agent import logger
from ab_agent.environment import WebAgentEnv
from ab_agent.schemas import AgentState, AgentInput, GlobalState
from langchain_mistralai.chat_models import ChatMistralAI
from shared.rabbitmq import Context, create_event_bus
from ab_agent.services.memory_service import MemoryService

DEBUG = True

async def start_node(input_data: AgentInput) -> AgentState:
    input_data = raw_input.data
    start_link = input_data.get('interface_a')
    intent = input_data.get('intent', "")
    llm_data: dict = input_data.get('llm', {})
    llm = ChatMistralAI(
        model_name=llm_data.get('modelName', "mistral-medium-2508"),
        temperature=llm_data.get('temperature', 0),
        api_key=llm_data.get('apiKey', 'CuqdoMUEoJJc3EDnwldZLCi1zmP0qSE8'),  # type: ignore
    )

    task_to_use = {
        "require_login": False,
        "start_url": start_link,
        "intent": intent,
    }

    env = WebAgentEnv()
    logger.info("Env setup...")
    await env.setup(task_to_use, True)
    logger.info("Env loaded!")

    event_bus = create_event_bus()
    await event_bus.broker.start()

    state = AgentState(
        is_debug=DEBUG,
        agent_id='idk',
        persona = "Background:\nThey are non-binary, between the ages of 25 and 34. They have an associate degree and live in Portland, Oregon, with a partner and a small rescue dog. They work part-time as a freelance graphic designer and supplement their income with gig-economy delivery work. They enjoy thrifting, photography, and attending local music shows. They follow sustainable living practices, are politically engaged, and view technology skeptically but appreciate tools that support creativity and community connection.\n\nFinancial Situation:\nTheir income is variable and sometimes unpredictable, so they prioritize building an emergency fund and tracking monthly expenses. They budget carefully for essentials and allocate a modest portion of earnings to savings and creative projects. They are open to affordable credit options but avoid high-interest debt.\n\nShopping Habits:\nThey shop online a few times per week, frequently browsing marketplaces and independent maker sites. Average monthly online spend is around $120–$200, with purchases including vintage clothing, art supplies, tech accessories, and eco-friendly household goods. They value ethical brands, transparent sourcing, and products with minimal packaging. They read reviews but also rely on community recommendations from social platforms. They enjoy discovering new small brands and are comfortable returning items that don't meet expectations.\n\nProfessional Life:\nTheir freelance design work is flexible and project-based; they juggle client deadlines with personal creative work. They cultivate a portfolio online and use networking at local events to find clients. They are motivated to grow into a sustainable creative practice and are exploring part-time remote roles to increase income stability.\n\nPersonal Style:\nThey have an eclectic, gender-neutral aesthetic that mixes thrifted finds with modern basics. Their routine includes morning coffee and a short photo walk, work sessions split between a home studio and local co-working spaces, and evenings spent editing photos, making zines, or attending shows. They prioritize mental health with regular therapy and community meetups.",
        intent = intent,
        environment=env,
        llm=llm,
        memory=MemoryService('idk'),
        max_steps=2,
    )

    return state