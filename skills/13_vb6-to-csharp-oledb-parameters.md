
SKILL.md

Page
1
/
1
100%
---
name: vb6-to-csharp-oledb-parameters
description: >
  Fixes broken auto-migrated VB6-to-C# stored procedure calls in the Excalibur Modernized project.
  USE THIS SKILL whenever you encounter C# code (produced by VBUC) that accesses DbCommand.Parameters
  by numeric index (e.g., comStProc.Parameters[1].Value = ...) without first adding those parameters
  to the collection — this pattern compiles but crashes at runtime. The skill teaches how to replace
  the entire index-based setup block with a typed List<OleParametersHelper.ParameterSpec> registered
  via OleParametersHelper.AddAndSetOleDbParameters(). Trigger on any of: Parameters[N].Value assignment
  blocks, "missing OleDbParameters" gap comments, stored-procedure methods in migrated DataObjects
  or BusinessLogic classes, or when a user reports a runtime error on DbCommand.Parameters access.
---

# VB6-to-C# OleDb Parameters Migration

## Project Context

This project is a VB6-to-C# migration (Excalibur Modernized). VB6 ADO stored-procedure calls
auto-migrated by the VBUC tool land in C# as index-based parameter assignments:

```csharp
comStProc.Parameters[1].Value = someValue;
comStProc.Parameters[2].Value = anotherValue;
// ...
comStProc.ExecuteNonQuery();
```

This code **compiles silently but fails at runtime** because `DbCommand.Parameters` is an empty
collection — nobody ever added the parameters. VBUC simply translated the VB6 ordinal index style
without emitting the corresponding `Parameters.Add(...)` calls.

## The Helper Class

Before applying this skill, **read the helper file** to understand the available API:

```
UpgradeSupport\UpgradeHelpers.DB.Essentials\OleParametersHelper.cs
```

This file defines:
- `OleParametersHelper.ParameterSpec` — a DTO with fields: `Name`, `OleDbType`, `DbType` (nullable),
  `Direction` (defaults to `Input`), `Value`, `Size` (nullable).
- `OleParametersHelper.AddAndSetOleDbParameters(DbCommand command, List<ParameterSpec> specs)` —
  creates `OleDbParameter` instances from the specs and adds them to the command's Parameters collection.

## What To Do

When you find a stored-procedure method using the broken index-based pattern:

### Step 1 — Identify the parameters

Scan the entire block of `comStProc.Parameters[N].Value = ...` assignments. Note:
- The `comStProc.CommandText` value — this tells you which stored procedure is being called.
- The total parameter count (highest index + 1, counting from 0).
- Any parameters whose index is **read after** `ExecuteNonQuery()` — those are output/return parameters.
- Any parameters assigned out of numeric order (VBUC sometimes scrambles this) — reorder them to
  SP declaration order when building the spec list.

### Step 2 — Build the `List<ParameterSpec>`

Replace the index assignments with a typed list. Always add a `//GAP-Note: Adding missing OleDbParameters in aStoredProc` comment immediately before the `var specs = ...` line to mark this as a reviewed gap fix.

```csharp
//GAP-Note: Adding missing OleDbParameters in aStoredProc
var specs = new List<OleParametersHelper.ParameterSpec>
{
    // index 0 is always the return value / output ID
    new OleParametersHelper.ParameterSpec { Name = "@RETURN_VALUE", Direction = ParameterDirection.ReturnValue, OleDbType = OleDbType.Integer, Value = null },
    // remaining parameters in SP declaration order
    new OleParametersHelper.ParameterSpec { Name = "ParamName", OleDbType = OleDbType.VarChar, Value = ... },
    // ...
};

OleParametersHelper.AddAndSetOleDbParameters(comStProc, specs);
```

### Step 3 — Leave the post-execution block alone

Do **not** change any `comStProc.Parameters[N].Value` reads that appear **after** `ExecuteNonQuery()`.
Those indexes remain valid once the collection has been populated by `AddAndSetOleDbParameters`.

### Step 4 — Add missing `using` directives

Ensure the file has **all four** of these at the top if they are not already present:
```csharp
using System.Collections.Generic;
using System.Data;
using System.Data.OleDb;
using UpgradeHelpers.DB;
```

