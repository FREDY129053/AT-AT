import asyncio
import base64
import contextlib
import random
import uuid
from pathlib import Path

from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

from . import logger


class WebAgentEnv:
    _shared_playwright: Playwright | None = None
    _shared_playwright_users: int = 0

    def __init__(self) -> None:
        self.browser = None
        self.context: BrowserContext | None = None
        self.context_manager: Playwright | None = None
        # note: pages are managed by self.context.pages
        self.page: Page | None = None  # current active page
        self.uuid = str(uuid.uuid4())  # TODO: external generator??
        self.task_config: dict | None = None  # TODO: config model??
        self.model_answer: str | None = None  # Model's final answer/response
        self.trace_file_path: str | None = None  # Path to the current trace file

    @classmethod
    async def _ensure_playwright(cls) -> Playwright:
        """Start Playwright"""
        if cls._shared_playwright is None:
            cls._shared_playwright = await async_playwright().start()
        cls._shared_playwright_users += 1

        return cls._shared_playwright

    @classmethod
    async def _cleanup_playwright(cls) -> None:
        cls._shared_playwright_users -= 1
        if 0 == cls._shared_playwright_users and cls._shared_playwright is not None:
            await cls._shared_playwright.stop()
            cls._shared_playwright = None

    async def _get_tabs_info(self) -> list[dict]:
        """Information about all opened tabs"""
        assert self.context is not None

        tabs_info = []
        for i, page in enumerate(self.context.pages):
            tabs_info.append(
                {
                    "id": i,
                    "title": await page.title(),
                    "url": page.url,
                    "is_active": page == self.page,
                }
            )

        return tabs_info

    async def setup(
        self, task_config: dict | None = None, headless: bool = True
    ) -> dict:
        """Init browser environment"""
        self.task_config = task_config
        self.context_manager = await self._ensure_playwright()
        self.browser = await self.context_manager.chromium.launch(headless=headless)
        self.context = await self.browser.new_context()

        # DEBUG: Disable timeout for tests
        self.context.set_default_timeout(0)
        self.context.set_default_navigation_timeout(0)

        # Init js scripts
        init_script_path = Path("./src/ab_agent/js/initscript.js")
        if init_script_path.exists():
            await self.context.add_init_script(init_script_path.read_text())
        else:
            logger.error("Init script not found!")

        # Get current page
        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()

        if self.task_config and "start_url" in self.task_config:
            await self.page.goto(
                self.task_config["start_url"],
                wait_until="domcontentloaded",
            )
        else:
            logger.warning("No start page")

        return await self.observation()

    # TODO: BaseModel??
    async def observation(self) -> dict:
        """Get parsed page content using the parser script"""
        assert self.page is not None

        parser_script = Path("./src/ab_agent/js/parser.js")
        content = {}

        try:
            await self.page.wait_for_load_state("domcontentloaded")

            # Use both original networkidle (for page loads) and custom detection (for XHR/fetch)
            try:
                # First wait for Playwright's networkidle (handles initial page loads well)
                await self.page.wait_for_load_state("networkidle")
            except Exception as e:
                logger.error(e)

            # Then wait for custom network idle detection (handles XHR/fetch after interactions)
            await self.__wait_for_custom_networkidle(timeout_ms=20_000)
        except Exception as e:
            logger.error(e)

        if parser_script.exists():
            parser_code = parser_script.read_text()
            try:
                content: dict = await self.page.evaluate(parser_code)
            except Exception as e:
                logger.warning(e)
                content: dict = {"html": await self.page.content()}
        else:
            logger.error("Parser script not found")
            content: dict = {"html": await self.page.content()}

        content["tabs"] = await self._get_tabs_info()
        content["model_answer"] = self.model_answer

        # TODO: придумать использование или убрать
        if self.task_config and "eval" in self.task_config:
            score = await self.evaluate_task()  # type: ignore
            content["score"] = score

            content["terminated"] = self.model_answer is not None or score != 0.0
        else:
            content["score"] = 0.0
            content["terminated"] = self.model_answer is not None

        return content

    async def __wait_for_custom_networkidle(
        self, timeout_ms: int = 10_000, idle_time_ms: int = 500
    ) -> None:
        assert self.page is not None

        start_time = asyncio.get_event_loop().time()
        timeout_seconds = timeout_ms / 1_000

        while True:
            try:
                # Check if our network tracker is available and if network is idle
                is_idle = await self.page.evaluate(
                    """
                    (idleTimeMs) => {
                        if (typeof window.__networkActivity === 'undefined') {
                            return true; // Fallback if tracker not available
                        }
                        return window.__networkActivity.isIdle(idleTimeMs);
                    }
                    """,
                    idle_time_ms,
                )

                if is_idle:
                    logger.info("CUSTOM NETWORK IDLE DETECTED")
                    break

                if (asyncio.get_event_loop().time() - start_time) >= timeout_seconds:
                    logger.warning("TAKE LONGER THAN TIMEOUT")
                    break

                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(e)
                break

    async def close(self):
        """Clean up pages/contexts/browsers deterministically, then shrink PW refcount."""

        # Close per-env resources (these are always safe to close)
        with contextlib.suppress(Exception):
            if self.page:
                await self.page.close()
        with contextlib.suppress(Exception):
            if self.context:
                await self.context.close()

        # Close this env's browser (you launch a new browser per env in setup)
        with contextlib.suppress(Exception):
            if self.browser:
                await self.browser.close()

        self.page = None
        self.context = None
        self.browser = None

        # Decrement the shared Playwright user count; stop PW only when last user is gone
        #    (stopping PW early would nuke other running envs)
        with contextlib.suppress(Exception):
            if self.context_manager:
                await self._cleanup_playwright()
                self.context_manager = None

    #############################
    ########   ACTIONS   ########
    #############################
    async def new_tab(self, url: str | None = None) -> int:
        """Create a new tab and optionally navigate to URL. Returns tab ID."""
        assert self.context is not None
        page = await self.context.new_page()
        if url:
            await page.goto(url, wait_until="domcontentloaded")

        self.page = page  # Make new tab active
        return len(self.context.pages) - 1

    async def switch_tab(self, tab_id: int) -> None:
        """Switch to a different tab by ID"""
        assert self.context is not None

        if 0 <= tab_id < len(self.context.pages):
            self.page = self.context.pages[tab_id]
            await self.page.bring_to_front()
        else:
            raise ValueError(f"Invalid tab ID: {tab_id}")

    async def close_tab(self, tab_id: int) -> None:
        """Close a tab by ID"""
        assert self.context is not None

        if 0 <= tab_id < len(self.context.pages):
            page = self.context.pages[tab_id]
            await page.close()
            # If we closed the active tab, switch to the currently activated tab from context
            if page == self.page and self.context.pages:
                # Find the currently active/focused tab in the context
                for p in self.context.pages:
                    try:
                        if await p.evaluate("document.hasFocus()"):
                            self.page = p
                            break
                    except Exception:
                        continue
                else:
                    # Fallback to last tab if no focused tab found
                    self.page = self.context.pages[-1]
                # Ensure the new active page is brought to front
                await self.page.bring_to_front()
        else:
            raise ValueError(f"Invalid tab ID: {tab_id}")

    async def screenshot(self, full_page: bool = False) -> str:
        """
        Capture screenshot of the current tab and return the base64 encoded image.
        """
        assert self.page is not None

        screenshot_bytes = await self.page.screenshot(full_page=full_page)
        return base64.b64encode(screenshot_bytes).decode("utf-8")

    async def reset(self):
        """Reset the environment to initial state"""
        assert self.context is not None

        # Close all tabs
        for page in self.context.pages:
            await page.close()
        self.page = await self.context.new_page()

        # Return to start URL from task config
        if self.task_config and "start_url" in self.task_config:
            await self.page.goto(
                self.task_config["start_url"], wait_until="domcontentloaded"
            )
        else:
            logger.debug("No start_url specified in task config")
        return await self.observation()

    async def step(self, action: str):
        """
        Execute an action in the environment using JSON string format and return the next observation.

        Args:
            action: JSON string describing the action to execute

        Returns:
            dict: The observation after executing the action (same format as observation() method)

        Examples:
            obs = await env.step('{"action": "click", "target": "login_button"}')
            obs = await env.step('{"action": "type", "target": "username", "text": "john_doe", "enter": true}')
            obs = await env.step('{"action": "select", "target": "country", "value": "US"}')
            obs = await env.step('{"action": "goto_url", "url": "https://example.com"}')
            obs = await env.step('{"action": "back"}')
            obs = await env.step('{"action": "new_tab", "url": "https://example.com"}')
            obs = await env.step('{"action": "switch_tab", "tab_id": 1}')
            obs = await env.step('{"action": "close_tab", "tab_id": 1}')
            obs = await env.step('{"action": "terminate", "answer": "The product costs $29.99"}')
        """
        import json

        try:
            action_data = json.loads(action)
            action_name = action_data.get("action")

            if action_name == "click":
                await self.click(action_data["target"])

            elif action_name == "mouse_click":
                await self.mouse_click(action_data["at_x"], action_data["at_y"])

            elif action_name == "type":
                text = action_data["text"]
                target = action_data["target"]
                press_enter = action_data.get("enter", False)
                await self.type(target, text, press_enter)

            elif action_name == "raw_type":
                await self.raw_type(action_data["text"])

            elif action_name == "scroll":
                await self.scroll(action_data["direction"], action_data["amount"])

            elif action_name == "hover":
                await self.hover(action_data["target"])

            elif action_name == "select":
                await self.select(action_data["target"], action_data["value"])

            elif action_name == "clear":
                await self.clear(action_data["target"])

            elif action_name == "key_press":
                key = action_data["key"]
                target = action_data.get("target")
                await self.key_press(key, target)

            elif action_name == "goto_url":
                await self.goto_url(action_data["url"])

            elif action_name == "back":
                await self.back()

            elif action_name == "forward":
                await self.forward()

            elif action_name == "refresh":
                await self.refresh()

            elif action_name == "new_tab":
                url = action_data.get("url")
                await self.new_tab(url)

            elif action_name == "switch_tab":
                tab_id = action_data["tab_id"]
                await self.switch_tab(tab_id)

            elif action_name == "close_tab":
                tab_id = action_data["tab_id"]
                await self.close_tab(tab_id)

            elif action_name == "terminate":
                answer = action_data.get("description", "")
                await self.terminate(answer)

            else:
                logger.debug(f"Unknown action: {action_name}")
                raise ValueError(f"Unknown action: {action_name}")

            # Sleep after action if configured
            # if self.config.browser.sleep_after_action > 0:
            # await asyncio.sleep(10)

            # Return the next observation after executing the action
            observation = await self.observation()
            observation["error"] = None
            return observation
        except json.JSONDecodeError as e:
            logger.debug(f"Invalid JSON action format: {action}")
            observation = await self.observation()
            observation["error"] = f"Invalid JSON action format: {e}"
            return observation
        except KeyError as e:
            logger.debug(f"Missing required parameter in action: {e}")
            observation = await self.observation()
            observation["error"] = f"Missing required parameter in action: {e}"
            return observation
        except Exception as e:
            logger.debug(f"Error executing action: {action}, error: {e}")
            observation = await self.observation()
            observation["error"] = f"Error executing action: {e}"
            return observation

    #############################
    ########   METHODS   ########
    #############################
    async def click(self, semantic_id: str) -> None:
        """
        Click on an element identified by its semantic ID.

        Args:
            semantic_id: The parser-semantic-id of the element to click

        Example:
            await env.click("login_button")
            await env.click("menu.settings")
        """
        assert self.page is not None

        selector = f'[parser-semantic-id="{semantic_id}"]'
        element = self.page.locator(selector)

        # TODO: сделать смещение внутри прямоугольника, чтобы была человечность
        bbox = await element.bounding_box(timeout=0)
        assert bbox is not None

        x1, y1 = bbox["x"], bbox["y"]
        x4, y4 = bbox["x"] + bbox["width"], bbox["y"] + bbox["height"]

        min_x, max_x = min(x1, x4), max(x1, x4)
        min_y, max_y = min(y1, y4), max(y1, y4)

        random_x = random.uniform(min_x, max_x)
        random_y = random.uniform(min_y, max_y)

        with open("./clicks_coords.txt", "a", encoding="utf-8") as f:
            f.write(f"{random_x} {random_y}\n")

        await element.click()
        logger.debug(f"Clicked element: {semantic_id}")

    async def mouse_move(self, x: int, y: int) -> None:
        """
        Move the cursor/mouse to a target coordinate.

        Args:
            x: The x-coordinate to move the cursor/mouse
            y: The y-coordinate to move the cursor/mouse

        Example:
            await env.mouse_move(200, 100)
        """
        assert self.page is not None

        await self.page.mouse.move(x, y)

        logger.debug(f"Moved mouse to [{x}, {y}]")

    async def mouse_click(self, at_x: int, at_y: int) -> None:
        """
        Perform a mouse click on the given coordinates. Defaults to the
        current mouse position if coordinates not given.

        Example:
            await env.mouse_click()
            await env.mouse_click(200, 100)
        """
        assert self.page is not None

        await self.page.mouse.click(x=at_x, y=at_y)

        logger.debug(f"Performed a raw click at [{at_x}, {at_y}]")

    async def type(
        self, semantic_id: str, text: str, press_enter: bool = False
    ) -> None:
        """
        Type text into an input element.

        Args:
            semantic_id: The parser-semantic-id of the input element
            text: Text to type
            press_enter: Whether to press Enter after typing

        Example:
            await env.type("search_input", "hello world")
            await env.type("username", "john_doe", press_enter=True)
        """
        assert self.page is not None

        selector = f'[parser-semantic-id="{semantic_id}"]'
        element = self.page.locator(selector)

        # Short timeout scroll - fail fast on hallucinated elements
        await element.scroll_into_view_if_needed(timeout=500)
        await element.fill(text, force=True)  # Clear and type

        if press_enter:
            await element.press("Enter")

        logger.debug(f"Typed '{text}' into element: {semantic_id}")

    async def raw_type(self, text: str):
        """
        Types the given string into the page as raw keyboard input.
        Will do nothing if an input element is not selected

        Args:
            text: Text to type

        Example:
            await env.raw_type("Best star wars movies")
        """
        assert self.page is not None

        await self.page.keyboard.type(text, delay=50)

        logger.debug(f"Typed '{text}' into the page as raw keyboard input")

    async def scroll(self, direction: str, amount: int) -> None:
        """
        Performs a mouse scroll at the page inside the viewport.

        Args:
            direction: "up", "down", "left", or "right". The direction to scroll by.
            amount: The amount of times to perform the scroll in that direction.
        """
        assert self.page is not None

        if direction not in ["up", "down", "left", "right"]:
            raise ValueError(f"Invalid direction: {direction}")

        scroll_button = {
            "up": "ArrowUp",
            "down": "ArrowDown",
            "left": "ArrowLeft",
            "right": "ArrowRight",
        }[direction]

        for _ in range(amount * 3):  # one mouse scroll event ~= 3 arrow keys
            await self.page.keyboard.press(scroll_button, delay=50)

        logger.debug(f"Scrolled the page {direction} by {amount} times")

    async def hover(self, semantic_id: str) -> None:
        """
        Hover over an element to trigger tooltips or dropdown menus.

        Args:
            semantic_id: The parser-semantic-id of the element to hover over

        Example:
            await env.hover("menu_item")
            await env.hover("tooltip_trigger")
        """
        assert self.page is not None

        selector = f'[parser-semantic-id="{semantic_id}"]'
        element = self.page.locator(selector)

        # Short timeout scroll - fail fast on hallucinated elements
        await element.scroll_into_view_if_needed(timeout=500)
        await element.hover(force=True)
        logger.debug(f"Hovered over element: {semantic_id}")

    async def select(self, semantic_id: str, value: str) -> None:
        """
        Select an option from a dropdown/select element.

        Args:
            semantic_id: The parser-semantic-id of the select element
            value: The value of the option to select

        Example:
            await env.select("country_dropdown", "USA")
            await env.select("language_select", "en")
        """
        assert self.page is not None

        selector = f'[parser-semantic-id="{semantic_id}"]'
        element = self.page.locator(selector)

        # Short timeout scroll - fail fast on hallucinated elements
        await element.scroll_into_view_if_needed(timeout=500)
        await element.select_option(value, force=True)
        logger.debug(f"Selected '{value}' in element: {semantic_id}")

    async def clear(self, semantic_id: str) -> None:
        """
        Clear the content of an input element.

        Args:
            semantic_id: The parser-semantic-id of the input element to clear

        Example:
            await env.clear("search_input")
            await env.clear("comment_textarea")
        """
        assert self.page is not None

        selector = f'[parser-semantic-id="{semantic_id}"]'
        element = self.page.locator(selector)

        # Short timeout scroll - fail fast on hallucinated elements
        await element.scroll_into_view_if_needed(timeout=500)
        await element.clear(force=True)
        logger.debug(f"Cleared element: {semantic_id}")

    async def key_press(self, key: str, semantic_id: str | None = None) -> None:
        """
        Press a keyboard key, optionally on a specific element.

        Args:
            key: Key to press (e.g., "Enter", "Escape", "Tab", "ArrowDown")
            semantic_id: Optional element to focus before pressing key

        Example:
            await env.key_press("Escape")  # Press Escape globally
            await env.key_press("Enter", "search_input")  # Press Enter on search input
            await env.key_press("ArrowDown", "dropdown")  # Navigate dropdown
        """
        assert self.page is not None

        if semantic_id:
            selector = f'[parser-semantic-id="{semantic_id}"]'
            element = self.page.locator(selector)
            # Short timeout scroll - fail fast on hallucinated elements
            await element.scroll_into_view_if_needed(timeout=500)
            await element.press(key)
            logger.debug(f"Pressed '{key}' on element: {semantic_id}")
        else:
            await self.page.keyboard.press(key)
            logger.debug(f"Pressed '{key}' globally")

    #############################
    ######   NAVIGATION    ######
    #############################
    async def goto_url(self, url: str) -> None:
        """
        Navigate to a specific URL in the current tab.

        Args:
            url: URL to navigate to

        Example:
            await env.goto_url("https://google.com")
            await env.goto_url("http://localhost:3000/login")
        """
        assert self.page is not None

        await self.page.goto(url, wait_until="domcontentloaded")
        logger.debug(f"Navigated to: {url}")

    async def back(self) -> None:
        """
        Navigate back in browser history.

        Example:
            await env.back()
        """
        assert self.page is not None

        await self.page.go_back(wait_until="domcontentloaded")
        logger.debug("Navigated back")

    async def forward(self) -> None:
        """
        Navigate forward in browser history.

        Example:
            await env.forward()
        """
        assert self.page is not None

        await self.page.go_forward(wait_until="domcontentloaded")
        logger.debug("Navigated forward")

    async def refresh(self) -> None:
        """
        Refresh/reload the current page.

        Example:
            await env.refresh()
        """
        assert self.page is not None

        await self.page.reload(wait_until="domcontentloaded")
        logger.debug("Page refreshed")

    async def terminate(self, answer: str = "") -> None:
        """
        Terminate the task with an optional answer.

        Args:
            answer: The model's final answer/response for the task

        Example:
            await env.terminate("The product costs $29.99")
            await env.terminate()  # Terminate without answer
        """
        self.model_answer = answer
        if answer:
            logger.debug(f"Task terminated with answer: {answer}")
        else:
            logger.debug("Task terminated without answer")
