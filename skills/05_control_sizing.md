---
id: control_sizing
title: Text Clipped — Control Too Small
category: control_sizing
severity: medium
symptoms: [text clipped, text cut off, truncated, label too small, checkbox text cut, not fully visible]
applies_to: []
vb6_pattern: VB6 controls auto-sized or had different font metrics
dotnet_fix: Increase Size and/or MinimumSize in Designer.cs
---

## Problem

During VB6→.NET migration, some controls (Label, CheckBox, RadioButton) end up too small
to display their full text, especially when:
- Text has multiple lines
- Font size differs between VB6 and .NET
- AutoSize=false with a fixed Size that's too small

## Fix

In **Designer.cs**, increase `Size` and optionally `MinimumSize`:
```csharp
// GAP-Note. agente, Size increased to prevent text clipping
this.Label4.Size = new System.Drawing.Size(353, 45);  // was (353, 25)
this.Label4.MinimumSize = new System.Drawing.Size(353, 45);
```

For CheckBox with long text:
```csharp
// GAP-Note. agente, Size and Location adjusted for full text display
this.chkOption.Size = new System.Drawing.Size(210, 24);  // was (185, 17)
this.chkOption.Location = new System.Drawing.Point(120, 76);  // adjust Y if overlapping
```

## Resolved Cases
- frmInvoiceCorrectionWizard: Label4 (353×25 → 353×45), chkUseProRatingFactor (185×17 → 210×24)
