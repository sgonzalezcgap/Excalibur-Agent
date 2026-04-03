---
id: commandbutton_image
title: Button Image Invisible — CommandButtonHelper.SetMaskColor
category: commandbutton_image
severity: high
symptoms: [button no image, button blank, icon invisible, SetMaskColor, Silver, commandButtonHelper, empty button]
applies_to: []
vb6_pattern: CommandButton with Picture property and MaskColor
dotnet_fix: Remove commandButtonHelper calls for the affected button
---

## Problem

The VBUC migration generates a `commandButtonHelper` that calls `SetMaskColor(Color.Silver)`.
This treats the color Silver as transparent, making small icons (16×16) invisible against
the gray button background, especially when the button is disabled.

## Symptoms
- Button appears empty/blank (no visible image)
- Button has an Image assigned in properties but nothing shows
- Designer.cs contains `commandButtonHelper1.SetMaskColor(button, Color.Silver)`

## Fix

### Step 1: Remove commandButtonHelper calls for the affected button
In **Designer.cs**, find and remove/comment:
```csharp
// REMOVE these lines for the affected button:
// this.commandButtonHelper1.SetStyle(this.pbUndo, 1);
// this.commandButtonHelper1.SetMaskColor(this.pbUndo, Color.Silver);
// this.commandButtonHelper1.SetCorrectEventsBehavior(this.pbUndo, true);
```

### Step 2: Set UseVisualStyleBackColor
```csharp
// GAP-Note. agente, Removed commandButtonHelper — icon now visible
this.pbUndo.UseVisualStyleBackColor = true;
```

### Step 3: Adjust size if oversized
Migrated buttons often have excessive size (74×44). Reduce to ~49×41.

## Resolved Cases
- frmInstallments: pbUndo, cmbClose, cmbSaveExit — removed commandButtonHelper
