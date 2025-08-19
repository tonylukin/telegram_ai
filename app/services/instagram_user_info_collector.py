import os
from datetime import datetime, timedelta

from fastapi.params import Depends
from playwright.async_api import async_playwright
from sqlalchemy.orm import Session

from app.config import IG_AI_USER_INFO_PROFILE_PROMPT_RU, IG_AI_USER_INFO_PROFILE_PROMPT_EN, \
    INSTAGRAM_USER_INFO_COLLECTOR_USERNAME, INSTAGRAM_USER_INFO_COLLECTOR_PASSWORD, ENV, APP_ROOT
from app.configs.logger import logger
from app.db.queries.ig_user import get_ig_user_by_username
from app.dependencies import get_db, get_ai_client
from app.services.ai.ai_client_base import AiClientBase
from app.models.ig_user import IgUser
from app.services.proxy.proxy_fetcher_decodo import ProxyFetcherDecodo
from playwright.async_api._generated import Page

SCROLL_COUNT = 10
POST_COUNT = 30    # number of posts to fetch
SESSION_DIR = os.path.join(APP_ROOT, "sessions")
SESSION_FILE = os.path.join(SESSION_DIR, "ig_session.json")

class InstagramUserInfoCollector:
    def __init__(
            self,
            ai_client: AiClientBase = Depends(get_ai_client),
            session: Session = Depends(get_db),
            proxy_fetcher: ProxyFetcherDecodo = Depends(),
    ):
        self.ai_client = ai_client
        self.session = session
        self.proxy_fetcher = proxy_fetcher

    async def get_user_info(self, username: str, prompt: str = None, lang: str = 'ru') -> dict:
        if username.startswith('@'):
            username = username[1:]

        user_found = get_ig_user_by_username(self.session, username)
        date_interval = datetime.now() - timedelta(weeks=12)
        if user_found and user_found.updated_at and user_found.updated_at > date_interval:
            logger.info(f"User {user_found.username} has fresh info")
            return user_found.description

        try:
            profile_data = await self.__get_instagram_profile_data(username)
        except ValueError as e:
            raise e
        except Exception as e:
            logger.error(e)
            raise e

        logger.info(f"Data from {username}: {profile_data}")
        translations = {
            'ru': {
                'profile_prompt': IG_AI_USER_INFO_PROFILE_PROMPT_RU,
            },
            'en': {
                'profile_prompt': IG_AI_USER_INFO_PROFILE_PROMPT_EN,
            },
        }
        overview = self.ai_client.generate_text(
            (prompt or translations.get(lang).get('profile_prompt')).format(
                followers=profile_data.get('followers'),
                following=profile_data.get('following'),
                posts=profile_data.get('posts'),
                bio=profile_data.get('bio', ''),
            )
        )
        full_desc = {
            'description': overview,
            'followers': len(profile_data.get('followers')),
            'following': len(profile_data.get('following')),
            'posts': len(profile_data.get('posts')),
            'bio': profile_data.get('bio'),
        }
        self.__save_to_db(user_found, username, full_desc)

        return full_desc

    async def __get_instagram_profile_data(self, username: str) -> dict | None:
        os.makedirs(SESSION_DIR, exist_ok=True)
        proxy_config = self.proxy_fetcher.get_random_proxy_config()
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                # headless=(ENV != 'dev'),
                headless=True,
                proxy=proxy_config,
            )

            if os.path.exists(SESSION_FILE):
                context = await browser.new_context(storage_state=SESSION_FILE, viewport={"width": 1280, "height": 800})
                await context.set_extra_http_headers({
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                })
                page = await context.new_page()
                await page.goto("https://www.instagram.com/")
                content = await page.content()
                ig_content_file = os.path.join(APP_ROOT, "data", "instagram_debug.html")
                with open(ig_content_file, "w", encoding="utf-8") as f:
                    f.write(content)

                if await page.query_selector('input[name="username"]'):
                    # Definitely not logged in
                    context = await self.__login_and_save_session(browser)
                else:
                    logger.info("✅ Logged in with saved session")
            else:
                context = await self.__login_and_save_session(browser)

            # Go to target profile
            page = await context.new_page()
            try:
                await page.goto(f"https://www.instagram.com/{username}/")
                await page.wait_for_selector("header")
            except Exception as e:
                logger.error(e)
                raise ValueError('User not found')

            # Bio
            try:
                bio = await page.locator("header section:eq(3) span > div > span").text_content() # todo bio does not work
            except:
                bio = ""

            # Followers
            await page.click('a[href$="/followers/"]')
            await page.wait_for_selector('div[role="dialog"]')
            followers_modal = await page.query_selector('div[role="dialog"]')
            await page.wait_for_timeout(1000)
            scrollable_div = await followers_modal.query_selector('div.html-div[style*="400px"] > div:last-child')

            followers = set()
            for _ in range(SCROLL_COUNT):
                items = await followers_modal.query_selector_all('a[role="link"]:not(:has(img))')
                for item in items:
                    try:
                        username_holder = await item.query_selector_all('span')
                        item_username = await username_holder[0].text_content()
                        if item_username:
                            followers.add(item_username)
                    except Exception as e:
                        logger.error(e)
                        continue

                await page.evaluate('(el) => el && (el.scrollTop += 1000)', scrollable_div)
                await page.wait_for_timeout(1000)

            await page.keyboard.press('Escape')

            # Following
            await page.click('a[href$="/following/"]')
            await page.wait_for_selector('div[role="dialog"]')
            following_modal = await page.query_selector('div[role="dialog"]')
            await page.wait_for_timeout(1000)
            scrollable_div = await following_modal.query_selector('div.html-div[style*="400px"] > div:last-child')

            following = set()
            for _ in range(SCROLL_COUNT):
                items = await following_modal.query_selector_all('a[role="link"]:not(:has(img))')
                for item in items:
                    try:
                        username_holder = await item.query_selector_all('span')
                        item_username = await username_holder[0].text_content()
                        if item_username:
                            following.add(item_username)
                    except Exception as e:
                        logger.error(e)
                        continue
                await page.evaluate('(div) => { div && div.scrollBy(0, 1000); }', scrollable_div) # scrollBy is the same
                await page.wait_for_timeout(1000)

            await page.keyboard.press('Escape')

            # Posts
            posts = []
            await page.wait_for_selector('main > div > :last-child')
            post_links = await page.eval_on_selector_all(
                'main > div > :last-child a',
                f'nodes => nodes.filter(n => n.href.includes("{username}/p") || n.href.includes("{username}/reel")).map(n => n.href).slice(0, {POST_COUNT})'
            )

            for link in post_links:
                await page.goto(link)

                strategy_selector_tuples = [
                    ('1', 'article'),
                    ('2', 'span[style*="--x-lineHeight: 18px"]'),
                ]
                current_method = None
                for method_number, selector in strategy_selector_tuples:
                    try:
                        await page.wait_for_selector(selector, timeout=10000)
                        current_method = '_parse_post_' + method_number
                        break
                    except:
                        continue

                if current_method is None:
                    raise RuntimeError(f"Strategy not found")

                logger.info(f"Strategy {current_method} found")
                caption = await getattr(self, current_method)(page)

                try:
                    place = await page.locator('a[href^="/explore/"]').first.text_content()
                except:
                    place = ""

                posts.append({
                    "url": link,
                    "text": caption.strip() if caption else "",
                    "place": place.strip() if place else ""
                })

            await browser.close()

            result = {
                "username": username,
                "bio": bio.strip() if bio else "",
                "followers": list(followers),
                "following": list(following),
                "posts": posts
            }
            return result

    async def _parse_post_1(self, page: Page):
        try:
            caption = await page.locator('article h1').first.text_content()
        except:
            caption = ""

        return caption

    async def _parse_post_2(self, page: Page):
        try:
            caption = await page.locator('hr + div span[style*="--x-lineHeight: 18px"] > div > span').first.text_content()
        except:
            caption = ""

        return caption

    async def __login_and_save_session(self, browser):
        """Logs into Instagram and saves session state"""
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_selector('input[name="username"]', timeout=15000)
        await page.fill('input[name="username"]', INSTAGRAM_USER_INFO_COLLECTOR_USERNAME)
        await page.fill('input[name="password"]', INSTAGRAM_USER_INFO_COLLECTOR_PASSWORD)
        await page.click('button[type="submit"]')

        await page.wait_for_timeout(7000)  # wait for login to complete

        await context.storage_state(path=SESSION_FILE)
        logger.info("💾 New session saved")

        return context

    def __save_to_db(self, user_found: IgUser | None, username: str, full_desc: dict[str, str]) -> None:
        try:
            if user_found is None:
                user_found = IgUser(username=username, description=full_desc)
                self.session.add(user_found)

            user_found.description = full_desc
            user_found.updated_at = datetime.now()
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.error(e)