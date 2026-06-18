from __future__ import annotations
import random
import string
import toml

class ProxyManager:
    def __init__(self, config_path: str = "config/crosspost/proxy.toml"):
        with open(config_path) as f:
            self.config = toml.load(f)
        self.proxies = self.config.get("proxies", [])

    def _generate_session(self) -> str:
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=6))

    def get_proxy(self) -> str | None:
        if not self.proxies:
            return None
            
        proxy_cfg = random.choice(self.proxies)
        
        if proxy_cfg["type"] == "smartproxy":
            session = self._generate_session()
            # Format: http://username-session-[id]:password@host:port
            return f"http://{proxy_cfg['user']}-session-{session}:{proxy_cfg['password']}@{proxy_cfg['endpoint']}"
        
        # Add support for other formats here if needed
        return None