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

SCROLL_COUNT = 10
POST_COUNT = 30    # number of posts to fetch
SESSION_DIR = os.path.join(APP_ROOT, "sessions")
SESSION_FILE = os.path.join(SESSION_DIR, "ig_session.json")

class InstagramUserInfoCollector:
    def __init__(
            self,
            ai_client: AiClientBase = Depends(get_ai_client),
            session: Session = Depends(get_db)
    ):
        self.ai_client = ai_client
        self.session = session

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
            'bio': profile_data.get('bio'),
        }
        self.__save_to_db(user_found, username, full_desc)

        return full_desc

    async def __get_instagram_profile_data(self, username: str) -> dict | None:
        os.makedirs(SESSION_DIR, exist_ok=True)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=(ENV != 'dev'))

            if os.path.exists(SESSION_FILE):
                context = await browser.new_context(storage_state=SESSION_FILE)
                page = await context.new_page()
                await page.goto("https://www.instagram.com/")
                try:
                    suggested_title = await page.query_selector('h4')
                    suggested_title = await suggested_title.text_content()
                    if suggested_title.strip().lower() != 'suggested for you':
                        raise Exception
                    logger.info("✅ Logged in with saved session")
                except:
                    logger.info("⚠️ Saved session invalid, logging in again...")
                    context = await self.__login_and_save_session(browser)
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
                bio = await page.locator("header section:eq(3) span > div > span").text_content()
            except:
                bio = ""

            # Followers
            await page.click('a[href$="/followers/"]')
            await page.wait_for_selector('div[role="dialog"]')
            followers_modal = await page.query_selector('div[role="dialog"]')
            await page.wait_for_timeout(1000)
            scrollable_div = await followers_modal.query_selector('div[style*="--maxHeight"] > div:last-child')

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

                await page.evaluate('(el) => el.scrollTop += 1000', scrollable_div)
                await page.wait_for_timeout(1000)

            await page.keyboard.press('Escape')

            # Following
            await page.click('a[href$="/following/"]')
            await page.wait_for_selector('div[role="dialog"]')
            following_modal = await page.query_selector('div[role="dialog"]')
            await page.wait_for_timeout(1000)
            scrollable_div = await following_modal.query_selector('div[style*="--maxHeight"] > div:last-child')

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
                await page.evaluate('(div) => { div.scrollBy(0, 1000); }', scrollable_div) # scrollBy is the same
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
                try:
                    await page.wait_for_selector('article', timeout=10000)
                except:
                    continue

                try:
                    caption = await page.locator('article h1').first.text_content()
                except:
                    caption = ""

                try:
                    place = await page.locator('header a[href^="/explore/"]').first.text_content()
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

    async def __login_and_save_session(self, browser):
        """Logs into Instagram and saves session state"""
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://www.instagram.com/accounts/login/")
        await page.wait_for_selector('input[name="username"]')
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