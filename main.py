import asyncio
import json

from protocol import *

class Config:
    proxy_host: str
    proxy_port: int
    domains: dict[str, dict[str, str | int]]

    def __init__(self, config_file):
        with open(config_file, "r", encoding='utf-8') as f:
            self.__dict__ = json.load(f)

class ClientProxy:
    config: Config

    def __init__(self, config):
        self.config = config

    def check_domain(self, client_connect_to: tuple[str, int], client: tuple[str, int]) -> tuple[str, int] | None:
        client_connect_to_addr, client_connect_to_port = client_connect_to

        target = self.config.domains.get(client_connect_to_addr)

        return target['target_host'], target['target_port']

    async def handle_client(self, client_reader: StreamReader, client_writer: StreamWriter):
        client_info: tuple[str, int] = client_writer.get_extra_info("peername")

        packet_length = await read_var_int(client_reader)
        packet_id = await read_var_int(client_reader)
        if packet_id != 0x00:
            raise Exception("Expected handshake packet")

        protocol_version = await read_var_int(client_reader)
        server_address = await read_string(client_reader)
        server_port = await read_ushort(client_reader)
        next_state = await read_var_int(client_reader)

        target = self.check_domain((server_address, server_port), client_info)
        if not target:
            raise Exception("Invalid domain")

        print(f"Client {client_info} connected to {target}")

        server_reader, server_writer = await asyncio.open_connection(target[0], target[1])

        # Перенаправляем пакет рукопожатия на сервер
        await write_varint(server_writer, packet_length)
        await write_varint(server_writer, packet_id)
        await write_varint(server_writer, protocol_version)
        await write_string(server_writer, server_address)
        await write_ushort(server_writer, server_port)
        await write_varint(server_writer, next_state)

        # Перенаправляем все остальные пакеты
        try:
            await asyncio.gather(
                self.pipe(client_reader, server_writer),
                self.pipe(server_reader, client_writer),
            )
        except ConnectionResetError:
            pass

        print(f"Client {client_info} disconnected")
        client_writer.close()
        server_writer.close()

    async def pipe(self, reader, writer):
        while True:
            try:
                data = await reader.read(4096)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
            except ConnectionResetError:
                break


class MinecraftProxy:
    def __init__(self):
        self.config = Config("config.json")

    async def start(self):
        cproxy = ClientProxy(self.config)
        server = await asyncio.start_server(
            cproxy.handle_client,
            self.config.proxy_host,
            self.config.proxy_port,
            reuse_address=True
        )
        async with server:
            await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(MinecraftProxy().start())
