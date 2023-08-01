import asyncio, socket
import dataclasses
import json
import threading
import time

from utils import readVarInt, read_packet, decode_handshake


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

    css: socket.socket
    sss: socket.socket

    buffer: bytearray
    is_proxied: bool

    def __init__(self, css):
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

    def on_packet(self, packet):
        packet, p_id = readVarInt(packet)

        if p_id == 0 and len(packet) > 2:
            pver, srv_addr, srv_port = decode_handshake(packet)

            target_addr = proxy_config.get(f"{srv_addr}:{srv_port}")
            # print(f'client [{self.css.getpeername()}] protocol[{pver}] target[{srv_addr}:{srv_port}]')
            # print(f'config target addr: {target_addr}')

            self._connect_target(target_addr)
            self.sss.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFLEN)
            self.sss.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, BUFLEN)
            self.sss.sendall(bytes(self.buffer))
            self.is_proxied = True
            return True

        return None

    def _connect_target(self, target: tuple[str, int]):
        self.sss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sss.connect(target)

    def proxy_css_sss(self):
        while True:
            res = self.css.recv(RCVLEN)
            print(f'aaaa L{len(res)} {type(res)}')
            if not res: return
            self.sss.sendall(res)

    def proxy_sss_css(self):
        while True:
            res = self.sss.recv(RCVLEN)
            print(f'bbbb L{len(res)}')
            if not res: return
            self.css.sendall(res)

class TCPServer:
    clients: list[ProxyClient]

    def __init__(self):
        self.clients = []

    def _handle_client(self, client: socket.socket):
        proxy = ProxyClient(client)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFLEN)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, BUFLEN)

        self.clients.append(proxy)
        while True:
            if proxy.is_proxied:
                t1 = threading.Thread(target=proxy.proxy_sss_css)
                t2 = threading.Thread(target=proxy.proxy_css_sss)
                t1.start()
                t2.start()
                t1.join()
                t2.join()
                break

            try:
                raw, packet = read_packet(client)
                proxy.buffer += raw
                proxy.on_packet(packet)
            except Exception as e:
                print(f'exc: generic: {str(e)}')
                break

        self.clients.remove(proxy)
        client.close()


    def _run_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFLEN)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, BUFLEN)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(listening)
        server.listen(100)
        server.setblocking(True)

        while True:
            try:
                server.listen(5)
                conn, addr = server.accept()
            except Exception as _:
                break
            print('new client', addr)

            threading.Thread(target=self._handle_client, args=(conn,)).start()

    def start_server(self):
        self._run_server()



if __name__ == "__main__":
    tcp_server = TCPServer()
    threading.Thread(target=tcp_server.start_server).start()

    while True:
        print("Current clients:", [str(_) for _ in tcp_server.clients])
        time.sleep(5)