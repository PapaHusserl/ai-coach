"""Собирает синтетический FIT активности (file_id + session + activity) для тестов импорта.

Запуск: python tests/fixtures/make_fit.py. Данных пользователя нет: значения придуманы.
"""

import struct
from pathlib import Path

FIT_EPOCH = 631065600
START_UNIX = 1773125852  # 2026-03-10 06:57:32 UTC
LOCAL_OFFSET = 18000  # местное время = UTC+5, старт 11:57:32


def crc16(data: bytes) -> int:
    table = [0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401]
    table += [0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400]
    crc = 0
    for byte in data:
        crc = (crc >> 4) & 0x0FFF ^ table[crc & 0xF] ^ table[byte & 0xF]
        crc = (crc >> 4) & 0x0FFF ^ table[crc & 0xF] ^ table[(byte >> 4) & 0xF]
    return crc


def definition(local: int, mesg: int, fields: list[tuple[int, int, int]]) -> bytes:
    head = struct.pack("<BBBHB", 0x40 | local, 0, 0, mesg, len(fields))
    return head + b"".join(struct.pack("<BBB", *f) for f in fields)


def build(with_sets: bool = False, local: bool = True, start_time: bool = True) -> bytes:
    start = START_UNIX - FIT_EPOCH
    body = definition(0, 0, [(0, 1, 0x00), (1, 2, 0x84), (4, 4, 0x86)])
    body += struct.pack("<BBHI", 0, 4, 1, start)
    session_fields = [
        (5, 1, 0x00),
        (7, 4, 0x86),
        (8, 4, 0x86),
        (9, 4, 0x86),
        (11, 2, 0x84),
        (16, 1, 0x02),
        (17, 1, 0x02),
    ]
    if start_time:
        session_fields.insert(0, (2, 4, 0x86))
    body += definition(1, 18, session_fields)
    values = (1, 1800000, 1750000, 500000, 320, 140, 170)
    if start_time:
        body += struct.pack("<BIBIIIHBB", 1, start, *values)
    else:
        body += struct.pack("<BBIIIHBB", 1, *values)
    if local:
        body += definition(2, 34, [(253, 4, 0x86), (5, 4, 0x86), (1, 2, 0x84)])
        body += struct.pack("<BIIH", 2, start + 1800, start + 1800 + LOCAL_OFFSET, 1)
    else:
        body += definition(2, 34, [(253, 4, 0x86), (1, 2, 0x84)])
        body += struct.pack("<BIH", 2, start + 1800, 1)
    if with_sets:
        set_fields = [(10, 2, 0x84), (6, 4, 0x86), (0, 4, 0x86), (3, 2, 0x84)]
        set_fields += [(4, 2, 0x84), (5, 1, 0x02), (11, 2, 0x84)]
        body += definition(3, 225, set_fields)
        # (индекс, старт, длительность мс, повторы, вес кг*16, тип 1=active/0=rest, шаг плана)
        for i, (offset, reps, kg, kind, step) in enumerate(
            [(0, 10, 40, 1, 1), (60, 0, 0, 0, 2), (90, 8, 40, 1, 3)]
        ):
            body += struct.pack("<BHIIHHBH", 3, i, start + offset, 45000, reps, kg * 16, kind, step)
    header = struct.pack("<BBHI4s", 14, 0x20, 2132, len(body), b".FIT")
    header += struct.pack("<H", crc16(header))
    data = header + body
    return data + struct.pack("<H", crc16(data))


if __name__ == "__main__":
    Path(__file__).with_name("synthetic_run.fit").write_bytes(build())
    Path(__file__).with_name("synthetic_strength.fit").write_bytes(build(with_sets=True))
    Path(__file__).with_name("synthetic_no_local.fit").write_bytes(build(local=False))
    Path(__file__).with_name("synthetic_no_start.fit").write_bytes(build(start_time=False))
