---
name: vb6-base1-to-base0-arrays
description: >
  Fixes VB6-to-C# migrated array indexing issues in the Excalibur Modernized project.
  USE THIS SKILL whenever you encounter C# code (produced by VBUC) that accesses arrays
  using VB6-era 1-based indices instead of .NET 0-based indices — this causes off-by-one
  errors, skipped first rows, or IndexOutOfRangeException at runtime. Covers all array
  usage contexts: UnboundColumnFetch grid data binding, row selection methods using
  RowBookmark, loops iterating over array rows, DBNull checks on array cells, and
  ArraysHelper.CastArray type mismatches. Trigger on any of: 1-based array access in
  migrated code, "base 1" or "base 0" discussion, off-by-one errors on grid data,
  `for (i = 1; i <= count` loop patterns used with 0-based arrays,
  `Values[RowIndex, col] = arr[col, RowIndex]` multi-column UnboundColumnFetch pattern,
  `if (lCurrentRowIndex > 0)` row selection guards, or when a user reports missing first
  row data or wrong column data in a grid.
---

# Skill: Fix VB6 Base-1 to .NET Base-0 Array Indexing

## Context

This project is a VB6-to-C# migration (Excalibur Modernized). VB6 arrays default to
`Option Base 1` or explicit `(1 To N)` bounds. The VBUC migration tool translated these
into C# but often preserved the 1-based index logic in the consuming code while the
underlying .NET arrays are 0-based. This mismatch causes:

- **Off-by-one errors**: first row skipped, last row causes `IndexOutOfRangeException`
- **Wrong column data**: column indices shifted by 1
- **Row selection guards excluding row 0**: `if (index > 0)` should be `if (index >= 0)`

### How arrays are created in this project

There are **two patterns** for how data object methods create arrays:

**Pattern A — Standard 0-based (most common):**
```csharp
// In the data object (e.g., PD_PolicyMarineMatrix.cs, PD_Special_Rate.cs)
arrResult = new object[3, recordCount]; // 0-based both dimensions
lAll = 1;
while (!rst.EOF)
{
    arrResult[0, lAll - 1] = rst["Col0"];
    arrResult[1, lAll - 1] = rst["Col1"];
    arrResult[2, lAll - 1] = rst["Col2"];
    lAll++;
    rst.MoveNext();
}
```
The VB6 `lAll = 1` start is a vestige, but `lAll - 1` makes the actual storage 0-based.

**Pattern B — Non-zero lower bounds (legacy):**
```csharp
// In the data object (e.g., PD_PolicyEndorsement.cs, PD_BillingInvoiceData.cs)
arrResult = Array.CreateInstance(typeof(object),
    new int[] { 10, recordCount },    // lengths
    new int[] { 0, 1 });              // lower bounds — rows start at 1!
```
These arrays have `GetLowerBound(1) == 1`, meaning row indices start at 1.
`ArraysHelper.CastArray<T>()` preserves these non-standard lower bounds.

---

## Workflow Overview

When asked to fix array indexing in a file, follow this sequence:

1. **Discover** all arrays (Rule 1)
2. **Classify** each array's index basis by tracing to its source (Rule 2)
3. **Fix** each usage pattern (Rules 3–6, 8) for 0-based arrays
4. **Report** arrays with non-zero lower bounds for user decision (Rule 7)
5. **Comment** all changes (Rule 9)

---

## Rule 1: Discovery — Inventory all arrays in the target file

Search the target file for array field declarations matching these patterns:

```
private T[] arrName = null;
private T[,] arrName = null;
private T[, ] arrName = null;
private Array arrName = null;
```

For each array found, build an inventory entry:

| Item | How to find |
|------|-------------|
| **Declaration** | Line number, type, name |
| **Count variable** | Nearby `private int lArrNameCount` or `lngArrNameCount` field |
| **Population** | Search for `arrName =` assignments; trace to the data object method that returns it |
| **Grid events** | Search for `UnboundColumnFetch` and `UnboundColumnUpdated` handlers that reference `arrName` |
| **Selection methods** | Search for methods like `GetSelected*` that read from `arrName` |
| **Loop accesses** | Search for `for` loops that iterate using the count variable and access `arrName[...]` |
| **DBNull checks** | Search for `Convert.IsDBNull(arrName[...])` patterns |

Present the inventory to help plan fixes before making any changes.

---

## Rule 2: Determine the source array's index basis

For each array in the inventory, trace back to the data object method that creates it.

### Classification rules:

