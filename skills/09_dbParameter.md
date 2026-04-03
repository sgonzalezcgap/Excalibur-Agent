---
name: fix-dbparameter-types
description: Replace incorrect DbParameter/UpgradeHelpers stub field types with DbVariant<T> wrapper class in VB6-to-C# migrated data object and form files
---

# Skill: Fix Incorrect DbParameter Field Types

## Context
This project is a VB6-to-C# migration (Excalibur Modernized). VB6 `Variant` fields were
migrated as `DbParameter` or `UpgradeHelpers` stub types. These must be replaced with the
lightweight `DbVariant<T>` wrapper class defined in
`Upgraded/DataObjects/DbVariant.cs`.

---

## Rule 1: DbVariant<T> class location
The `DbVariant<T>` class lives in:
`Upgraded/DataObjects/DbVariant.cs`
namespace: `ARM_DataObjects`

It is a **class** (not struct) with a single `Value` property of type `object` that:
- Returns `DBNull.Value` when the field is null/unset
- Accepts `DBNull.Value` to reset to null
- Accepts any typed value and stores it internally
- Uses `Convert.ChangeType` internally for type coercion

---

## Rule 2: Field declaration pattern
Replace any `DbParameter`, `UpgradeHelpers.DB.*`, or incorrectly typed field with `DbVariant<T>`.

Choose `T` based on the database column type:
| DB column type | C# `T` |
|---|---|
| INT, SMALLINT, TINYINT | `int` |
| FLOAT, DECIMAL, MONEY, NUMERIC | `double` |
| VARCHAR, NVARCHAR, CHAR, TEXT | `string` |
| DATETIME, DATE | `DateTime` |

### Before:
```csharp
private DbParameter m_itPOLICY_UMBRELLA_ID = UpgradeHelpers.DB.AdoFactoryManager.GetFactory().CreateParameter();
```

### After:
```csharp
//GAP-Note: fixing field types
private DbVariant<int> m_itPOLICY_UMBRELLA_ID = new();
```

---

## Rule 3: Property declaration pattern
Properties that expose `DbVariant<T>` fields must:
- Return type: `DbVariant<T>` (same as backing field)
- Getter: return the backing field directly
- Setter: assign to `backingField.Value`

### Before:
```csharp
public DbParameter POLICY_UMBRELLA_ID
{
    get => m_itPOLICY_UMBRELLA_ID;
    set => m_itPOLICY_UMBRELLA_ID = value;
}
```

### After:
```csharp
//GAP-Note: fixing field types
public DbVariant<int> POLICY_UMBRELLA_ID
{
    get => m_itPOLICY_UMBRELLA_ID;
    set => m_itPOLICY_UMBRELLA_ID.Value = value.Value;
}
```

---

## Rule 4: Update() / stored procedure parameter assignment
When passing `DbVariant<T>` fields to stored procedure parameters, use `.Value`:

### Before:
```csharp
aStoredProc.Parameters[28].Value = m_itPOLICY_UMBRELLA_ID;
```

### After:
```csharp
//GAP-Note: fixing field types
aStoredProc.Parameters[28].Value = m_itPOLICY_UMBRELLA_ID.Value;
```

This works correctly because `DbVariant<T>.Value` returns `DBNull.Value` when unset,
which OleDb correctly maps to a SQL NULL column.

---

## Rule 5: Populate() / AddFromSQL() — reading from DB recordset
When reading from a DB recordset into a `DbVariant<T>` field, assign directly to `.Value`:

### Before:
```csharp
m_itPOLICY_UMBRELLA_ID.Value = rsRec.GetField("POLICY_UMBRELLA_ID").Value;
```

### After:
```csharp
//GAP-Note: fixing field types
m_itPOLICY_UMBRELLA_ID.Value = rsRec["POLICY_UMBRELLA_ID"];
```

`DBNull` is preserved automatically because `DbVariant<T>.Value` setter handles it.

