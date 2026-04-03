---
name: fix-truedbgrid-unbound-columns
description: >
  Fixes broken VB6-to-C# migrated TrueDBGrid unbound column patterns in the Excalibur Modernized project. USE THIS SKILL whenever you encounter C# code (produced by VBUC) that uses C1TrueDBGrid's UnboundColumnFetch event with the old VB6 pattern: setting multiple columns per call via Values[RowIndex, N], using setRowCount (commented out), or missing dummy DataTable binding. Triggers on: UnboundColumnFetch, Values[RowIndex, N], setRowCount, C1TrueDBGrid, unbound columns, dummy DataTable, grid data binding, or when a user reports grid data not displaying or off-by-one errors in unbound columns.
---

# Skill: Fix TrueDBGrid Unbound Column Patterns (Excalibur Modernized)

## Context

In VB6, TrueDBGrid's UnboundReadData event fired once per row, passing a Values array to fill all columns at once. In .NET, C1TrueDBGrid's UnboundColumnFetch event fires once per cell. The VBUC migration tool often preserved the per-row logic, resulting in broken patterns: setting multiple columns per call, using Values[RowIndex, N], and failing to bind the grid with the correct number of rows. This causes missing data, off-by-one errors, and runtime exceptions.

---

## Rule 1: Discovery — Find all affected grids
- Search for UnboundColumnFetch event handlers.
- For each handler, identify: grid name, backing array, population method, any setRowCount calls (commented out), any GetSelected* or RowBookmark methods, any IsDBNull checks.
- Classify each grid:
  - **Simple**: grid columns map 1:1 to array columns, 0-based source array (auto-fixable)
  - **Remapped**: grid col N ≠ array col N (flag for manual review)
  - **Non-zero-bound**: source uses Array.CreateInstance with non-zero lowerBounds (flag for manual review)

---

## Rule 2: Fix array field type
- Change field type to object[,] if the data source returns object[,].
- Remove ArraysHelper.CastArray<T>() if the source already returns object[,].
- Example:
  ```csharp
  // BEFORE:
  private int[, ] arrTransitModes = null;
  arrTransitModes = ArraysHelper.CastArray<int[, ]>(oMarineMatrix.GetTransiteModesForMarinePolicy(...));
  // AFTER:
  // GAP-Note: jnunez. No need to cast, it should be an object array.
  private object[, ] arrTransitModes = null;
  arrTransitModes = oMarineMatrix.GetTransiteModesForMarinePolicy(...);
  ```

---

## Rule 3: Fix UnboundColumnFetch handler
- Replace all multi-column assignments (Values[RowIndex, N] = arr[N, RowIndex]) with:
  ```csharp
  // GAP-Note: jnunez. The UnboundColumnFetch fires once per cell. Set only the requested cell via eventArgs.Value.
  eventArgs.Value = arr[eventArgs.Col, RowIndex]?.ToString();
  ```
- Remove the Values variable and any per-row logic.
- Only apply to **Simple** grids (1:1 mapping, 0-based array).

---

## Rule 4: Add dummy DataTable binding
- Replace commented-out setRowCount() calls with:
  - Clear all grid.Columns[i].DataField = "";
  - Create a dummy DataTable with N rows (N = array row count).
  - Call grid.SetDataBinding(dummyTable, "", true);
- Example:
  ```csharp
  // GAP-Note: jnunez, This grid uses unbound columns to load data. We need to create a dummyTable to emulate the full unbound behavior.
  grid.Columns[0].DataField = "";
  grid.Columns[1].DataField = "";
  var dummyTable = new System.Data.DataTable();
  dummyTable.Columns.Add("DummyCol");
  for (int i = 0; i < rowCount; i++)
      dummyTable.Rows.Add(new object[] { null });
  grid.SetDataBinding(dummyTable, "", true);
  ```

---

## Rule 5: Fix RowBookmark guards
- Change `if (lCurrentRowIndex > 0)` to `if (lCurrentRowIndex >= 0)`.
- Example:
  ```csharp
  // BEFORE:
  if (lCurrentRowIndex > 0)
  // AFTER:
  // GAP-Note: jnunez. index 0 is a valid row, in the truedbgrid the headers are managed separately.
  if (lCurrentRowIndex >= 0)
  ```

---

## Rule 6: Fix array column indices
- Shift 1-based column indices down by 1 in GetSelected* methods and IsDBNull checks.
- Example:
  ```csharp
  // BEFORE:
  result = arrTransitModes[3, lCurrentRowIndex];
  // AFTER:
  // GAP-Note: jnunez. The array is 0 based.
  result = (int) arrTransitModes[2, lCurrentRowIndex];
  ```

---

## Rule 7: Handle special cases
- For **Remapped** or **Non-zero-bound** grids, generate a summary report for manual review. Do not auto-fix.
- Example: gexSpecialRates, GridEXLocations, GridEndorsements, gexCoverage, etc.

---

## Rule 8: Comment all changes
- Use `// GAP-Note: {author}.` prefix on every change.

---

## Canonical Example: frmPolicyMarine.cs
- See gexTransiteMode and gexBCATransitModes for the correct pattern.
- See PopulateTransitModes and PopulateBCATransitModes for dummy DataTable binding.

---

## Known Instances Inventory

### Auto-fixable (Simple, 0-based, 1:1 columns):
- gexBCAExGlobal (frmPolicyMarine.cs) — 1 column, 1D array
- gexBCAExInsCo (frmPolicyMarine.cs) — 1 column, 1D array
- gexBCAExPolicy (frmPolicyMarine.cs) — 1 column, 1D array
- gexCoverageTypes (frmPolicyMarine.cs) — 2 columns
- GridWriteOffs (dlgEndorsementBillingWizrd.cs) — 2 columns
- GridEXAccounts (dlgSelectPolicyType.cs) — 3 columns

### Flagged — Column remapping needed (grid col ≠ array col):
- gexSpecialRates (frmPolicyMarine.cs) — 9 grid cols, remapped
- gexWarRates (frmPolicyMarine.cs) — 3 cols, DateTime formatting + RowIndex-1 offset
- GridEXLocations (frmWarehouseLocations.cs) — 12 cols, heavy remapping
- GridEXMain (FrmMEGASweeper.cs) — 7 cols, loop-based
- GridEXCheck (FrmMEGASweeper.cs) — 6 cols, loop-based
- GridEXMain (frmMEGAPayor.cs) — 8 cols, loop-based
- GridEXCheck (frmMEGAPayor.cs) — 7 cols, loop-based

### Flagged — Non-zero lower bound source arrays:
- GridEndorsements (frmPolicyMarine.cs) — 6 cols, Array.CreateInstance with {0,1} bounds
- gexCoverage (frmPolicyMarine.cs) — 4 cols, Array.CreateInstance with {0,1} bounds

---

## Further Notes
- For single-column 1D arrays (gexBCAExGlobal/InsCo/Policy), use eventArgs.Value = ReflectionHelper.GetPrimitiveValue(arr[RowIndex - 1])
- For grids already data-bound (e.g., GridEXMain in FrmMEGASweeper), dummy DataTable may not be needed
- For loop-based handlers, document the structural fix (loop→single cell) as a sub-pattern, but flag for manual review