- `System.Collections.Generic` — required for `List<>`
- `System.Data` — required for `ParameterDirection` (Input, Output, ReturnValue, etc.)
- `System.Data.OleDb` — required for `OleDbType`
- `UpgradeHelpers.DB` — required for `OleParametersHelper` and `OleParametersHelper.ParameterSpec`

Without `using UpgradeHelpers.DB;` and `using System.Data;` the compiler will report
`OleParametersHelper`, `ParameterSpec`, and `ParameterDirection` as undefined types.

---

## OleDbType Mapping Rules

Infer `OleDbType` from the field name and original value expression:

| Pattern / Naming convention | OleDbType |
|---|---|
| `_ID`, `_Id`, count fields, integer booleans | `OleDbType.Integer` |
| String fields with `Substring(0, Min(N, ...))` | `OleDbType.VarChar` (variable) or `OleDbType.Char` (fixed-width, e.g. Office_Code, Port_Code) |
| `_DT`, `Date`, `EffDate` | `OleDbType.Date` |
| Premium, Amount, Comm, Rate, Decimal money | `OleDbType.Decimal` |
| Small flag fields (`TinyInt` pattern, 0/1 values with byte semantics) | `OleDbType.TinyInt` |
| `CORRECT_BY` and similar single-byte flags | `OleDbType.TinyInt` |

When in doubt, check the original VB6 source comments (they are often preserved inline as `//`
comments after each assignment, e.g. `//Account_NO`, `//Invoice_Amount`) — these can help confirm
both the name and intended type.

---

## Null-Guard Value Patterns

Preserve the original null-guard logic exactly; just add the appropriate type conversion:

**Nullable decimal / money fields (use DBNull when null, not zero):**
```csharp
Value = (Object.Equals(m_itField, null) || string.IsNullOrEmpty(m_itField?.ToString()))
        ? DBNull.Value
        : Convert.ToDecimal(m_itField)
```

**Nullable Nullable<T> value types (e.g. `int?`, `double?`):**
```csharp
Value = (m_itField is null) ? DBNull.Value : m_itField.Value
// or with conversion:
Value = (m_itField is null) ? (object) DBNull.Value : (object) Convert.ToInt32(m_itField.Value)
```

**Fields that default to 0 instead of null (e.g. Profit_Sharing_Amount, MGA_COMMISSION):**
```csharp
Value = (Object.Equals(m_itField, null) || string.IsNullOrEmpty(m_itField?.ToString()))
        ? ((object) 0)
        : Convert.ToDecimal(m_itField)
```

**Date fields that can be null:**
```csharp
Value = (Object.Equals(m_itField, null)) ? (object) DBNull.Value : (object) Convert.ToDateTime(m_itField)
```

**Integer/ID fields that can be null:**
```csharp
Value = (Object.Equals(m_itField, null)) ? (object) DBNull.Value : m_itField
```

---

## Parameter Direction Rules

| Situation | Direction |
|---|---|
| Index 0 / return value from SP | `ParameterDirection.ReturnValue` |
| Parameter read back after ExecuteNonQuery AND written before | `ParameterDirection.InputOutput` |
| Parameter only read back after ExecuteNonQuery, not set | `ParameterDirection.Output` |
| Everything else | `ParameterDirection.Input` (default, can be omitted) |

### Always include `@RETURN_VALUE` — even when the SP has no explicit RETURN

SQL Server always emits an integer exit code from every stored procedure, whether or not it
contains an explicit `RETURN` statement. OleDb always reserves position 0 for this value, and
VBUC generates input assignments starting at `Parameters[1]` for exactly this reason.

The rule is: **if the original broken code starts inputs at `Parameters[1]`, always add
`@RETURN_VALUE` first at position 0.** Omitting it shifts all inputs one slot down, breaking the
positional indexes used in the post-execution block (`comStProc.Parameters[0].Value`, etc.).

The only exception is VBUC code where inputs genuinely start at `Parameters[0]` — rare, and would
indicate the original VB6 code was not using the return value slot at all.

---

## Declaration Order

VBUC sometimes emits assignments out of order (e.g., assigns index 34 before index 32). When
building the `ParameterSpec` list, parameters must be in the stored procedure's **declaration
order** (ascending by the original index number), because `AddAndSetOleDbParameters` appends
them sequentially and the post-execution block addresses them by the resulting positional index.