---

## Rule 6: Form / caller side — reading DbVariant<T> properties
When reading a `DbVariant<T>` property value in a form or caller class, always use `.Value`:

### Before (broken — missing .Value):
```csharp
txtCarrier.Text = Global_V.oUtil.UnNull(woPolicy.Carrier);
Global_V.oCmbOfficeID.SelectCombo(cmbIssuing_Office_ID, woPolicy.Issuing_Office_ID);
```

### After (correct):
```csharp
//GAP-Note: fixing field types
txtCarrier.Text = Global_V.oUtil.UnNull(woPolicy.Carrier.Value);
//GAP-Note: fixing field types
Global_V.oCmbOfficeID.SelectCombo(cmbIssuing_Office_ID, woPolicy.Issuing_Office_ID.Value);
```

---

## Rule 7: Form / caller side — writing DbVariant<T> properties
When setting a `DbVariant<T>` property in a form or caller class, always use `.Value`:

### Before (broken):
```csharp
woPolicy.Carrier = ReflectionHelper.GetPrimitiveValue(Global_V.oUtil.MakeNull(txtCarrier.Text));
```

### After (correct):
```csharp
//GAP-Note: fixing field types
woPolicy.Carrier.Value = ReflectionHelper.GetPrimitiveValue(Global_V.oUtil.MakeNull(txtCarrier.Text));
```

---

## Rule 8: Null / DBNull checks on DbVariant<T> fields
Use `Convert.IsDBNull(field.Value)` to check for null:

```csharp
//GAP-Note: fixing field types
if (!Convert.IsDBNull(woPolicy.PRODUCER_ID.Value))
{
    Global_V.ocmbProducers.SelectPDCombo(pcmbProducer, woPolicy.PRODUCER_ID.Value);
}
```

---

## Rule 9: Assigning DBNull to a DbVariant<T> field
When the original VB6 code assigned `Null` (i.e., DBNull), use:

```csharp
//GAP-Note: fixing field types
woPolicy.POLICY_UMBRELLA_ID.Value = DBNull.Value;
```

Do **NOT** use `null` (C# null) — OleDb requires `DBNull.Value` for SQL NULL.

---

## Rule 10: GAP-Note comment requirement
Every modified line **must** have this comment on the line directly above it:

```csharp
//GAP-Note: fixing field types
```

This applies to:
- Field declarations
- Property declarations
- `Update()` parameter assignments
- `Populate()` / `AddFromSQL()` assignments
- Form-side reads and writes

---

## Rule 11: Which fields require DbVariant<T>?
Apply `DbVariant<T>` **only** to fields that:
1. Previously were `DbParameter` or `UpgradeHelpers` stub types, **OR**
2. Map to a **nullable** database column (i.e., original VB6 code assigned `Null` / `DBNull.Value`)

Do **NOT** apply to:
- `int`, `string`, `bool`, `DateTime` fields that are always non-null
- Fields that never had `DBNull.Value` assigned in the original VB6 code

---

## Rule 12: Files that commonly need this fix
Based on the patterns found in this project, check these file types:
- `Upgraded/DataObjects/PD_*.cs` — data object classes
- `Upgraded/ExcaliburEXE/frm*.cs` — form classes that read/write policy properties

---

## Checklist when fixing a new file
1. [ ] Identify all `DbParameter` field declarations → replace with `DbVariant<T>`
2. [ ] Update matching property return types to `DbVariant<T>`
3. [ ] Fix `Update()`: add `.Value` to all `DbVariant<T>` parameter assignments
4. [ ] Fix `Populate()` / `AddFromSQL()`: add `.Value` to all `DbVariant<T>` assignments
5. [ ] Fix caller forms: add `.Value` to all reads and writes of `DbVariant<T>` properties
6. [ ] Add `//GAP-Note: fixing field types` above every modified line
7. [ ] Do NOT modify lines that are already correct