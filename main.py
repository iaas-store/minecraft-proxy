import asyncio
import json


class Config:
    def __init__(self, config_file):
        with open(config_file, "r") as f:
            self.__dict__ = json.load(f)


class MinecraftProxy:
    def __init__(self, config):
        self.config = config

    async def handle_client(self, client_reader, client_writer):
        client_info = client_writer.get_extra_info("peername")

        print(f"Client {client_info} connected")

        # Читаем и анализируем пакет рукопожатия
        packet_length = await self.read_varint(client_reader)
        packet_id = await self.read_varint(client_reader)
        if packet_id != 0x00:
            raise Exception("Expected handshake packet")

        protocol_version = await self.read_varint(client_reader)
        server_address = await self.read_string(client_reader)
        server_port = await self.read_ushort(client_reader)
        next_state = await self.read_varint(client_reader)

        # Проверяем доменное имя
        if server_address not in self.config.domains:
            raise Exception("Invalid domain")

        target = self.config.domains[server_address]
        server_reader, server_writer = await asyncio.open_connection(
            target["target_host"], target["target_port"]
        )

        # Перенаправляем пакет рукопожатия на сервер
        await self.write_varint(server_writer, packet_length)
        await self.write_varint(server_writer, packet_id)
        await self.write_varint(server_writer, protocol_version)
        await self.write_string(server_writer, server_address)
        await self.write_ushort(server_writer, server_port)
        await self.write_varint(server_writer, next_state)

        # Перенаправляем все остальные пакеты
        try:
            await asyncio.gather(
                self.pipe(client_reader, server_writer),
                self.pipe(server_reader, client_writer),
            )
        except ConnectionResetError:
            pass
        finally:
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

    async def read_varint(self, reader):
        num_read = 0
        result = 0
        while True:
            byte = await reader.readexactly(1)
            byte = byte[0]
            value = byte & 0b01111111
            result |= value << (7 * num_read)

            num_read += 1
            if num_read > 5:
                raise Exception("VarInt is too big")

            if (byte & 0b10000000) == 0:
                break

        return result

    async def read_string(self, reader):
        length = await self.read_varint(reader)
        string_data = await reader.readexactly(length)
        return string_data.decode("utf-8")

    async def read_ushort(self, reader):
        ushort_data = await reader.readexactly(2)
        return int.from_bytes(ushort_data, byteorder="big")

    async def write_varint(self, writer, value):
        while True:
            byte = value & 0b01111111
            value >>= 7
            if value != 0:
                byte |= 0b10000000
            writer.write(bytes([byte]))
            if value == 0:
                break
        await writer.drain()

    async def write_string(self, writer, value):
        string_data = value.encode("utf-8")
        await self.write_varint(writer, len(string_data))
        writer.write(string_data)
        await writer.drain()

    async def write_ushort(self, writer, value):
        ushort_data = value.to_bytes(2, byteorder="big")
        writer.write(ushort_data)
        await writer.drain()

    async def start(self, host, port):
        server = await asyncio.start_server(self.handle_client, host, port)
        async with server:
            await server.serve_forever()


if __name__ == "__main__":
    config = Config("config.json")
    proxy = MinecraftProxy(config)
    asyncio.run(proxy.start(config.proxy_host, config.proxy_port))