| Creation pattern | Index basis |
|-----------------|-------------|
| `new T[cols, rows]` | **0-based** (standard .NET) |
| `new T[size]` | **0-based** (standard .NET) |
| `Array.CreateInstance(type, lengths, lowerBounds)` where all bounds are 0 | **0-based** |
| `Array.CreateInstance(type, lengths, lowerBounds)` where any bound ≠ 0 | **Non-zero lower bound** — see Rule 7 |

### ArraysHelper.CastArray behavior:

`ArraysHelper.CastArray<T>()` (in `UpgradeSupport/UpgradeHelpers.Utils/ArraysHelper.cs`)
**preserves the source array's lower bounds**. It reads `GetLowerBound()` from the source
and passes them to `Array.CreateInstance` for the destination. So:
- If source is 0-based → `CastArray` result is 0-based
- If source has `lowerBounds = {0, 1}` → `CastArray` result also has `lowerBounds = {0, 1}`

### Common VB6 population idiom (still produces 0-based):

```csharp
lAll = 1;  // VB6 vestige
while (!rst.EOF)
{
    arr[0, lAll - 1] = ...;  // actual index is 0-based due to lAll - 1
    lAll++;
}
```
Despite `lAll` starting at 1, the `- 1` makes storage 0-based.

---

## Rule 3: Fix UnboundColumnFetch handlers (grid data binding)

The .NET C1 TrueDBGrid's `UnboundColumnFetch` event fires **once per cell** (one column
at a time), not once per row. The VB6 `GridEx.UnboundReadData` event fired once per row
and received a `Values` array to fill all columns at once.

### Broken pattern (VBUC-migrated):

The migrated code treats the event as if it fires once per row and sets multiple columns:
```csharp
private void grid_UnboundColumnFetch(object eventSender, UnboundColumnFetchEventArgs eventArgs)
{
    var Values = eventSender as C1TrueDBGrid;
    var RowIndex = eventArgs.Row;
    // WRONG: sets ALL columns on every call, ignoring which column was requested
    Values[RowIndex, 1] = arr[1, RowIndex];
    Values[RowIndex, 2] = arr[2, RowIndex];
    Values[RowIndex, 3] = arr[3, RowIndex];
    // ...
}
```

### Correct pattern:

```csharp
private void grid_UnboundColumnFetch(object eventSender, UnboundColumnFetchEventArgs eventArgs)
{
    var RowIndex = eventArgs.Row;
    try
    {
        // GAP-Note: {author}. The UnboundColumnFetch fires once per cell.
        // Set only the requested cell via eventArgs.Value.
        eventArgs.Value = arr[eventArgs.Col, RowIndex].ToString();
    }
    catch
    {
        // existing error handling
    }
}
```

### Key points:

- `eventArgs.Row` is **0-based** in .NET TrueDBGrid
- `eventArgs.Col` is **0-based** in .NET TrueDBGrid and corresponds to the column being fetched
- Use `eventArgs.Value = ...` instead of `Values[row, col] = ...`
- When the source array is 0-based, `arr[eventArgs.Col, RowIndex]` maps directly
- Remove the `Values` variable — it is not needed in the corrected pattern
- The `.ToString()` call is generally safe; add null checks if the array can contain `DBNull` values

### Special case — arrays with computed column mapping:

If the grid columns do not map 1:1 to array columns (e.g., grid shows columns in a
different order, or skips some array columns), you cannot use `eventArgs.Col` directly.
Instead use a `switch` or `if` on `eventArgs.Col`:

```csharp
eventArgs.Value = eventArgs.Col switch
{
    0 => arr[1, RowIndex]?.ToString(),  // Grid col 0 shows array col 1
    1 => arr[3, RowIndex]?.ToString(),  // Grid col 1 shows array col 3
    _ => ""
};
```

### Special case — formatted output:

If the original code applied formatting (e.g., date formatting, percentage strings),
preserve that logic per column:

```csharp
eventArgs.Value = eventArgs.Col switch
{
    0 => DateTime.FromOADate((int)arr[0, RowIndex]).ToString("MM/dd/yyyy"),
    1 => $"{((double)arr[8, RowIndex] * 100)}%",
    _ => arr[eventArgs.Col, RowIndex]?.ToString()
};
```

---

## Rule 4: Fix row selection methods (`GetSelected*` patterns)

These methods read from the grid's current row to extract data from the backing array.

### Fix the row guard:

In VB6, row indices started at 1, so `> 0` meant "a row is selected". In .NET
TrueDBGrid, row 0 is the first data row (headers are separate).

