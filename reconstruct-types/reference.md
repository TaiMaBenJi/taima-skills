# Type Reconstruction Technical Reference

Detailed reference for memory access patterns, mangled name decoding, vtable layouts, and struct reconstruction techniques.

---

## Memory Access Patterns in IDA Decompiled Code

### Pattern Types

The scanner recognizes three primary patterns in Hex-Rays decompiled output:

| Pattern | Example | Offset Calculation |
|---------|---------|-------------------|
| Typed pointer arith | `*((_QWORD *)ptr + 14)` | `14 * sizeof(QWORD) = 14 * 8 = 112 = 0x70` |
| Byte offset cast | `*(_DWORD *)(ptr + 0x10)` | `0x10 = 16` (direct byte offset) |
| Zero offset deref | `*(_DWORD *)ptr` | `0` |

**Key distinction**: Double parens `*((_TYPE *)base + N)` use element indexing (multiply by type size). Single parens with addition inside `*(_TYPE *)(base + N)` use direct byte offsets.

### IDA Type to Size Mapping

| IDA Type | Bytes | C Type |
|----------|-------|--------|
| `_BYTE`, `char`, `bool` | 1 | `uint8_t` / `char` / `bool` |
| `_WORD`, `short` | 2 | `uint16_t` / `int16_t` |
| `_DWORD`, `int`, `LONG`, `HRESULT` | 4 | `uint32_t` / `int32_t` |
| `_QWORD`, `__int64` | 8 | `uint64_t` / `int64_t` |

### Offset Calculation Examples

```
*((_QWORD *)ptr + 14)   → offset = 14 * 8 = 112 = 0x70
*((_DWORD *)ptr + 32)   → offset = 32 * 4 = 128 = 0x80
*((_BYTE  *)ptr + 20)   → offset = 20 * 1 =  20 = 0x14
*(_DWORD *)ptr           → offset = 0
*(_QWORD *)(ptr + 0x30) → offset = 0x30 = 48  (byte offset, NOT multiplied)
```

### Store vs Load Detection

Both loads and stores use the same patterns:

```cpp
v5 = *((_QWORD *)a1 + 14);          // LOAD from +0x70
*((_QWORD *)a1 + 14) = v3;          // STORE to +0x70
*(_DWORD *)a2 = 45;                  // STORE to +0x00
if ( *((_BYTE *)a1 + 32) )          // LOAD from +0x20
```

### Patterns NOT Currently Scanned (decompiled)

These decompiled code patterns require manual analysis:

- **Nested dereferences**: `*(TYPE *)(*(QWORD *)(a1 + 8) + N)` -- pointer chain through another struct
- **Array indexing**: `*(DWORD *)(ptr + 4 * idx)` -- variable offset (loop-dependent)
- **Direct field access**: `a1->field` -- only when IDA has type information applied
- **Function pointer casts**: `((void (__fastcall *)(_QWORD))(**((_QWORD **)a1 + 1) + 8LL))` -- vtable calls
- **LODWORD/HIDWORD wrappers**: `LODWORD(*((_QWORD *)this + 3))` -- partial access

---

## Assembly Scanning (Ground Truth)

Assembly is the **authoritative source** for struct field sizes and offsets. The scanner
analyses x64 assembly from the DB alongside the decompiled code for maximum accuracy.

### Why Assembly Matters

| Advantage | Example |
|-----------|---------|
| **Exact sizes** from instruction operands | `mov r8d, [r13+14h]` → DWORD (4B) guaranteed by `r8d` |
| **Exact hex offsets** with no element-vs-byte ambiguity | `[r13+0Ch]` → offset 0x0C = 12 directly |
| **Missing accesses** the decompiler optimised away | `cmp [rbx+68h], r14` visible in asm but absent in decompiled |
| **Cross-validation** between both sources | Decompiled says 4B, assembly says 8B → trust assembly |

### How Sizes Are Determined

**Priority 1 -- explicit `ptr` qualifier** (most reliable):

| Qualifier | Size |
|-----------|------|
| `byte ptr [reg+off]` | 1 |
| `word ptr [reg+off]` | 2 |
| `dword ptr [reg+off]` | 4 |
| `qword ptr [reg+off]` | 8 |

**Priority 2 -- destination/source register width**:

