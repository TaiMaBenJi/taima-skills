#!/usr/bin/env python3
"""Locate ELF init/init_array targets and dynamic relocation context."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


PT_DYNAMIC = 2
DT_NULL = 0
DT_INIT = 12
DT_RELA = 7
DT_RELASZ = 8
DT_RELAENT = 9
DT_REL = 17
DT_RELSZ = 18
DT_RELENT = 19
DT_INIT_ARRAY = 25
DT_INIT_ARRAYSZ = 27
DT_JMPREL = 23
DT_PLTRELSZ = 2

R_ARM_RELATIVE = 23
R_AARCH64_RELATIVE = 1027


@dataclass
class Segment:
    type: int
    offset: int
    vaddr: int
    filesz: int
    memsz: int
    flags: int
    align: int


def read_u(data: bytes, offset: int, size: int, endian: str) -> int:
    return int.from_bytes(data[offset : offset + size], endian, signed=False)


def parse_elf(path: Path) -> tuple[dict, list[Segment], bytes]:
    data = path.read_bytes()
    if len(data) < 64 or data[:4] != b"\x7fELF":
        raise SystemExit(f"not an ELF file: {path}")
    elf_class = data[4]
    endian = "little" if data[5] == 1 else "big"
    is_64 = elf_class == 2
    if is_64:
        e_phoff = read_u(data, 32, 8, endian)
        e_phentsize = read_u(data, 54, 2, endian)
        e_phnum = read_u(data, 56, 2, endian)
    else:
        e_phoff = read_u(data, 28, 4, endian)
        e_phentsize = read_u(data, 42, 2, endian)
        e_phnum = read_u(data, 44, 2, endian)
    segments = []
    for idx in range(e_phnum):
        off = e_phoff + idx * e_phentsize
        if is_64:
            p_type = read_u(data, off, 4, endian)
            p_flags = read_u(data, off + 4, 4, endian)
            p_offset = read_u(data, off + 8, 8, endian)
            p_vaddr = read_u(data, off + 16, 8, endian)
            p_filesz = read_u(data, off + 32, 8, endian)
            p_memsz = read_u(data, off + 40, 8, endian)
            p_align = read_u(data, off + 48, 8, endian)
        else:
            p_type = read_u(data, off, 4, endian)
            p_offset = read_u(data, off + 4, 4, endian)
            p_vaddr = read_u(data, off + 8, 4, endian)
            p_filesz = read_u(data, off + 16, 4, endian)
            p_memsz = read_u(data, off + 20, 4, endian)
            p_flags = read_u(data, off + 24, 4, endian)
            p_align = read_u(data, off + 28, 4, endian)
        segments.append(Segment(p_type, p_offset, p_vaddr, p_filesz, p_memsz, p_flags, p_align))
    header = {
        "class": "ELF64" if is_64 else "ELF32",
        "endian": endian,
        "program_header_offset": hex(e_phoff),
        "program_header_count": e_phnum,
    }
    return header, segments, data


def vaddr_to_offset(vaddr: int, segments: list[Segment]) -> int | None:
    for seg in segments:
        if seg.type != 1:
            continue
        if seg.vaddr <= vaddr < seg.vaddr + seg.filesz:
            return seg.offset + (vaddr - seg.vaddr)
    return None


def parse_dynamic(data: bytes, segments: list[Segment], is_64: bool, endian: str) -> dict[int, list[int]]:
    dynamic_seg = next((seg for seg in segments if seg.type == PT_DYNAMIC), None)
    if not dynamic_seg:
        return {}
    entry_size = 16 if is_64 else 8
    tags: dict[int, list[int]] = {}
    for off in range(dynamic_seg.offset, dynamic_seg.offset + dynamic_seg.filesz, entry_size):
        if is_64:
            tag = read_u(data, off, 8, endian)
            val = read_u(data, off + 8, 8, endian)
        else:
            tag = read_u(data, off, 4, endian)
            val = read_u(data, off + 4, 4, endian)
        tags.setdefault(tag, []).append(val)
        if tag == DT_NULL:
            break
    return tags


def read_pointer_array(data: bytes, file_offset: int, size: int, ptr_size: int, endian: str) -> list[int]:
    values = []
    for off in range(file_offset, file_offset + size, ptr_size):
        if off + ptr_size <= len(data):
            values.append(read_u(data, off, ptr_size, endian))
    return values


def parse_relocations(data: bytes, file_offset: int | None, total_size: int, entry_size: int, is_64: bool, endian: str) -> list[dict]:
    if file_offset is None or not total_size:
        return []
    if not entry_size:
        entry_size = 24 if is_64 else 8
    relocs = []
    for off in range(file_offset, file_offset + total_size, entry_size):
        if off + entry_size > len(data):
            break
        if is_64:
            r_offset = read_u(data, off, 8, endian)
            r_info = read_u(data, off + 8, 8, endian)
            r_addend = read_u(data, off + 16, 8, endian) if entry_size >= 24 else 0
            r_type = r_info & 0xFFFFFFFF
        else:
            r_offset = read_u(data, off, 4, endian)
            r_info = read_u(data, off + 4, 4, endian)
            r_addend = read_u(data, off + 8, 4, endian) if entry_size >= 12 else 0
            r_type = r_info & 0xFF
        relocs.append({"offset": r_offset, "type": r_type, "addend": r_addend})
    return relocs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("so", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    header, segments, data = parse_elf(args.so)
    is_64 = header["class"] == "ELF64"
    endian = header["endian"]
    ptr_size = 8 if is_64 else 4
    tags = parse_dynamic(data, segments, is_64, endian)

    init_array_vaddr = (tags.get(DT_INIT_ARRAY) or [0])[0]
    init_array_size = (tags.get(DT_INIT_ARRAYSZ) or [0])[0]
    init_array_file_offset = vaddr_to_offset(init_array_vaddr, segments) if init_array_vaddr else None
    init_array = (
        read_pointer_array(data, init_array_file_offset, init_array_size, ptr_size, endian)
        if init_array_file_offset is not None
        else []
    )

    rela_vaddr = (tags.get(DT_RELA) or [0])[0]
    rela_size = (tags.get(DT_RELASZ) or [0])[0]
    rela_ent = (tags.get(DT_RELAENT) or [0])[0]
    rel_vaddr = (tags.get(DT_REL) or [0])[0]
    rel_size = (tags.get(DT_RELSZ) or [0])[0]
    rel_ent = (tags.get(DT_RELENT) or [0])[0]
    rela = parse_relocations(data, vaddr_to_offset(rela_vaddr, segments), rela_size, rela_ent, is_64, endian)
    rel = parse_relocations(data, vaddr_to_offset(rel_vaddr, segments), rel_size, rel_ent, is_64, endian)
    relative_type = R_AARCH64_RELATIVE if is_64 else R_ARM_RELATIVE
    relative_init_relocs = [
        item for item in rela + rel if item["type"] == relative_type and init_array_vaddr <= item["offset"] < init_array_vaddr + init_array_size
    ]

    result = {
        "schema": "android-native-auto-reverse.elf_init_array.v1",
        "input": str(args.so),
        "header": header,
        "dynamic": {
            "DT_INIT": hex((tags.get(DT_INIT) or [0])[0]),
            "DT_INIT_ARRAY": hex(init_array_vaddr),
            "DT_INIT_ARRAYSZ": init_array_size,
            "DT_RELA": hex(rela_vaddr),
            "DT_RELASZ": rela_size,
            "DT_REL": hex(rel_vaddr),
            "DT_RELSZ": rel_size,
        },
        "init_array_file_offset": hex(init_array_file_offset) if init_array_file_offset is not None else None,
        "init_array_targets": [hex(value) for value in init_array],
        "relative_relocations_in_init_array": [
            {"offset": hex(item["offset"]), "addend": hex(item["addend"])} for item in relative_init_relocs
        ],
        "entry_candidates": [hex(item["addend"] or value) for item, value in zip(relative_init_relocs, init_array)]
        or [hex(value) for value in init_array],
    }

    text = json.dumps(result, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    if result["entry_candidates"]:
        print("entry_candidates:", ", ".join(result["entry_candidates"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