```csharp
// BEFORE (broken — skips first row):
if (lCurrentRowIndex > 0)

// AFTER (correct — row 0 is valid):
// GAP-Note: {author}. index 0 is a valid row, in the truedbgrid the headers are managed separately.
if (lCurrentRowIndex >= 0)
```

### Fix column indices:

When the source array is 0-based, shift VB6 column indices down by 1:

```csharp
// BEFORE (VB6 1-based columns):
result = arrTransitModes[3, lCurrentRowIndex];           // Transit Mode Id
po_strName = arrTransitModes[2, lCurrentRowIndex].ToString(); // Description

// AFTER (0-based columns):
// GAP-Note: {author}. The array is 0 based.
result = (int) arrTransitModes[2, lCurrentRowIndex];           // Transit Mode Id
po_strName = arrTransitModes[1, lCurrentRowIndex].ToString();  // Description
```

Note: add explicit casts (e.g., `(int)`) when the array type is `object[,]` and the
target variable is a value type.

---

## Rule 5: Fix loops iterating over array rows

VB6 loops often start at 1 and use `<=` with the count variable. In .NET with 0-based
arrays, these must start at 0 and use `<`.

```csharp
// BEFORE (VB6-style 1-based loop):
int tempForEndVar = count;
for (i = 1; i <= tempForEndVar; i++)
{
    total += arr[4, i];
}

// AFTER (0-based loop):
// GAP-Note: {author}. The array is 0 based.
for (int i = 0; i < count; i++)
{
    total += arr[4, i];
}
```

### Watch for:
- The count variable itself should still represent the total number of elements
  (not the last index). Only the loop bounds change.
- If the loop body accesses specific columns by index, those column indices may
  also need to be shifted (see Rule 4).
- The `tempForEndVar` pattern is a VBUC artifact. Replace with direct use of the
  count variable when possible.

---

## Rule 6: Fix array type declarations and CastArray removal

### Type mismatch fix:

When the data object returns `object[,]` but the form declares the array as `int[,]`,
update the field type to match:

```csharp
// BEFORE (type mismatch — CastArray will fail or produce unexpected runtime behavior):
private int[, ] arrTransitModes = null;
// ...
arrTransitModes = ArraysHelper.CastArray<int[, ]>(
    oMarineMatrix.GetTransiteModesForMarinePolicy(...));

// AFTER (match source return type):
// GAP-Note: {author}. No need to cast, it should be an object array.
private object[, ] arrTransitModes = null;
// ...
arrTransitModes = oMarineMatrix.GetTransiteModesForMarinePolicy(...);
```

### When to remove CastArray:

Remove `ArraysHelper.CastArray<T>()` when:
- The source method already returns the exact type `T`
- You changed the field type to match the source return type

Keep `CastArray<T>()` when:
- The source returns a different type and the cast is genuinely needed
- The source returns `Array` (untyped) and you need `T[]` or `T[,]`

### When to keep CastArray but note the bounds issue:

If the source uses `Array.CreateInstance` with non-zero lower bounds, `CastArray`
preserves those bounds. Flag this per Rule 7 rather than removing `CastArray`.

---

## Rule 7: Handle arrays with non-zero lower bounds (Array.CreateInstance)

Some data object methods create arrays with non-standard lower bounds using:
```csharp
Array.CreateInstance(typeof(T), new int[]{ cols, rows }, new int[]{ 0, 1 })
```

This means `GetLowerBound(1) == 1` — row indices genuinely start at 1.

### DO NOT auto-fix these arrays.

Instead, generate a summary report for the user:

```
## Arrays with non-zero lower bounds — user decision required

### arrEndorsements
- **Source:** PD_PolicyEndorsement.GetEndorsementsForPolicy()
- **File:** DataObjects/PD_PolicyEndorsement.cs, line 559
- **Lower bounds:** {0, 1} (columns 0-based, rows 1-based)
- **Consumers in target file:**
  - GridEndorsements_UnboundColumnFetch: reads [6,RowIndex]...[1,RowIndex]
  - GetSelectedENDORSEMENT_DOCUMENT_ID: reads [6,lCurrentRowIndex], [7,lCurrentRowIndex]
  - PopulateEndorsements loop: `for (i = 1; i <= count; i++) { arr[4, i] }`
- **Options:**
  (A) Fix source method to use 0-based rows → then fix all consumers (safest)
  (B) Use GetLowerBound(1) at consumer sites for iteration
  (C) Leave as-is if current indices already match the 1-based rows
```

### How to identify these arrays:

1. Read the data object method that populates the array
2. Look for `Array.CreateInstance` with a `lowerBounds` parameter
3. Check if any `lowerBound` value is not 0
4. Also check if `ArraysHelper.CastArray` is wrapping such an array (it preserves bounds)

