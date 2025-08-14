import requests
import random

from app.config import PROXY_DECODO_PASSWORD, PROXY_DECODO_USERNAME, ENV
from app.configs.logger import logger

# todo use interface for different implementations
class ProxyFetcherDecodo:

    def get_random_proxy_config(self) -> dict | None:
        if ENV != 'prod':
            return None

        port = random.choice(range(10001, 10008))
        return {
            "server": f"gate.decodo.com:{port}",
            "username": PROXY_DECODO_USERNAME,
            "password": PROXY_DECODO_PASSWORD
        }

    def __get_random_proxy(self, protocol="http", timeout=5000, country="all", anonymity="all", limit=100) -> str:
        """
        Fetches a random proxy from ProxyScrape API.

        protocol: 'http', 'socks4', 'socks5'
        timeout: max latency in ms
        country: 'all' or country code (e.g., 'US', 'DE')
        anonymity: 'all', 'elite', 'anonymous', 'transparent'
        """
        url = (
            "https://api.proxyscrape.com/v4/free-proxy-list/get"
            f"?request=displayproxies&protocol={protocol}"
            f"&timeout={timeout}&country={country}&anonymity={anonymity}&limit={limit}"
        )

        try:
            resp = requests.get(url)
            resp.raise_for_status()
            proxies = resp.text.strip().split("\n")
            proxies = [p for p in proxies if p.strip()]  # remove empty lines

            if not proxies:
                raise ValueError("No proxies found with the given filters.")

            return random.choice(proxies).strip()  # format: IP:PORT

        except requests.RequestException as e:
            logger.error(f"Error fetching proxies: {e}")
            return None