| Register class | Size | Examples |
|----------------|------|----------|
| 64-bit | 8 | rax, rbx, rcx, rdx, r8–r15 |
| 32-bit | 4 | eax, ebx, ecx, edx, r8d–r15d |
| 16-bit | 2 | ax, bx, cx, dx, r8w–r15w |
| 8-bit  | 1 | al, bl, cl, dl, r8b–r15b |

### Parameter Register Tracking

The scanner detects prologue register saves (e.g., `mov r13, rcx`) within the first
~30 instructions. This builds an alias map so that later accesses like `[r13+14h]`
are correctly attributed to parameter 1 (the same struct as `a1` / `this`).

x64 fastcall parameter registers:

| Register family | Parameter # |
|-----------------|-------------|
| rcx / ecx / cx / cl | 1 (this) |
| rdx / edx / dx / dl | 2 |
| r8 / r8d / r8w / r8b | 3 |
| r9 / r9d / r9w / r9b | 4 |

### Excluded Patterns

- **Stack accesses**: `[rsp+...]`, `[rbp+...]` -- local variables, not struct fields
- **Scaled indexing**: `[rax+rcx*8+10h]` -- array / dynamic offset (not a fixed field)

---

## Microsoft C++ Mangled Name Format

### Structure

```
?MethodName@ClassName@Namespace@@EncodingSuffix
```

- `?` prefix marks all mangled names
- `@`-separated components form the qualified name (innermost first)
- `@@` separates the qualified name from the encoding

### Special Method Prefixes

| Prefix | Meaning | Example |
|--------|---------|---------|
| `??0` | Constructor | `??0CMyClass@@QEAA@XZ` → `CMyClass::CMyClass()` |
| `??1` | Destructor | `??1CMyClass@@UEAA@XZ` → `CMyClass::~CMyClass()` |
| `??_G` | Scalar deleting destructor | `??_GCMyClass@@UEAAPEAXI@Z` |
| `??_E` | Vector deleting destructor | `??_ECMyClass@@...` |
| `??_7` | VFTable | `??_7CMyClass@@6B@` → `CMyClass::'vftable'` |
| `??_R0` | RTTI Type Descriptor | `??_R0?AVCMyClass@@@8` |
| `??_R1` | RTTI Base Class Descriptor | |
| `??_R3` | RTTI Class Hierarchy Descriptor | |
| `??_R4` | RTTI Complete Object Locator | |

### Access Encoding (after `@@`)

| Prefix | Access |
|--------|--------|
| `UEAA`, `UEBA`, `UEA` | Public virtual |
| `QEAA`, `QEBA`, `QEA` | Public non-virtual |
| `AEAA`, `AEBA`, `AEA` | Private |
| `IEAA`, `IEBA`, `IEA` | Protected |

### Namespace Decoding Example

```
?Initialize@CService@AppInfo@@UEAAJXZ
```

Reading `@`-separated parts: `Initialize`, `CService`, `AppInfo`, `@@...`
- Method: `Initialize`
- Class: `CService`
- Namespace: `AppInfo`
- Full: `AppInfo::CService::Initialize`
- `UEAA` → public virtual, `J` → returns `long`, `XZ` → no params

---

## VTable Context Data

### vtable_contexts JSON Format

Stored per-function in the DB as a JSON array:

```json
[
  {
    "reconstructed_classes": [
      "class CMyClass {\n  virtual void Method1();\n  virtual void Method2();\n};"
    ],
    "source_ea": "0x180012345",
    "extraction_type": "detailed_vtable_analysis"
  }
]
```

### Using VTable Skeletons

The `reconstructed_classes` strings are C++ class outlines with virtual methods. They reveal:

1. **Virtual method order** -- slot positions in the vtable
2. **Virtual method signatures** -- parameter and return types
3. **Class name** -- from the class declaration

Standard COM vtable layout (first 3 slots):

| VTable Offset | Method |
|---------------|--------|
| `+0x00` | `QueryInterface` |
| `+0x08` | `AddRef` |
| `+0x10` | `Release` |
| `+0x18` | First custom virtual method |

---

## Struct Reconstruction Strategy

### Priority Order for Field Discovery

1. **Constructors** (`??0`) -- initialize fields in order; the decompiled constructor reveals the initialization sequence and often all fields
2. **Destructors** (`??1`, `??_G`) -- cleanup code shows resource-holding fields (handles, pointers, COM interfaces)
3. **Virtual methods** -- access `this` pointer fields extensively
4. **Regular methods** -- additional field usage
5. **External callers** -- functions that receive the struct as a parameter