---

## Scenario Example

### Before — broken auto-migrated pattern

```csharp
comStProc.CommandText = "up_InsertBillingInvoice_BondBilling";

//UPGRADE_WARNING: (2080) IsEmpty was upgraded to a comparison ...
comStProc.Parameters[1].Value = ((Object.Equals(m_itAccount_NO, null)) ? "" : ReflectionHelper.GetPrimitiveValue<string>(m_itAccount_NO)).Substring(0, Math.Min(25, ((Object.Equals(m_itAccount_NO, null)) ? "" : ReflectionHelper.GetPrimitiveValue<string>(m_itAccount_NO)).Length)); //Account_NO
comStProc.Parameters[2].Value = ((Object.Equals(m_itBar_Code, null)) ? "" : ReflectionHelper.GetPrimitiveValue<string>(m_itBar_Code)).Substring(0, Math.Min(50, ((Object.Equals(m_itBar_Code, null)) ? "" : ReflectionHelper.GetPrimitiveValue<string>(m_itBar_Code)).Length)); //Bar_Code
comStProc.Parameters[3].Value = m_itBill_DT; //Bill_DT
// ... many more index assignments, possibly out of order ...
comStProc.Parameters[31].Value = ReflectionHelper.GetPrimitiveValue(m_itMGA_COMMISSION);
comStProc.Parameters[34].Value = (psProducerOverwrite) ? 1 : 0;   // note: out of order
comStProc.Parameters[32].Value = (m_itProducer_Comm_Owned.Equals(0)) ? 0 : m_itProducer_Comm_Owned;

UpgradeHelpers.DB.TransactionManager.SetCommandTransaction(comStProc);
comStProc.ExecuteNonQuery();

// Post-execution reads — leave these unchanged:
po_lngInvoiceNo = Convert.ToInt32(comStProc.Parameters[0].Value);
if (po_lngInvoiceNo != 0)
{
    result = true;
    m_itINVOICE_NO = po_lngInvoiceNo;
    m_itProducer_Comm_Owned = Convert.ToDouble(comStProc.Parameters[32].Value);
    m_itPRODUCER_ID = comStProc.Parameters[33].Value;
}
```

### After — correct pattern using OleParametersHelper

