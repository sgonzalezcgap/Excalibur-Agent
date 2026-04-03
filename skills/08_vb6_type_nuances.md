---
id: vb6_type_nuances
title: VB6 Integer/Long Type Nuances in Migration
category: dbvariant_cast
severity: high
symptoms: [Integer overflow, Long to int, wrong type, VB6 Integer is short, VB6 Long is int, type size mismatch]
applies_to: []
vb6_pattern: VB6 Integer=16bit, Long=32bit
dotnet_fix: Map correctly — VB6 Integer→short, VB6 Long→int
---

## Critical VB6/.NET Type Difference

| VB6 Type | Size | .NET Equivalent |
|----------|------|-----------------|
| **Integer** | 16-bit | **short** (Int16) — NOT int! |
| **Long** | 32-bit | **int** (Int32) |
| **Single** | 32-bit | **float** |
| **Double** | 64-bit | **double** |
| **Currency** | 64-bit | **decimal** |
| **Date** | 64-bit | **DateTime** |
| **Variant** | varies | **object** or **DbVariant<T>** |

## Common Migration Error

VBUC sometimes maps VB6 `Integer` to C# `int` (32-bit) instead of `short` (16-bit).
This usually works but can cause issues with:
- Database column types that expect Int16
- COM interop where parameter size matters
- Overflow when the reverse happens (VB6 Long mapped to short)

## Fix
Always verify the VB6 source type when debugging cast/overflow errors:
```csharp
// If VB6 had: Dim nValue As Integer
// Correct .NET: short nValue;
// WRONG .NET:   int nValue;  // over-sized but usually works

// If VB6 had: Dim nValue As Long
// Correct .NET: int nValue;
// WRONG .NET:   long nValue;  // over-sized
```

## Legacy Contract
Do NOT change the type size unless the expected result explicitly requires it.
Maintaining VB6/.NET parity is critical for database interactions.
