import asyncio, socket

from utils import readVarInt, async_read_packet, decode_handshake

listening = ('0.0.0.0', 25565)
proxy_config: dict[str, tuple] = {
    'test.a.local:25565': ('85.196.228.115', 25565),
    'test.b.local:25565': ('146.158.101.170', 25565)
}

class ProxyClient:
    _loop: asyncio.AbstractEventLoop

    css: socket.socket
    sss: socket.socket

    buffer: bytearray
    is_proxied: bool

    def __init__(self, loop: asyncio.AbstractEventLoop, css):
        self._loop = loop
        self.is_proxied = False
        self.buffer = bytearray()
        self.css = css

    async def on_packet(self, packet):
        packet, p_id = readVarInt(packet)

        if p_id == 0 and len(packet) > 2:
            pver, srv_addr, srv_port = decode_handshake(packet)

            target_addr = proxy_config.get(f"{srv_addr}:{srv_port}")
            print(f'client [{self.css.getpeername()}] protocol[{pver}] target[{srv_addr}:{srv_port}]')
            print(f'config target addr: {target_addr}')

            await self._connect_target(target_addr)
            await self._loop.sock_sendall(self.sss, bytes(self.buffer))
            self.is_proxied = True
            return True

        return None

    async def _connect_target(self, target: tuple[str, int]):
        address, port = target
        self.sss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        await self._loop.sock_connect(self.sss, target)

    async def proxy_css_sss(self):
        while True:
            await self._loop.sock_sendall(self.sss, await self._loop.sock_recv(self.css, 16384))

    async def proxy_sss_css(self):
        while True:
            await self._loop.sock_sendall(self.css, await self._loop.sock_recv(self.sss, 16384))

async def handle_client(client: socket.socket):
    loop = asyncio.get_event_loop()
    proxy = ProxyClient(loop, client)
    while True:
        if proxy.is_proxied:
            c1 = proxy.proxy_css_sss()
            c2 = proxy.proxy_sss_css()
            try:
                await asyncio.gather(c1, c2)
            except Exception as e:
                print(f'asyncio.gather(c1, c2): {str(e)}')
                pass
            break

        try:
            raw, packet = await async_read_packet(loop, client)
            proxy.buffer += raw
            await proxy.on_packet(packet)
        except Exception as e:
            print(f'generic: {str(e)}')
            break

        print('\n')

    client.close()

async def run_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(listening)
    server.listen(100)
    server.setblocking(False)

    loop = asyncio.get_event_loop()

    while True:
        client, _ = await loop.sock_accept(server)
        loop.create_task(handle_client(client))

asyncio.run(run_server())

