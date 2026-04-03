---
id: backcolor_visual
title: Missing VB6 Cyan/Celeste BackColor on Controls
category: backcolor_visual
severity: medium
symptoms: [missing color, white control, cyan color, celeste, background color, BackColor, 192 255 255, visual mismatch]
applies_to: []
vb6_pattern: Input controls had &H00FFFF00& (cyan) background
dotnet_fix: Set BackColor = Color.FromArgb(192, 255, 255) in Designer.cs
---

## Problem

In VB6, input controls (TextBox, ComboBox, MaskedEdit) had a light cyan/celeste background
(`&H00FFFF00&`). The VBUC migration loses this BackColor on many controls, leaving them
with the default white background.

## Identification
Compare migrated form screenshot vs VB6 legacy screenshot:
- Controls that are cyan in VB6 but white in .NET
- Typically INPUT controls (TextBox, ComboBox, DateTimePicker)
- Labels and Frames do NOT get this color

## Fix

In the **Designer.cs**, add BackColor to affected controls:
```csharp
// GAP-Note. agente, BackColor celeste to replicate VB6 visual
this.txtControlName.BackColor = System.Drawing.Color.FromArgb(192, 255, 255);
```

## Exact Value
```csharp
Color.FromArgb(192, 255, 255)  // R=192, G=255, B=255 — light cyan/celeste
```

## Controls that typically get this color
- TextBox (data fields: name, date, number)
- ComboBox (dropdowns)
- MaskedEdit / DateTimePicker
- Numeric fields (fpc*, fpd*, fpl* prefixes)

## Controls that do NOT get this color
- Labels
- Frames / GroupBox
- Buttons
- Grids (have their own color scheme)
- Calculated/read-only fields (varies)

## Resolved Cases
- frmPolicyPropertyCasualty: txtEff_Date, fpcPS2_Per, cmbProduct_Type_ID, txtPolicy_Number
- frmInstallments: fpcTotalAmt, fpcFirstInsAmt, fpdEffDate, fpdInsSpreadDate
