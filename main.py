import asyncio, socket
import json
import threading
import time

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

    def __str__(self):
        return json.dumps({
            'css': self.css.getpeername(),
            'sss': self.sss.getpeername() if self.sss else None,
        })

    async def on_packet(self, packet):
        packet, p_id = readVarInt(packet)

        if p_id == 0 and len(packet) > 2:
            pver, srv_addr, srv_port = decode_handshake(packet)

            target_addr = proxy_config.get(f"{srv_addr}:{srv_port}")
            # print(f'client [{self.css.getpeername()}] protocol[{pver}] target[{srv_addr}:{srv_port}]')
            # print(f'config target addr: {target_addr}')

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

class TCPServer:
    clients: list[ProxyClient]

    def __init__(self):
        self.clients = []

    async def _handle_client(self, client: socket.socket):
        loop = asyncio.get_event_loop()
        proxy = ProxyClient(loop, client)

        self.clients.append(proxy)
        while True:
            if proxy.is_proxied:
                try:
                    await asyncio.gather(
                        proxy.proxy_css_sss(),
                        proxy.proxy_sss_css()
                    )
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
        self.clients.remove(proxy)

        client.close()

    async def _run_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(listening)
        server.listen(100)
        server.setblocking(False)

        loop = asyncio.get_event_loop()

        while True:
            client, _ = await loop.sock_accept(server)
            loop.create_task(self._handle_client(client))

    def start_server(self):
        asyncio.run(self._run_server())



if __name__ == "__main__":
    tcp_server = TCPServer()
    threading.Thread(target=tcp_server.start_server).start()
    while True:
        print("Current clients:", [str(_) for _ in tcp_server.clients])
        time.sleep(5)