import socket
from asyncio import AbstractEventLoop
from typing import Literal


def readVarInt(buffer: bytearray) -> tuple[bytearray, int]:
    SEGMENT_BITS = 0x7F
    CONTINUE_BIT = 0x80

    value: int = 0
    position: int = 0

    while True:
        currentByte = buffer[0]
        buffer = buffer[1:]
        value |= (currentByte & SEGMENT_BITS) << position

        if (currentByte & CONTINUE_BIT) == 0: break;
        position += 7

        if position >= 32: raise RuntimeError("VarInt is too big");
    return buffer, value


async def async_read_packet(loop: AbstractEventLoop, s: socket.socket) -> tuple[bytearray, bytearray]:
    SEGMENT_BITS = 0x7F
    CONTINUE_BIT = 0x80

    value: int = 0
    position: int = 0
    raw = bytearray()

    while True:
        currentByte = (await loop.sock_recv(s, 1))[0]
        raw += bytes([currentByte])

        value |= (currentByte & SEGMENT_BITS) << position

        if (currentByte & CONTINUE_BIT) == 0: break;
        position += 7

        if position >= 32: raise RuntimeError("VarInt is too big");

    packet = bytearray(await loop.sock_recv(s, value))
    raw += packet

    print(f'[IN] L{value} DATA {packet.hex(" ")}')
    return raw, packet

def decode_handshake(buffer: bytearray) -> tuple[int, str, int]:
    buffer, protocol_ver = readVarInt(buffer)
    _s_addr_len = int(buffer[0]); buffer = buffer[1:]

    server_addr = buffer[:_s_addr_len].decode('utf-8'); buffer = buffer[_s_addr_len:]
    server_port = int.from_bytes(buffer[:2], byteorder='big', signed=False)

    return protocol_ver, server_addr, server_port


