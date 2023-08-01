import asyncio, socket
import dataclasses
import json
import threading
import time

from utils import readVarInt, async_read_packet, decode_handshake


# class Config:
#     buf_len: int = 256000
#     rcv_len: int = 256000
#     proxy_config: dict[str, tuple] = {
#         'test.a.local:25565': ('136.243.216.186', 25565),
#     }
#     listening: tuple = ('0.0.0.0', 25565)
#
#     def __init__(self, data: dict):
#
#



BUFLEN = 256000
RCVLEN = 256000
listening = ('0.0.0.0', 25565)
proxy_config: dict[str, tuple] = {
    'test.a.local:25565': ('136.243.216.186', 25565),
    'test.b.local:25565': ('146.158.101.170', 25565),
    '192.168.10.1:25565': ('136.243.216.186', 25565),
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
        try:
            css_name = self.css.getpeername()
        except:
            css_name = None

        try:
            sss_name = self.sss.getpeername()
        except:
            sss_name = None

        return json.dumps({
            'css': css_name,
            'sss': sss_name,
        })

    async def on_packet(self, packet):
        packet, p_id = readVarInt(packet)

        if p_id == 0 and len(packet) > 2:
            pver, srv_addr, srv_port = decode_handshake(packet)

            target_addr = proxy_config.get(f"{srv_addr}:{srv_port}")
            # print(f'client [{self.css.getpeername()}] protocol[{pver}] target[{srv_addr}:{srv_port}]')
            # print(f'config target addr: {target_addr}')

            await self._connect_target(target_addr)
            self.sss.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFLEN)
            self.sss.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, BUFLEN)
            await self._loop.sock_sendall(self.sss, bytes(self.buffer))
            self.is_proxied = True
            return True

        return None

    async def _connect_target(self, target: tuple[str, int]):
        address, port = target
        self.sss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        await self._loop.sock_connect(self.sss, target)

    async def proxy_css_sss(self):
        try:
            while True:
                res = (await self._loop.sock_recv(self.css, RCVLEN))
                print(f'aaaa L{len(res)} {type(res)}')
                if not res: return
                await self._loop.sock_sendall(self.sss, res)
        except:
            return

    async def proxy_sss_css(self):
        try:
            while True:
                res = (await self._loop.sock_recv(self.sss, RCVLEN))
                print(f'bbbb L{len(res)}')
                if not res: return
                await self._loop.sock_sendall(self.css, res)

        except:
            return

class TCPServer:
    clients: list[ProxyClient]

    def __init__(self):
        self.clients = []

    async def _handle_client(self, client: socket.socket):
        loop = asyncio.get_event_loop()
        proxy = ProxyClient(loop, client)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFLEN)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, BUFLEN)

        self.clients.append(proxy)
        while True:
            if proxy.is_proxied:
                try:
                    await asyncio.gather(
                        proxy.proxy_css_sss(),
                        proxy.proxy_sss_css()
                    )
                except Exception as e:
                    print(f'exc: asyncio.gather(c1, c2): {str(e)}')
                    pass
                break

            try:
                raw, packet = await async_read_packet(loop, client)
                proxy.buffer += raw
                await proxy.on_packet(packet)
            except Exception as e:
                raise e
                print(f'exc: generic: {str(e)}')
                break

        self.clients.remove(proxy)
        client.close()


    async def _run_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFLEN)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, BUFLEN)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(listening)
        server.listen(100)
        server.setblocking(False)

        loop = asyncio.get_event_loop()

        while True:
            client, _ = await loop.sock_accept(server)
            print(_)
            loop.create_task(self._handle_client(client))

    def start_server(self):
        asyncio.run(self._run_server())



if __name__ == "__main__":
    tcp_server = TCPServer()
    threading.Thread(target=tcp_server.start_server).start()

    while True:
        print("Current clients:", [str(_) for _ in tcp_server.clients])
        time.sleep(5)