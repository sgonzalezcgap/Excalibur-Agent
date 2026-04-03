---
id: dbvariant_cast
title: DbVariant<T> IConvertible Cast Failure
category: dbvariant_cast
severity: critical
symptoms: [InvalidCastException, IConvertible, DbVariant, Convert.ToDouble, Convert.ToInt32, cast error, type mismatch, FieldHelper]
applies_to: []
vb6_pattern: Variant type auto-converts between numeric types
dotnet_fix: Extract .Value before Convert, or use GetPrimitiveValue<T>
---

## Problem

`DbVariant<T>` is a wrapper from UpgradeHelpers.DB framework. Its `.Value` property returns
the value of type `T` (boxed as object). However, `DbVariant<T>` does **NOT** implement
`IConvertible`, so it cannot be passed directly to `Convert.ToDouble()`, `Convert.ToInt32()`, etc.

## Symptoms
- `InvalidCastException: Object must implement IConvertible`
- `Unable to cast object of type 'DbVariant<double>' to type 'System.IConvertible'`
- Any `Convert.To*()` call on a recordset column value

## Heuristic
**If a runtime error involves type mismatches or FieldHelper utilities, search for
`//GAP-Note. sgonzalez: Extract value from FieldHelper` patterns.**

## Fix Options

### Option A: Extract .Value first
```csharp
// BEFORE (bug):
double val = Convert.ToDouble(recordset["COLUMN"]);

// AFTER (fix):
// GAP-Note. agente, Extract .Value from DbVariant before conversion
double val = Convert.ToDouble(recordset["COLUMN"].Value);
```

### Option B: GetPrimitiveValue<T>
```csharp
// GAP-Note. agente, Use GetPrimitiveValue to safely extract typed value
int id = recordset.GetPrimitiveValue<int>("COLUMN");
```

### Option C: IsNull guard
```csharp
if (!recordset["COLUMN"].IsNull)
{
    double val = (double)recordset["COLUMN"].Value;
}
```

### Option D: Safe helper function (for bulk conversions)
```csharp
double safeDouble(object raw)
{
    if (raw is DbVariant<double> dv) return dv.Value;
    if (raw is DBNull || raw == null) return 0.0;
    return Convert.ToDouble(raw);
}
```

## Critical Notes
- `.Value` returns `T` boxed — if T=double, `.Value` returns `object` containing `double`
- `.IsNull` checks for null/DBNull
- NEVER use `(double)dbVariant` directly — use `(double)dbVariant.Value`
- `DateTime.FromOADate()` needs a `double`, not a `DbVariant<double>`

## Resolved Cases
- PD_BillingRules.cs: safeDouble helper + Bill_DT with DateTime.FromOADate
- PD_BillingRules.cs: PRODUCER_ID with GetPrimitiveValue<int> instead of <double>
- PDUtilityFunctions.cs: UnNull() extracts .Value via reflection