### Identifying Field Types Beyond Size

| Clue | Likely Type |
|------|-------------|
| Field passed to `CreateFileW`, `OpenProcess` | `HANDLE` |
| Field compared with `< 0` (HRESULT check) | `HRESULT` |
| Field used as function pointer or vtable | `void*` / vtable pointer |
| Field passed to `wcslen`, `wcscpy` | `wchar_t*` |
| Field incremented/decremented atomically | Reference count (`LONG`) |
| Field used in `EnterCriticalSection` | `CRITICAL_SECTION` |
| 8-byte field at offset 0 | Often a vtable pointer |

### Handling Ambiguous Accesses

When the same offset is accessed as different types:

```
+0x10 accessed as _DWORD in Function1
+0x10 accessed as _QWORD in Function2
```

Possible interpretations:
- **Union**: The field is used as different types in different contexts
- **Partial access**: Function1 reads only the low 32 bits of a 64-bit field
- **Type confusion**: One function has incorrect type info (trust the larger access)

### Alignment and Padding

Windows x64 structs follow natural alignment:
- 1-byte fields: any offset
- 2-byte fields: even offsets
- 4-byte fields: 4-byte aligned offsets
- 8-byte fields: 8-byte aligned offsets
- Struct total size: aligned to largest member

Use `_unknown_XX` padding arrays to fill gaps between known fields. As more functions are analyzed, unknown regions get resolved into real fields.

---

## Database Queries for Type Reconstruction

### Find All Functions for a Class

```sql
SELECT function_id, function_name, mangled_name, function_signature
FROM functions
WHERE mangled_name LIKE '%@ClassName@@%' COLLATE NOCASE
ORDER BY function_name;
```

### Find Constructor/Destructor

```sql
-- Constructors
SELECT * FROM functions WHERE mangled_name LIKE '??0ClassName@@%';
-- Destructors (regular + scalar deleting)
SELECT * FROM functions WHERE mangled_name LIKE '??1ClassName@@%'
   OR mangled_name LIKE '??_GClassName@@%';
```

### Find Functions with VTable Contexts

```sql
SELECT function_id, function_name, vtable_contexts
FROM functions
WHERE vtable_contexts IS NOT NULL
  AND vtable_contexts != ''
  AND vtable_contexts NOT LIKE 'null%'
  AND vtable_contexts NOT LIKE '[]%';
```

### Find Functions Referencing a Type in Signature

```sql
SELECT function_id, function_name, function_signature_extended
FROM functions
WHERE function_signature_extended LIKE '%TypeName%' COLLATE NOCASE;
```

---

## Script Output Formats

### scan_struct_fields.py --json

```json
{
  "module": "appinfo.dll",
  "class_filter": "CMyClass",
  "functions_scanned": 5,
  "per_function": {
    "CMyClass::Init": {
      "function_id": 42,
      "class_name": "CMyClass",
      "param_types": {"this": "CMyClass *"},
      "fields_by_base": {
        "this": {
          "base_type": "CMyClass *",
          "fields": [
            {"byte_offset": 0, "offset_hex": "0x00", "size": 4, "access_type": "_DWORD"},
            {"byte_offset": 16, "offset_hex": "0x10", "size": 8, "access_type": "_QWORD"}
          ]
        }
      }
    }
  },
  "merged_types": {
    "CMyClass": {
      "fields": [
        {"byte_offset": 0, "offset_hex": "0x00", "size": 4, "access_types": ["_DWORD"], "source_functions": ["Init", "Process"]},
        {"byte_offset": 16, "offset_hex": "0x10", "size": 8, "access_types": ["_QWORD"], "source_functions": ["Init"]}
      ],
      "total_source_functions": 2
    }
  }
}
```

### extract_class_hierarchy.py --json

```json
{
  "module": "appinfo.dll",
  "total_classes": 15,
  "classes": {
    "CMyClass": {
      "class_name": "CMyClass",
      "namespaces": ["AppInfo"],
      "constructors": [{"name": "CMyClass", "function_id": 10, "signature": "..."}],
      "destructors": [{"name": "~CMyClass", "function_id": 11, "role": "destructor"}],
      "virtual_methods": [{"name": "Init", "function_id": 42, "access": "public_virtual"}],
      "methods": [...],
      "vtable_skeletons": ["class CMyClass { virtual void Init(); ... };"],
      "function_ids": [10, 11, 42, 43, 44]
    }
  }
}
```
