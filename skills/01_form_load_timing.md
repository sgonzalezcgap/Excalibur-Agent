---
id: form_load_timing
title: Form_Load Timing — CreateInstance Premature Execution
category: form_load_timing
severity: critical
symptoms: [Form_Load crash, NullReferenceException on load, controls not initialized, grid empty on open, Form_Load in CreateInstance, data not available in Form_Load]
applies_to: []
vb6_pattern: Form_Load fires when form is shown (Show/ShowDialog)
dotnet_fix: Override OnLoad or use Load event delegate
---

## Problem

VBUC migrates VB6's `Form_Load` by placing it inside `CreateInstance()` in the Designer.cs:

```csharp
// Designer.cs — BUGGY CODE
public static FrmXxx CreateInstance()
{
    FrmXxx theInstance = new FrmXxx();
    theInstance.Form_Load();  // ← Executes BEFORE ShowDialog
    return theInstance;
}
```

In VB6, `Form_Load` fires when the form is displayed. In .NET, `CreateInstance()` is called
when accessing `DefInstance`, which happens **before** `SetScreenMode()`, `SetCustomer()`, etc.

## Root Cause
```
Caller code:
  FrmXxx.DefInstance.SetScreenMode(mode);  // 1. DefInstance → CreateInstance() → Form_Load()
  FrmXxx.DefInstance.ShowDialog();          // 2. Too late — Form_Load already ran
```

## Fix Pattern A: OnLoad Override (Preferred)

In the **.cs** file:
```csharp
// GAP-Note. agente, Form_Load moved to OnLoad to execute after ShowDialog
protected override void OnLoad(EventArgs e)
{
    base.OnLoad(e);
    Form_Load();
}
```

In the **Designer.cs**, comment out the call:
```csharp
public static FrmXxx CreateInstance()
{
    FrmXxx theInstance = new FrmXxx();
    // GAP-Note. agente, Removed Form_Load from CreateInstance — now runs via OnLoad
    // theInstance.Form_Load();
    return theInstance;
}
```

## Fix Pattern B: Load Event Delegate

If Form_Load already has `(object sender, EventArgs e)` signature:
```csharp
// In InitializeComponent(), at the end:
this.Load += Form_Load;
```

## Resolved Cases
- frmInstallments: Form_Load crashed because wnScreenMode was not set yet
- frmBondBilling: Same timing issue — data not available at Form_Load time
- FrmCustomerDetail: Fixed by jnunez with the same pattern
