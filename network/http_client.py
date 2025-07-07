from aiohttp import ClientSession, ClientTimeout
from typing import Optional

class HttpClient:
    """Zarządza współdzieloną sesją aiohttp."""
    _instance = None

    def __init__(self):
        self.session: Optional[ClientSession] = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = HttpClient()
        return cls._instance

    async def get_session(self) -> ClientSession:
        if self.session is None or self.session.closed:
            timeout = ClientTimeout(total=10)
            self.session = ClientSession(timeout=timeout)
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()