```csharp
comStProc.CommandText = "up_InsertBillingInvoice_BondBilling";

//GAP-Note: Adding missing OleDbParameters in aStoredProc
var specs = new List<OleParametersHelper.ParameterSpec>
{
    new OleParametersHelper.ParameterSpec { Name = "@RETURN_VALUE", Direction = ParameterDirection.ReturnValue, OleDbType = OleDbType.Integer, Value = null },
    new OleParametersHelper.ParameterSpec { Name = "Account_NO", OleDbType = OleDbType.VarChar, Value = ((Object.Equals(m_itAccount_NO, null)) ? "" : ReflectionHelper.GetPrimitiveValue<string>(m_itAccount_NO)).Substring(0, Math.Min(25, ((Object.Equals(m_itAccount_NO, null)) ? "" : ReflectionHelper.GetPrimitiveValue<string>(m_itAccount_NO)).Length)) },
    new OleParametersHelper.ParameterSpec { Name = "Bar_Code", OleDbType = OleDbType.VarChar, Value = ((Object.Equals(m_itBar_Code, null)) ? "" : ReflectionHelper.GetPrimitiveValue<string>(m_itBar_Code)).Substring(0, Math.Min(50, ((Object.Equals(m_itBar_Code, null)) ? "" : ReflectionHelper.GetPrimitiveValue<string>(m_itBar_Code)).Length)) },
    new OleParametersHelper.ParameterSpec { Name = "Bill_DT", OleDbType = OleDbType.Date, Value = m_itBill_DT },
    new OleParametersHelper.ParameterSpec { Name = "Bond_Serial_NO", OleDbType = OleDbType.Char, Value = ((Object.Equals(m_itBond_Serial_NO, null)) ? "" : ReflectionHelper.GetPrimitiveValue<string>(m_itBond_Serial_NO)).Substring(0, Math.Min(20, ((Object.Equals(m_itBond_Serial_NO, null)) ? "" : ReflectionHelper.GetPrimitiveValue<string>(m_itBond_Serial_NO)).Length)) },
    new OleParametersHelper.ParameterSpec { Name = "Branch_ID", OleDbType = OleDbType.Integer, Value = m_itBRANCH_ID },
    new OleParametersHelper.ParameterSpec { Name = "Customer_Id", OleDbType = OleDbType.Integer, Value = m_itCustomer_ID },
    new OleParametersHelper.ParameterSpec { Name = "Description", OleDbType = OleDbType.VarChar, Value = ((Object.Equals(m_itDESCRIPTION, null)) ? "" : ReflectionHelper.GetPrimitiveValue<string>(m_itDESCRIPTION)).Substring(0, Math.Min(50, ((Object.Equals(m_itDESCRIPTION, null)) ? "" : ReflectionHelper.GetPrimitiveValue<string>(m_itDESCRIPTION)).Length)) },
    new OleParametersHelper.ParameterSpec { Name = "Form_Serial_NO", OleDbType = OleDbType.VarChar, Value = ((Object.Equals(m_itForm_Serial_NO, null)) ? "" : ReflectionHelper.GetPrimitiveValue<string>(m_itForm_Serial_NO)).Substring(0, Math.Min(20, ((Object.Equals(m_itForm_Serial_NO, null)) ? "" : ReflectionHelper.GetPrimitiveValue<string>(m_itForm_Serial_NO)).Length)) },
    new OleParametersHelper.ParameterSpec { Name = "Grand_Total_Premium", OleDbType = OleDbType.Decimal, Value = (Object.Equals(m_itGrand_Total_Premium, null) || string.IsNullOrEmpty(m_itGrand_Total_Premium?.ToString())) ? DBNull.Value : Convert.ToDecimal(m_itGrand_Total_Premium) },
    new OleParametersHelper.ParameterSpec { Name = "Insurance_Company_ID", OleDbType = OleDbType.Integer, Value = m_itInsurance_Company_ID },
    new OleParametersHelper.ParameterSpec { Name = "Invoice_Amount", OleDbType = OleDbType.Decimal, Value = (Object.Equals(m_itInvoice_Amount, null) || string.IsNullOrEmpty(m_itInvoice_Amount?.ToString())) ? DBNull.Value : Convert.ToDecimal(m_itInvoice_Amount) },
    new OleParametersHelper.ParameterSpec { Name = "Invoice_Type_ID", OleDbType = OleDbType.Integer, Value = m_itInvoice_Type_ID },
    new OleParametersHelper.ParameterSpec { Name = "Limit", OleDbType = OleDbType.Decimal, Value = (Object.Equals(m_itLimit, null) || string.IsNullOrEmpty(m_itLimit?.ToString())) ? DBNull.Value : Convert.ToDecimal(m_itLimit) },
    new OleParametersHelper.ParameterSpec { Name = "Net_Premium", OleDbType = OleDbType.Decimal, Value = (Object.Equals(m_itNet_Premium, null) || string.IsNullOrEmpty(m_itNet_Premium?.ToString())) ? DBNull.Value : Convert.ToDecimal(m_itNet_Premium) },
    new OleParametersHelper.ParameterSpec { Name = "Net_Worth_Discount", OleDbType = OleDbType.Decimal, Value = (Object.Equals(m_itNet_Worth_Discount, null) || string.IsNullOrEmpty(m_itNet_Worth_Discount?.ToString())) ? (object) DBNull.Value : (object) Convert.ToDecimal(m_itNet_Worth_Discount) },
    new OleParametersHelper.ParameterSpec { Name = "Office_Code", OleDbType = OleDbType.Char, Value = m_itOffice_Code.Substring(0, Math.Min(10, m_itOffice_Code.Length)) },
    new OleParametersHelper.ParameterSpec { Name = "Office_Id", OleDbType = OleDbType.Integer, Value = m_itOffice_ID },
    new OleParametersHelper.ParameterSpec { Name = "PolEffDate", OleDbType = OleDbType.Date, Value = (Object.Equals(m_itPolEffDate, null)) ? (object) DBNull.Value : (object) Convert.ToDateTime(m_itPolEffDate) },
    new OleParametersHelper.ParameterSpec { Name = "Policy_Number", OleDbType = OleDbType.VarChar, Value = ((Object.Equals(m_itPolicy_Number, null)) ? "" : ReflectionHelper.GetPrimitiveValue<string>(m_itPolicy_Number)).Substring(0, Math.Min(20, ((Object.Equals(m_itPolicy_Number, null)) ? "" : ReflectionHelper.GetPrimitiveValue<string>(m_itPolicy_Number)).Length)) },
    new OleParametersHelper.ParameterSpec { Name = "Port_Code", OleDbType = OleDbType.Char, Value = ((Object.Equals(m_itPort_Code, null)) ? "" : ReflectionHelper.GetPrimitiveValue<string>(m_itPort_Code)).Substring(0, Math.Min(18, ((Object.Equals(m_itPort_Code, null)) ? "" : ReflectionHelper.GetPrimitiveValue<string>(m_itPort_Code)).Length)) },
    new OleParametersHelper.ParameterSpec { Name = "Principal", OleDbType = OleDbType.VarChar, Value = ((Object.Equals(m_itPrincipal, null)) ? "" : ReflectionHelper.GetPrimitiveValue<string>(m_itPrincipal).Substring(0, Math.Min(30, ReflectionHelper.GetPrimitiveValue<string>(m_itPrincipal).Length))).Substring(0, Math.Min(30, ((Object.Equals(m_itPrincipal, null)) ? "" : ReflectionHelper.GetPrimitiveValue<string>(m_itPrincipal).Substring(0, Math.Min(30, ReflectionHelper.GetPrimitiveValue<string>(m_itPrincipal).Length))).Length)) },
    new OleParametersHelper.ParameterSpec { Name = "Product_Type_ID", OleDbType = OleDbType.Integer, Value = m_itProduct_Type_ID },
    new OleParametersHelper.ParameterSpec { Name = "Profit_Sharing_Amount", OleDbType = OleDbType.Decimal, Value = (Object.Equals(m_itProfit_Sharing_Amount, null) || string.IsNullOrEmpty(m_itProfit_Sharing_Amount?.ToString())) ? ((object) 0) : Convert.ToDecimal(m_itProfit_Sharing_Amount) },
    new OleParametersHelper.ParameterSpec { Name = "Profit_Sharing_Amount2", OleDbType = OleDbType.Decimal, Value = (Object.Equals(m_itProfit_Sharing_Amount2, null) || string.IsNullOrEmpty(m_itProfit_Sharing_Amount2?.ToString())) ? ((object) 0) : Convert.ToDecimal(m_itProfit_Sharing_Amount2) },
    new OleParametersHelper.ParameterSpec { Name = "Ref_NO", OleDbType = OleDbType.VarChar, Value = ((Object.Equals(m_itREF_NO, null)) ? "" : ReflectionHelper.GetPrimitiveValue<string>(m_itREF_NO)).Substring(0, Math.Min(50, ((Object.Equals(m_itREF_NO, null)) ? "" : ReflectionHelper.GetPrimitiveValue<string>(m_itREF_NO)).Length)) },
    new OleParametersHelper.ParameterSpec { Name = "Total_Comm", OleDbType = OleDbType.Decimal, Value = (Object.Equals(m_itTotal_Comm, null) || string.IsNullOrEmpty(m_itTotal_Comm?.ToString())) ? DBNull.Value : Convert.ToDecimal(m_itTotal_Comm) },
    new OleParametersHelper.ParameterSpec { Name = "Producer_Id", OleDbType = OleDbType.Integer, Value = (Object.Equals(m_itPRODUCER_ID, null)) ? (object) DBNull.Value : m_itPRODUCER_ID },
    new OleParametersHelper.ParameterSpec { Name = "CORRECT_BY", OleDbType = OleDbType.TinyInt, Value = (Object.Equals(m_itCORRECT_BY, null)) ? DBNull.Value : m_itCORRECT_BY },
    new OleParametersHelper.ParameterSpec { Name = "Calculate_Rate_When_Renewing", OleDbType = OleDbType.Char, Value = m_itCalculate_Rate_When_Renewing },
    new OleParametersHelper.ParameterSpec { Name = "Renewal_Status_ID", OleDbType = OleDbType.Integer, Value = m_itRenewal_Status_ID },
    new OleParametersHelper.ParameterSpec { Name = "MGA_COMMISSION", OleDbType = OleDbType.Decimal, Value = (Object.Equals(m_itMGA_COMMISSION, null) || string.IsNullOrEmpty(m_itMGA_COMMISSION?.ToString())) ? ((object) 0) : Convert.ToDecimal(m_itMGA_COMMISSION) },
    new OleParametersHelper.ParameterSpec { Name = "Producer_Comm_Owned", OleDbType = OleDbType.Decimal, Direction = ParameterDirection.InputOutput, Value = (m_itProducer_Comm_Owned.Equals(0)) ? 0 : Convert.ToDecimal(m_itProducer_Comm_Owned) },
    new OleParametersHelper.ParameterSpec { Name = "poProducer_ID_Out", OleDbType = OleDbType.Decimal, Direction = ParameterDirection.Output, Value = DBNull.Value },
    new OleParametersHelper.ParameterSpec { Name = "psProducerOverwrite", OleDbType = OleDbType.Integer, Value = (psProducerOverwrite) ? 1 : 0 },
    new OleParametersHelper.ParameterSpec { Name = "BILLINGPROCESS_ID", OleDbType = OleDbType.Integer, Value = (m_itBILLINGPROCESS_ID.Equals(0)) ? 0 : m_itBILLINGPROCESS_ID },
    new OleParametersHelper.ParameterSpec { Name = "Renewal_Fee_Amount", OleDbType = OleDbType.Decimal, Value = (Object.Equals(m_itRenewal_Fee_Amount, null) || string.IsNullOrEmpty(m_itRenewal_Fee_Amount?.ToString())) ? (object) DBNull.Value : (object) Convert.ToDecimal(m_itRenewal_Fee_Amount) },
    new OleParametersHelper.ParameterSpec { Name = "FEE_AMOUNT", OleDbType = OleDbType.Decimal, Value = (Object.Equals(m_itFEE_AMOUNT, null) || string.IsNullOrEmpty(m_itFEE_AMOUNT.Value?.ToString())) ? (object) DBNull.Value : (object) Convert.ToDecimal(m_itFEE_AMOUNT.Value) },
    new OleParametersHelper.ParameterSpec { Name = "FEE_INSURANCE_COMPANY_ID", OleDbType = OleDbType.Integer, Value = (Object.Equals(m_itFEE_INSURANCE_COMPANY_ID, null) || string.IsNullOrEmpty(m_itFEE_INSURANCE_COMPANY_ID.Value?.ToString())) ? (object) DBNull.Value : (object) Convert.ToInt32(m_itFEE_INSURANCE_COMPANY_ID.Value) },
    new OleParametersHelper.ParameterSpec { Name = "OLD_INVOICE_NO", OleDbType = OleDbType.Integer, Value = (Object.Equals(m_itOLD_INVOICE_NO, null)) ? (object) DBNull.Value : (object) m_itOLD_INVOICE_NO },
    new OleParametersHelper.ParameterSpec { Name = "FEE_DESCRIPTION", OleDbType = OleDbType.VarChar, Value = m_itFEE_DESCRIPTION },
    new OleParametersHelper.ParameterSpec { Name = "BOND_ACCOUNT_ID", OleDbType = OleDbType.Integer, Value = (ReflectionHelper.GetPrimitiveValue<int>(m_itBOND_ACCOUNT_ID) <= 0) ? DBNull.Value : m_itBOND_ACCOUNT_ID }
};

OleParametersHelper.AddAndSetOleDbParameters(comStProc, specs);

UpgradeHelpers.DB.TransactionManager.SetCommandTransaction(comStProc);
comStProc.ExecuteNonQuery();

// Post-execution reads — unchanged:
po_lngInvoiceNo = Convert.ToInt32(comStProc.Parameters[0].Value);
if (po_lngInvoiceNo != 0)
{
    result = true;
    m_itINVOICE_NO = po_lngInvoiceNo;
    m_itProducer_Comm_Owned = Convert.ToDouble(comStProc.Parameters[32].Value);
    m_itPRODUCER_ID = comStProc.Parameters[33].Value;
}
```
Displaying SKILL.md.