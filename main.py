import asyncio
import threading

from proxy import *
from config import *

if __name__ == "__main__":
    config = Config()
    threading.Thread(target=config.checking).start()

    asyncio.run(MinecraftProxy(config).start())
