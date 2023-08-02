from asyncio import StreamWriter, StreamReader


async def read_var_int(reader: StreamReader) -> int:
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


async def read_string(reader: StreamReader) -> str:
    length = await read_var_int(reader)
    string_data = await reader.readexactly(length)
    return string_data.decode("utf-8")


async def read_ushort(reader: StreamReader) -> int:
    ushort_data = await reader.readexactly(2)
    return int.from_bytes(ushort_data, byteorder="big")


async def write_varint(writer: StreamWriter, value: int):
    while True:
        byte = value & 0b01111111
        value >>= 7
        if value != 0:
            byte |= 0b10000000
        writer.write(bytes([byte]))
        if value == 0:
            break
    await writer.drain()


async def write_string(writer: StreamWriter, value: str):
    string_data = value.encode("utf-8")
    await write_varint(writer, len(string_data))
    writer.write(string_data)
    await writer.drain()


async def write_ushort(writer: StreamWriter, value: int):
    ushort_data = value.to_bytes(2, byteorder="big")
    writer.write(ushort_data)
    await writer.drain()