---
id: treeview_migration
title: TreeView SelectedNodes and ImageList Migration
category: treeview_migration
severity: high
symptoms: [SelectedNodes, TreeView error, tree node selection, tree no icons, ImageList missing, ImageIndex]
applies_to: []
vb6_pattern: TreeView had SelectedNodes collection and ImageList for icons
dotnet_fix: Use SelectedNode (singular) and configure ImageList properly
---

## Problem: SelectedNodes
VB6 TreeView had `SelectedNodes` (collection). .NET WinForms TreeView only has
`SelectedNode` (singular).

### Fix
```csharp
// BEFORE (bug):
var node = treeView.SelectedNodes[0];

// AFTER:
// GAP-Note. agente, SelectedNodes does not exist in .NET — use SelectedNode
var node = treeView.SelectedNode;
```

## Problem: Missing Icons
VB6 TreeView loaded icons from an ImageList. Migration may lose the association.

### Fix
```csharp
// In Designer.cs:
this.ImageList2 = new System.Windows.Forms.ImageList(this.components);
this.ImageList2.Images.Add("KEY_PLUS", /* resource */);
this.treeView.ImageList = this.ImageList2;

// When creating nodes:
node.ImageKey = "KEY_PLUS";
node.SelectedImageKey = "KEY_PLUS";
```

## Resolved Cases
- FrmBranchDetail: SelectedNodes → SelectedNode, ImageList2 for icons
