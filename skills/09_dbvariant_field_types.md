---
id: dbvariant_field_types
title: Fix Incorrect DbParameter Field Types → DbVariant<T>
category: dbvariant_cast
severity: critical
symptoms: [DbParameter, UpgradeHelpers.DB.AdoFactoryManager, CreateParameter, InvalidCastException, IConvertible, fixing field types, DbVariant, nullable column]
applies_to: [PD_Policy, PD_BillingInvoiceData, PD_PolicyMarineMatrix, PD_PolicyBCAMarineMatrix]
vb6_pattern: Variant fields migrated as DbParameter or UpgradeHelpers stub types
dotnet_fix: Replace with DbVariant<T> wrapper class from DataObjects/DbVariant.cs
---

## Problem

VB6 `Variant` fields were migrated as `DbParameter` or `UpgradeHelpers` stub types.
These must be replaced with the lightweight `DbVariant<T>` wrapper class defined in
`Upgraded/DataObjects/DbVariant.cs` (namespace: `ARM_DataObjects`).

`DbVariant<T>` is a **class** (not struct) with a `.Value` property of type `object` that:
- Returns `DBNull.Value` when the field is null/unset
- Accepts `DBNull.Value` to reset to null
- Accepts any typed value and stores it internally
- Uses `Convert.ChangeType` internally for type coercion

## Type Mapping
| DB column type | C# `T` |
|---|---|
| INT, SMALLINT, TINYINT | `int` |
| FLOAT, DECIMAL, MONEY, NUMERIC | `double` |
| VARCHAR, NVARCHAR, CHAR, TEXT | `string` |
| DATETIME, DATE | `DateTime` |

## Rule 1: Field Declaration
```csharp
// ❌ BEFORE:
private DbParameter m_itPOLICY_UMBRELLA_ID = UpgradeHelpers.DB.AdoFactoryManager.GetFactory().CreateParameter();

// ✅ AFTER:
//GAP-Note: fixing field types
private DbVariant<int> m_itPOLICY_UMBRELLA_ID = new();
```

## Rule 2: Property Declaration
```csharp
// ❌ BEFORE:
public DbParameter POLICY_UMBRELLA_ID
{
    get => m_itPOLICY_UMBRELLA_ID;
    set => m_itPOLICY_UMBRELLA_ID = value;
}

// ✅ AFTER:
//GAP-Note: fixing field types
public DbVariant<int> POLICY_UMBRELLA_ID
{
    get => m_itPOLICY_UMBRELLA_ID;
    set => m_itPOLICY_UMBRELLA_ID.Value = value.Value;
}
```

## Rule 3: Update() / Stored Procedure Parameter Assignment
Use `.Value` when passing to stored procedure parameters:
```csharp
// ❌ BEFORE:
aStoredProc.Parameters[28].Value = m_itPOLICY_UMBRELLA_ID;

// ✅ AFTER:
//GAP-Note: fixing field types
aStoredProc.Parameters[28].Value = m_itPOLICY_UMBRELLA_ID.Value;
```

## Rule 4: Populate() / AddFromSQL() — Reading from DB Recordset
```csharp
// ❌ BEFORE:
m_itPOLICY_UMBRELLA_ID.Value = rsRec.GetField("POLICY_UMBRELLA_ID").Value;

// ✅ AFTER:
//GAP-Note: fixing field types
m_itPOLICY_UMBRELLA_ID.Value = rsRec["POLICY_UMBRELLA_ID"];
```

## Rule 5: Form/Caller Side — Reading DbVariant<T> Properties
ALWAYS use `.Value` when reading:
```csharp
// ❌ BEFORE:
txtCarrier.Text = Global_V.oUtil.UnNull(woPolicy.Carrier);

// ✅ AFTER:
//GAP-Note: fixing field types
txtCarrier.Text = Global_V.oUtil.UnNull(woPolicy.Carrier.Value);
```

## Rule 6: Form/Caller Side — Writing DbVariant<T> Properties
ALWAYS use `.Value` when writing:
```csharp
// ❌ BEFORE:
woPolicy.Carrier = ReflectionHelper.GetPrimitiveValue(Global_V.oUtil.MakeNull(txtCarrier.Text));

// ✅ AFTER:
//GAP-Note: fixing field types
woPolicy.Carrier.Value = ReflectionHelper.GetPrimitiveValue(Global_V.oUtil.MakeNull(txtCarrier.Text));
```

## Rule 7: Null/DBNull Checks
Use `Convert.IsDBNull(field.Value)`:
```csharp
//GAP-Note: fixing field types
if (!Convert.IsDBNull(woPolicy.PRODUCER_ID.Value))
{
    Global_V.ocmbProducers.SelectPDCombo(pcmbProducer, woPolicy.PRODUCER_ID.Value);
}
```

## Rule 8: Assigning DBNull
Use `DBNull.Value` (NOT C# `null`):
```csharp
//GAP-Note: fixing field types
woPolicy.POLICY_UMBRELLA_ID.Value = DBNull.Value;
```

## Rule 9: Which Fields Need DbVariant<T>?
Apply ONLY to fields that:
1. Were `DbParameter` or `UpgradeHelpers` stub types, OR
2. Map to a nullable DB column (VB6 code assigned `Null`/`DBNull.Value`)

Do NOT apply to `int`, `string`, `bool`, `DateTime` fields that are always non-null.

## Rule 10: GAP-Note Comment
Every modified line MUST have `//GAP-Note: fixing field types` above it.

## Checklist
1. Identify all `DbParameter` field declarations → replace with `DbVariant<T>`
2. Update matching property return types to `DbVariant<T>`
3. Fix `Update()`: add `.Value` to all `DbVariant<T>` parameter assignments
4. Fix `Populate()`/`AddFromSQL()`: add `.Value` to all assignments
5. Fix caller forms: add `.Value` to all reads and writes
6. Add `//GAP-Note: fixing field types` above every modified line

## Target Files
- `Upgraded/DataObjects/PD_*.cs` — data object classes
- `Upgraded/ExcaliburEXE/frm*.cs` — form classes that read/write policy properties