### Why not auto-fix:

Fixing these requires changes in **both** the data object (source) and all consumers
across potentially many files. The decision to fix at the source or adapt consumers has
architectural implications the user should weigh.

---

## Rule 8: Fix DBNull checks on array cells

VB6 code checking if a cell is null used 1-based column indices. Shift to 0-based:

```csharp
// BEFORE (1-based column):
if (Convert.IsDBNull(arrTransitModes[1, lCurrentRowIndex]))

// AFTER (0-based column):
// GAP-Note: {author}. The array index is 0 based.
if (Convert.IsDBNull(arrTransitModes[0, lCurrentRowIndex]))
```

This applies to all `Convert.IsDBNull(arr[col, row])` patterns where the array source
is 0-based (Pattern A). For arrays with non-zero lower bounds (Pattern B), defer to
Rule 7.

---

## Rule 9: Add GAP-Note comments

Mark every change with a `// GAP-Note:` comment explaining the fix. Use the format:

```
// GAP-Note: {author}. {brief reason}
```

### Standard reasons by rule:

| Rule | Comment text |
|------|-------------|
| Rule 3 | `The UnboundColumnFetch fires once per cell. Set only the requested cell via eventArgs.Value.` |
| Rule 4 (guard) | `index 0 is a valid row, in the truedbgrid the headers are managed separately.` |
| Rule 4 (index) | `The array is 0 based.` |
| Rule 5 | `The array is 0 based.` |
| Rule 6 | `No need to cast, it should be an object array.` |
| Rule 8 | `The array index is 0 based.` |

Replace `{author}` with the current developer's identifier.

---

## Canonical Example: frmPolicyMarine.cs

The file `Upgraded/ExcaliburEXE/frmPolicyMarine.cs` contains both **already-fixed** and
**still-broken** arrays, making it a useful reference.

### Already fixed (0-based source, consumers corrected):

**`arrTransitModes`** — `object[,]`, populated by `PD_PolicyMarineMatrix.GetTransiteModesForMarinePolicy()`
- Field type changed: `int[,]` → `object[,]` (Rule 6)
- CastArray removed (Rule 6)
- UnboundColumnFetch: uses `eventArgs.Value = arrTransitModes[eventArgs.Col, RowIndex]` (Rule 3)
- GetSelectedTRANSIT_MODE_ID: guard changed to `>= 0`, indices shifted `[3,x]→[2,x]` and `[2,x]→[1,x]` (Rule 4)
- SetMatrixButtons: DBNull check shifted `[1,x]→[0,x]` (Rule 8)

**`arrBCATransitModes`** — identical pattern, same fixes applied.

### Still needs fixing (0-based source, consumers use 1-based):

**`arrSpecialRates`** — `double[,]`, source: `PD_Special_Rate.GetSpecialRatesArray()` uses `new object[9, count]` (0-based)
- UnboundColumnFetch at line ~5440: still uses `Values[RowIndex, N] = arrSpecialRates[N, RowIndex]` pattern
- GetSelectedSPECIAL_RATE_ID at line ~5648: guard uses `> 0`, reads `arrSpecialRates[7, x]`

**`arrWarRates`** — `int[,]`, source: `PD_WarRate.GetWarRatesArray()` uses `new object[4, count]` (0-based)
- UnboundColumnFetch at line ~6110: uses `Values[RowIndex, N] = arrWarRates[N, RowIndex - 1]`
- Multiple update/delete handlers also access with various index patterns

**`arrCovTypes`** — `object[,]`, source: `PD_CovType.GetCovTypesArrayForPolicyType()` uses `new object[2, count]` (0-based)
- UnboundColumnFetch at line ~7996: uses `Values[RowIndex, N] = arrCovTypes[N, RowIndex]`

### Needs user decision (non-zero lower bounds):

**`arrEndorsements`** — `int[,]`, source: `PD_PolicyEndorsement.GetEndorsementsForPolicy()` uses
`Array.CreateInstance(typeof(string), new int[]{8, count}, new int[]{0, 1})` — rows 1-based
- CastArray preserves bounds, so column and row indices in consumers may already be correct for the 1-based rows
- Loop at line ~8777: `for (i = 1; i <= count; i++)` — may be correct if rows start at 1

**`arrInvoices`** — `object[,]`, source: `PD_BillingInvoiceData.GetInvoicesForPolicy()` uses
`Array.CreateInstance(typeof(object), new int[]{10, count}, new int[]{0, 1})` — rows 1-based
- Same situation: existing 1-based access may be intentionally matching the source bounds