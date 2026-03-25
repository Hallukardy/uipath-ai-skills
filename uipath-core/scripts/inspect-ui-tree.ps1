<#
.SYNOPSIS
    Inspect the UI Automation tree of a Windows application for UiPath selector generation.

.DESCRIPTION
    Uses System.Windows.Automation (UIA) API to walk the element tree of a target window.
    Outputs hierarchical element data with properties that map directly to UiPath selectors.

    Features:
    - UWP app detection with AppId resolution via install path matching
    - Single-pass duplicate AutomationId and Name+ClassName detection with idx assignment
    - Smart window title wildcarding for document-based apps
    - ControlType-aware activity hints (ControlType-first, then pattern fallback)
    - Framework boundary markers (Win32/XAML/DirectUI transitions)
    - WinForms detection with structural overview (ClassName-based type inference)
    - Spatial Label-to-Edit association for WinForms (BoundingRectangle proximity)
    - Smart VERIFY_TYPE flagging (only for ambiguous toggle-like button names)
    - DataGrid/Table detection with collapsed output (summary instead of cells)
    - Type counts in summary for quick workflow planning
    - JSON output format for programmatic consumption

    WinForms Note:
      WinForms apps expose all elements as ControlType=Pane with no UIA patterns.
      UiPath uses a proprietary .NET bridge to read Control.Name (ctrlname/automationid).
      This script cannot access ctrlname - it provides structural layout with inferred
      control types from ClassName to help understand the app. Use UI Explorer for selectors.

    Flags:
      [!NO_AID]      - Missing AutomationId (selector will depend on name - locale fragile)
      [!NO_CLS]      - Missing ClassName (less selector specificity)
      [!DYNAMIC]     - Name contains dynamic content (numbers, dates, status text)
      [!DUP_AID]     - AutomationId is not unique among siblings (needs idx)
      [!DUP_NAME]    - Name+ClassName is not unique among siblings (needs idx)
      [!POS_AID]     - AutomationId is a positional index (unstable, changes with content)
      [!VERIFY_TYPE] - WinForms Button* could be CheckBox/RadioButton (verify in UI Explorer)
      [!EMPTY_FIELD] - Edit field with no current text value
      [!DISABLED]    - Element is not enabled (may need Wait for Element)

.PARAMETER WindowTitle
    Title (or wildcard pattern) of the target window.
.PARAMETER WindowClass
    ClassName of the target window (e.g., 'CabinetWClass', 'Notepad').
.PARAMETER ProcessName
    Process name to match (e.g., 'desktopapp.exe'). Supports wildcards.
.PARAMETER ScreenshotDir
    Optional directory path. When provided, captures a PNG screenshot of each interactive
    element's bounding rectangle and saves it to this directory. Filenames are auto-generated
    as NNN_controltype_name.png. Use with -OutputFormat json or selectors to get the filename
    mapped to each element. Intended for populating .screenshots/ in UiPath projects.
.PARAMETER MaxDepth
    Maximum tree depth to traverse. Default: 8.
.PARAMETER MaxElements
    Maximum number of elements to output. Default: 200.
.PARAMETER OutputFormat
    'tree' (indented hierarchy), 'flat' (pipe-delimited), 'selectors' (UiPath selector XML),
    or 'json' (structured JSON for programmatic consumption).
.EXAMPLE
    .\inspect-ui-tree.ps1 -WindowTitle "Calculator" -OutputFormat selectors
    .\inspect-ui-tree.ps1 -WindowTitle "*Notepad" -OutputFormat tree -MaxDepth 4
    .\inspect-ui-tree.ps1 -WindowClass "CabinetWClass" -OutputFormat flat
    .\inspect-ui-tree.ps1 -ProcessName "desktopapp.exe" -OutputFormat json
    .\inspect-ui-tree.ps1 -WindowTitle "Calculator" -OutputFormat json -ScreenshotDir "C:\MyProject\.screenshots"
#>
param(
    [string]$WindowTitle = "",
    [string]$WindowClass = "",
    [string]$ProcessName = "",
    [int]$MaxDepth = 8,
    [int]$MaxElements = 200,
    [ValidateSet("tree", "flat", "selectors", "json")]
    [string]$OutputFormat = "tree",
    [string]$ScreenshotDir = ""
)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

# ═══════════════════════════════════════════════════════════════════════════
# ELEMENT SCREENSHOT CAPTURE
# ═══════════════════════════════════════════════════════════════════════════

$script:screenshotEnabled = $false
if ($ScreenshotDir) {
    Add-Type -AssemblyName System.Drawing
    Add-Type -AssemblyName System.Windows.Forms
    if (-not (Test-Path $ScreenshotDir)) {
        New-Item -ItemType Directory -Path $ScreenshotDir -Force | Out-Null
    }
    $script:screenshotEnabled = $true
    $script:screenshotIndex = 0
}

function Save-ElementScreenshot {
    <#
    .SYNOPSIS
        Captures a screenshot of a UI element's bounding rectangle and saves it as PNG.
        Returns the filename (not full path) or empty string if capture fails/skipped.
    #>
    param(
        [System.Windows.Automation.AutomationElement]$Element,
        [string]$ControlType,
        [string]$Name,
        [string]$AutomationId
    )
    if (-not $script:screenshotEnabled) { return "" }

    # Only capture interactive elements that map to UiPath activities
    $interactiveTypes = @('Button','CheckBox','ComboBox','Edit','Hyperlink','ListItem',
        'MenuItem','RadioButton','Slider','Tab','TabItem','Text','ToggleButton',
        'TreeItem','DataGrid','Table','Document','SplitButton','MenuBar','ToolBar')
    if ($ControlType -notin $interactiveTypes) { return "" }

    try {
        $r = $Element.Current.BoundingRectangle
        if ($r.Width -le 0 -or $r.Height -le 0 -or $r.IsEmpty) { return "" }
        # Skip offscreen or absurdly large elements
        $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
        if ($r.X -lt -100 -or $r.Y -lt -100 -or $r.Width -gt $screen.Width -or $r.Height -gt $screen.Height) { return "" }

        # Build a sanitized filename: controltype_name-or-aid_index.png
        $label = if ($AutomationId) { $AutomationId } elseif ($Name) { $Name } else { "element" }
        # Sanitize: keep only alphanumeric, dash, underscore; truncate
        $label = ($label -replace '[^a-zA-Z0-9_\-]', '_') -replace '_+', '_'
        if ($label.Length -gt 40) { $label = $label.Substring(0, 40) }
        $script:screenshotIndex++
        $filename = "{0:D3}_{1}_{2}.png" -f $script:screenshotIndex, $ControlType.ToLower(), $label.ToLower().TrimEnd('_')

        $bmp = New-Object System.Drawing.Bitmap([int]$r.Width, [int]$r.Height)
        $gfx = [System.Drawing.Graphics]::FromImage($bmp)
        $gfx.CopyFromScreen([int]$r.X, [int]$r.Y, 0, 0, (New-Object System.Drawing.Size([int]$r.Width, [int]$r.Height)))
        $gfx.Dispose()
        $fullPath = Join-Path $ScreenshotDir $filename
        $bmp.Save($fullPath, [System.Drawing.Imaging.ImageFormat]::Png)
        $bmp.Dispose()
        return $filename
    } catch {
        return ""
    }
}
# FIND TARGET WINDOW
# ═══════════════════════════════════════════════════════════════════════════

$root = [System.Windows.Automation.AutomationElement]::RootElement
$targetWindow = $null
$allWindows = $root.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)

# Build a PID-to-process-name cache for -ProcessName matching
$procNameCache = @{}
if ($ProcessName) {
    foreach ($w in $allWindows) {
        $pid2 = $w.Current.ProcessId
        if (-not $procNameCache.ContainsKey($pid2)) {
            $p = Get-Process -Id $pid2 -ErrorAction SilentlyContinue
            $procNameCache[$pid2] = if ($p) { "$($p.ProcessName).exe" } else { "" }
        }
    }
}

foreach ($w in $allWindows) {
    $matchT = if ($WindowTitle) { $w.Current.Name -like $WindowTitle } else { $true }
    $matchC = if ($WindowClass) { $w.Current.ClassName -eq $WindowClass } else { $true }
    $matchP = if ($ProcessName) {
        $pn = $procNameCache[$w.Current.ProcessId]
        $pn -like $ProcessName
    } else { $true }
    if ($matchT -and $matchC -and $matchP) { $targetWindow = $w; break }
}
if (-not $targetWindow) {
    Write-Error "Window not found. Title='$WindowTitle' Class='$WindowClass' Process='$ProcessName'"
    Write-Output "Available windows:"
    foreach ($w in $allWindows) {
        $cn = $w.Current.ClassName; $nm = $w.Current.Name
        if ($nm -and $cn -notlike "Shell_*" -and $cn -ne "Progman") {
            $pid2 = $w.Current.ProcessId
            $pn = if ($procNameCache.ContainsKey($pid2)) { $procNameCache[$pid2] } else {
                $p = Get-Process -Id $pid2 -ErrorAction SilentlyContinue
                if ($p) { "$($p.ProcessName).exe" } else { "?" }
            }
            Write-Output "  Title='$nm' | Class='$cn' | Process='$pn'"
        }
    }
    exit 1
}

# ═══════════════════════════════════════════════════════════════════════════
# WINDOW INFO + UWP DETECTION
# ═══════════════════════════════════════════════════════════════════════════

$wc = $targetWindow.Current
$procId = $wc.ProcessId
$proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
$processName = if ($proc) { "$($proc.ProcessName).exe" } else { "unknown" }

$appId = ""; $isUwp = $false
if ($wc.ClassName -eq "ApplicationFrameWindow") {
    $xamlChild = $targetWindow.FindFirst(
        [System.Windows.Automation.TreeScope]::Children,
        (New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::ClassNameProperty, "Windows.UI.Core.CoreWindow")))
    if ($xamlChild) {
        $childPid = $xamlChild.Current.ProcessId
        $childProc = Get-Process -Id $childPid -ErrorAction SilentlyContinue
        if ($childProc) {
            $exePath = $childProc.MainModule.FileName
            $pkg = Get-AppxPackage | Where-Object { $exePath -like "$($_.InstallLocation)*" } | Select-Object -First 1
            if ($pkg) { $appId = "$($pkg.PackageFamilyName)!App"; $isUwp = $true }
        }
    }
}

$titleSel = $wc.Name
foreach ($sep in @(' - ', ' | ')) {
    if ($titleSel -match [regex]::Escape($sep)) {
        $appPart = ($titleSel -split [regex]::Escape($sep))[-1].Trim()
        $titleSel = "*$sep$appPart"; break
    }
}

Write-Output "=== UI TREE INSPECTION ==="
Write-Output ""
Write-Output "Window:"
Write-Output "  Title         = $($wc.Name)"
Write-Output "  ClassName     = $($wc.ClassName)"
Write-Output "  FrameworkId   = $($wc.FrameworkId)"
Write-Output "  ProcessName   = $processName"
if ($isUwp) { Write-Output "  UWP AppId     = $appId" }
Write-Output ""

# Detect WinForms framework
$isWinForms = ($wc.FrameworkId -eq 'WinForm') -or ($wc.ClassName -match '^WindowsForms10\.')

# Define wndSel early so it's available for both WinForms and standard paths
$wndSel = "<wnd app='$($processName.ToLower())' />"

if ($isWinForms) {
    Write-Output "  ** WinForms Detected **"
    Write-Output ""
    Write-Output "UiPath Selector Pattern (WinForms):"
    Write-Output "  <wnd app='$($processName.ToLower())' />"
    Write-Output "  <ctrl name='[element name]' role='[role]' />"
    Write-Output ""
    Write-Output "NOTE: For stable selectors with ctrlname/automationid, use UiPath UI Explorer."
    Write-Output "  This script generates <ctrl name='...' /> selectors from UIA Name property."
    Write-Output "  The structural overview shows control types and text values to help"
    Write-Output "  Claude understand the app layout and generate correct activity types."
    Write-Output ""
} else {
    $wndSel = "<wnd app='$($processName.ToLower())'"
    if ($appId) { $wndSel += " appid='$appId'" }
    $wndSel += " />"
    Write-Output "UiPath Window Selector:  $wndSel"
    if ($wc.ClassName -or $titleSel) {
        $extras = @()
        if ($wc.ClassName) { $extras += "cls='$($wc.ClassName)'" }
        if ($titleSel) { $extras += "title='$titleSel'" }
        Write-Output "  (add $($extras -join ' or ') only if multiple windows need disambiguation)"
    }
    Write-Output ""
}

# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

# Pattern detection using GetSupportedPatterns() - single call, no exceptions
$script:patIdMap = @{
    10000 = 'Invoke'
    10002 = 'Value'
    10003 = 'RangeValue'
    10004 = 'Scroll'
    10005 = 'ExpandCollapse'
    10006 = 'Grid'
    10007 = 'GridItem'
    10010 = 'SelectionItem'
    10012 = 'Table'
    10013 = 'TableItem'
    10014 = 'Text'
    10015 = 'Toggle'
    10017 = 'Window'
    10018 = 'Selection'
}

function Get-Pat {
    param([System.Windows.Automation.AutomationElement]$El)
    $supported = $El.GetSupportedPatterns()
    $result = @()
    foreach ($sp in $supported) {
        if ($script:patIdMap.ContainsKey($sp.Id)) {
            $result += $script:patIdMap[$sp.Id]
        }
    }
    return $result
}

# Tighter dynamic name detection - avoids false positives on version numbers,
# control identifiers, and embedded technical strings
function Test-Dynamic([string]$Name) {
    if (-not $Name) { return $false }
    # Calculator/app display values
    if ($Name -match '^Display is |^Expression is ') { return $true }
    # Status counters: "3 items", "42 characters", "Line 7"
    if ($Name -match '^\d+ item|^\d+ character|^Line \d') { return $true }
    # Dates: dd/mm/yyyy, yyyy-mm-dd, mm.dd.yyyy
    if ($Name -match '\d{1,4}[/\-\.]\d{1,2}[/\-\.]\d{2,4}') { return $true }
    # Timestamps: HH:MM or HH:MM:SS
    if ($Name -match '\d{1,2}:\d{2}(:\d{2})?') { return $true }
    # Phone numbers: sequences of digits with dashes/dots/spaces (7+ digits total)
    if ($Name -match '[\d][\d\-\.\s]{6,}[\d]') { return $true }
    # Pure numbers 3+ digits (but NOT short ones like "0" button on calculator)
    if ($Name -match '^\-?\d{3,}(\.\d+)?$') { return $true }
    # IDs/codes: alphanumeric with 4+ consecutive digits (order numbers, zip codes)
    if ($Name -match '[A-Za-z]*\d{4,}') { return $true }
    # Currency values
    if ($Name -match '[\$\u20AC\u00A3]\s*[\d,]+\.?\d*') { return $true }
    # Percentage values
    if ($Name -match '\d+\.?\d*\s*%') { return $true }
    return $false
}

function Get-ActivityHint {
    param([string[]]$Patterns, [string]$ControlType)
    # ControlType-first: some types have clear activity regardless of patterns
    switch ($ControlType) {
        'Edit'      { return "Type Into / Get Text" }
        'Document'  { return "Type Into / Get Text" }
        'Text'      {
            if ('Value' -in $Patterns) { return "Get Text" }
            if ('Text' -in $Patterns)  { return "Get Text / Get Full Text" }
            return "Get Text (Name attribute)"
        }
        'CheckBox'      { return "Check / Uncheck" }
        'RadioButton'   { return "Select Item" }
        'ComboBox'      { return "Select Item" }
        'ListItem'      { return "Select Item / Click" }
        'TabItem'       { return "Select Item" }
        'MenuItem'      { return "Click" }
        'Hyperlink'     { return "Click" }
        'SplitButton'   {
            if ('ExpandCollapse' -in $Patterns) { return "Click (expand/collapse)" }
            return "Click"
        }
        'Button' {
            if ('Toggle' -in $Patterns) { return "Check / Uncheck" }
            if ('ExpandCollapse' -in $Patterns) { return "Click (expand/collapse)" }
            return "Click"
        }
        'Slider'    { return "Set Range Value" }
        'Spinner'   { return "Set Value" }
        'ScrollBar' { return "" }
        'DataGrid'  { return "Extract Data / For Each Row" }
        'Table'     { return "Extract Data / For Each Row" }
        'DataItem'  { return "Get Row Item / Click" }
    }
    # Fallback: pattern-based for types not handled above
    if ('Value' -in $Patterns -and $ControlType -notin @('StatusBar','Header','List','Group','SplitButton','RadioButton')) { return "Type Into / Get Text" }
    if ('Toggle' -in $Patterns)         { return "Check / Uncheck" }
    if ('SelectionItem' -in $Patterns)  { return "Select Item" }
    if ('ExpandCollapse' -in $Patterns) { return "Click (expand/collapse)" }
    if ('Invoke' -in $Patterns)         { return "Click" }
    if ('Text' -in $Patterns)           { return "Get Text" }
    return ""
}

# ═══════════════════════════════════════════════════════════════════════════
# WINFORMS: Infer real control type from ClassName
# ═══════════════════════════════════════════════════════════════════════════

function Get-WinFormsControlType {
    param([string]$ClassName)
    if ($ClassName -match 'WindowsForms10\.([^.]+)\.') {
        switch ($matches[1]) {
            'EDIT'               { return 'Edit' }
            'BUTTON'             { return 'Button*' }
            'COMBOBOX'           { return 'ComboBox' }
            'STATIC'             { return 'Label' }
            'SysTabControl32'    { return 'TabControl' }
            'SysListView32'      { return 'ListView' }
            'SysTreeView32'      { return 'TreeView' }
            'SysHeader32'        { return 'ColumnHeader' }
            'msctls_trackbar32'  { return 'Slider' }
            'msctls_progress32'  { return 'ProgressBar' }
            'SysDateTimePick32'  { return 'DatePicker' }
            'SysMonthCal32'      { return 'MonthCalendar' }
            'RichEdit20W'        { return 'RichTextBox' }
            'SysAnimate32'       { return 'Animation' }
            'msctls_statusbar32' { return 'StatusBar' }
            'ToolbarWindow32'    { return 'ToolBar' }
            'SysIPAddress32'     { return 'IPAddress' }
            'Window'             { return 'Container' }
            default              { return $matches[1] }
        }
    }
    return 'Unknown'
}

function Get-WinFormsActivityHint {
    param([string]$InferredType, [string]$Name)
    switch ($InferredType) {
        'Edit'          { return "Type Into / Get Text" }
        'RichTextBox'   { return "Type Into / Get Text" }
        'Button*'       { return "Click (or Check/Select - verify type in UI Explorer)" }
        'ComboBox'      { return "Select Item" }
        'Label'         { return "Get Text (read-only)" }
        'TabControl'    { return "Click tab item" }
        'Slider'        { return "Set Range Value" }
        'DatePicker'    { return "Type Into / Select Date" }
        'ListView'      { return "Select Item / Get Row Item" }
        'TreeView'      { return "Select Item / Expand" }
        'ProgressBar'   { return "Get Value (read-only)" }
        'Container'     {
            if ($Name) { return "-- group: $Name" }
            return "-- container"
        }
        default         { return "" }
    }
}

# ═══════════════════════════════════════════════════════════════════════════
# MAIN TREE WALKER - Single-pass with inline duplicate detection per parent
# ═══════════════════════════════════════════════════════════════════════════

$script:count = 0
$script:typeCounts = @{}
$script:dupAidTotal = @{}
$script:dupNameTotal = @{}
$script:jsonElements = @()

function Inc-TypeCount([string]$t) {
    if ($script:typeCounts.ContainsKey($t)) { $script:typeCounts[$t]++ } else { $script:typeCounts[$t] = 1 }
}

function Walk-Tree {
    param(
        [System.Windows.Automation.AutomationElement]$El,
        [int]$D = 0
    )
    if ($D -gt $MaxDepth -or $script:count -ge $MaxElements) { return }

    # Fetch children once
    $children = $El.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
    $childList = @($children)

    # --- Inline duplicate detection for this parent's children ---
    $sibAids = @{}; $sibNames = @{}
    $ph = $El.GetHashCode()
    foreach ($ch in $childList) {
        $aid = $ch.Current.AutomationId
        $nm = $ch.Current.Name
        $cls = $ch.Current.ClassName
        if ($aid) {
            $k = "${ph}_${aid}"
            if ($sibAids.ContainsKey($k)) { $sibAids[$k]++ } else { $sibAids[$k] = 1 }
        } elseif ($nm) {
            $nk = "${ph}_${cls}_${nm}"
            if ($sibNames.ContainsKey($nk)) { $sibNames[$nk]++ } else { $sibNames[$nk] = 1 }
        }
    }
    # Build index counters for duplicates
    $aidIdx = @{}; $nameIdx = @{}
    foreach ($kv in $sibAids.GetEnumerator()) {
        if ($kv.Value -gt 1) {
            $aidIdx[$kv.Key] = 0
            $shortKey = ($kv.Key -split '_', 2)[1]
            if (-not $script:dupAidTotal.ContainsKey($shortKey)) {
                $script:dupAidTotal[$shortKey] = $kv.Value
            }
        }
    }
    foreach ($kv in $sibNames.GetEnumerator()) {
        if ($kv.Value -gt 1) {
            $nameIdx[$kv.Key] = 0
            if (-not $script:dupNameTotal.ContainsKey($kv.Key)) {
                $script:dupNameTotal[$kv.Key] = $kv.Value
            }
        }
    }

    # --- Process each child ---
    foreach ($ch in $childList) {
        if ($script:count -ge $MaxElements) { return }
        $c = $ch.Current
        $ct = $c.ControlType.ProgrammaticName -replace 'ControlType\.', ''

        # DataGrid/Table collapse: emit summary instead of recursing into every cell
        if ($ct -in @('DataGrid','Table') -and $D -ge 1) {
            $script:count++
            Inc-TypeCount $ct
            $dgChildren = $ch.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
            $dgList = @($dgChildren)
            $headerItems = @()
            $rowCount = 0
            foreach ($dgc in $dgList) {
                $dgct = $dgc.Current.ControlType.ProgrammaticName -replace 'ControlType\.', ''
                if ($dgct -in @('Header','HeaderItem')) {
                    $hChildren = $dgc.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
                    foreach ($hc in $hChildren) { $headerItems += $hc.Current.Name }
                } elseif ($dgct -in @('DataItem','Custom','ListItem')) {
                    $rowCount++
                }
            }
            $colCount = if ($headerItems.Count -gt 0) { $headerItems.Count } else { "?" }
            $gridName = if ($c.Name) { $c.Name } elseif ($c.AutomationId) { $c.AutomationId } else { $ct }

            switch ($OutputFormat) {
                "tree" {
                    $ind = "  " * $D
                    Write-Output "${ind}[$D] === $ct`: $gridName (rows=$rowCount, cols=$colCount) ==="
                    if ($headerItems.Count -gt 0) {
                        Write-Output "${ind}  Columns: $($headerItems -join ' | ')"
                    }
                    Write-Output "${ind}  -> Activity: Extract Data / For Each Row"
                }
                "flat" {
                    $r = $c.BoundingRectangle
                    Write-Output "$ct|$($c.Name)|$($c.AutomationId)|$($c.ClassName)|$($c.FrameworkId)|Grid|$([int]$r.X),$([int]$r.Y),$([int]$r.Width),$([int]$r.Height)||rows=$rowCount,cols=$colCount"
                }
                "selectors" {
                    $pts = @()
                    if ($c.AutomationId) { $pts += "automationid='$($c.AutomationId)'" }
                    if ($c.ClassName) { $pts += "cls='$($c.ClassName)'" }
                    if (-not $c.AutomationId -and $c.Name) { $pts += "name='$($c.Name)'" }
                    Write-Output ""
                    Write-Output "# === $ct`: $gridName (rows=$rowCount, cols=$colCount) ==="
                    if ($headerItems.Count -gt 0) {
                        Write-Output "# Columns: $($headerItems -join ' | ')"
                    }
                    Write-Output "$wndSel"
                    Write-Output "<uia $($pts -join ' ') />"
                    Write-Output "# Activity: Extract Data / For Each Row"
                    Write-Output "# Cell access: use tableRow/tableCol or Get Row Item activity"
                }
                "json" {
                    $script:jsonElements += @{
                        depth = $D; controlType = $ct; name = $c.Name
                        automationId = $c.AutomationId; className = $c.ClassName
                        frameworkId = $c.FrameworkId; isTable = $true
                        rows = $rowCount; columns = $colCount
                        columnHeaders = $headerItems
                        activityHint = "Extract Data / For Each Row"
                    }
                }
            }
            continue  # Skip recursion into table children
        }

        # --- Normal element processing ---
        $pats = Get-Pat -El $ch
        $isDyn = Test-Dynamic $c.Name
        $flags = @()
        if ([string]::IsNullOrEmpty($c.AutomationId)) { $flags += "NO_AID" }
        if ([string]::IsNullOrEmpty($c.ClassName))     { $flags += "NO_CLS" }
        if ($isDyn) { $flags += "DYNAMIC" }
        if (-not $c.IsEnabled) { $flags += "DISABLED" }
        # Numeric-only AutomationIds are positional indices
        if ($c.AutomationId -match '^\d+$' -and $ct -in @('ListItem','TabItem','TreeItem','DataItem')) { $flags += "POS_AID" }

        $idxVal = -1
        if ($c.AutomationId) {
            $dk = "${ph}_$($c.AutomationId)"
            if ($aidIdx.ContainsKey($dk)) {
                $flags += "DUP_AID"; $idxVal = $aidIdx[$dk]; $aidIdx[$dk]++
            }
        } elseif ($c.Name) {
            $nk = "${ph}_$($c.ClassName)_$($c.Name)"
            if ($nameIdx.ContainsKey($nk)) {
                $flags += "DUP_NAME"; $idxVal = $nameIdx[$nk]; $nameIdx[$nk]++
            }
        }

        $patStr = if ($pats.Count -gt 0) { $pats -join ',' } else { '-' }
        $flagStr = if ($flags.Count -gt 0) { " [!$($flags -join ',')]" } else { "" }
        $fwM = ""
        if ($D -le 2 -and $c.ClassName -eq 'Windows.UI.Core.CoreWindow' -and $c.FrameworkId -eq 'XAML') { $fwM = " << FW_BOUNDARY" }
        if ($D -le 2 -and $c.ClassName -eq 'Microsoft.UI.Content.DesktopChildSiteBridge') { $fwM = " << XAML_ISLAND" }
        if ($c.FrameworkId -eq 'DirectUI' -and $D -le 3) { $fwM = " << DirectUI" }
        $script:count++
        Inc-TypeCount $ct

        # Capture element screenshot if enabled
        $ssFile = Save-ElementScreenshot -Element $ch -ControlType $ct -Name $c.Name -AutomationId $c.AutomationId

        switch ($OutputFormat) {
            "tree" {
                $ind = "  " * $D
                $is = if ($idxVal -ge 0) { " idx=$idxVal" } else { "" }
                $ssNote = if ($ssFile) { " [screenshot=$ssFile]" } else { "" }
                Write-Output "${ind}[$D] $ct | Name='$($c.Name)' | AId='$($c.AutomationId)' | Cls='$($c.ClassName)' | FwId='$($c.FrameworkId)' | Pat=$patStr$is$flagStr$fwM$ssNote"
            }
            "flat" {
                $r = $c.BoundingRectangle
                $is = if ($idxVal -ge 0) { $idxVal } else { "" }
                Write-Output "$ct|$($c.Name)|$($c.AutomationId)|$($c.ClassName)|$($c.FrameworkId)|$patStr|$([int]$r.X),$([int]$r.Y),$([int]$r.Width),$([int]$r.Height)|$is|$($flags -join ',')"
            }
            "selectors" {
                $act = $pats | Where-Object { $_ -in @('Invoke','Value','Toggle','SelectionItem','ExpandCollapse','Text') }
                if ($act -and $ct -notin @('Pane','Window','Group','Custom','Image')) {
                    $pts = @()
                    if ($c.AutomationId -and "NO_AID" -notin $flags) { $pts += "automationid='$($c.AutomationId)'" }
                    if ($c.ClassName) { $pts += "cls='$($c.ClassName)'" }
                    $needN = (-not $c.AutomationId) -or ("DUP_AID" -in $flags) -or $isDyn
                    if ($c.Name -and $needN) {
                        $nv = if ($isDyn) { $c.Name -replace '\d+', '*' } else { $c.Name }
                        $pts += "name='$nv'"
                    }
                    $rm = @{ 'Text'='text'; 'Edit'='edit'; 'Document'='document'; 'MenuItem'='menuitem'; 'TabItem'='tabitem'; 'ListItem'='listitem'; 'CheckBox'='checkbox' }
                    $addR = (-not $c.AutomationId) -or ($ct -in @('Text','Edit','Document'))
                    if ($rm.ContainsKey($ct) -and $addR) { $pts += "role='$($rm[$ct])'" }
                    if ($idxVal -ge 0) { $pts += "idx='$idxVal'" }
                    if ($pts.Count -eq 0) { return }
                    $ah = Get-ActivityHint -Patterns $pats -ControlType $ct
                    Write-Output ""
                    Write-Output "# $($c.Name) ($ct)$flagStr"
                    Write-Output "$wndSel"
                    Write-Output "<uia $($pts -join ' ') />"
                    if ($ah) { Write-Output "# Activity: $ah" }
                    if ($ssFile) { Write-Output "# Screenshot: $ssFile" }
                }
            }
            "json" {
                $r = $c.BoundingRectangle
                $ah = Get-ActivityHint -Patterns $pats -ControlType $ct
                $idxOut = $null; if ($idxVal -ge 0) { $idxOut = $idxVal }
                $script:jsonElements += @{
                    depth = $D; controlType = $ct
                    name = $c.Name; automationId = $c.AutomationId
                    className = $c.ClassName; frameworkId = $c.FrameworkId
                    patterns = $pats; flags = $flags
                    isEnabled = [bool]$c.IsEnabled
                    idx = $idxOut
                    rect = @{ x = $(try{[int]$r.X}catch{0}); y = $(try{[int]$r.Y}catch{0}); w = $(try{[int]$r.Width}catch{0}); h = $(try{[int]$r.Height}catch{0}) }
                    activityHint = $ah
                    screenshot = $ssFile
                }
            }
        }

        # Recurse into children
        Walk-Tree -El $ch -D ($D + 1)
    }
}

# ═══════════════════════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════════════════════

if ($isWinForms) {
    $script:count = 0

    function Walk-WinForms {
        param([System.Windows.Automation.AutomationElement]$El, [int]$D = 0)
        if ($D -gt $MaxDepth -or $script:count -ge $MaxElements) { return }

        # Pre-fetch children for sibling-aware processing
        $children = $El.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
        $childList = @($children)

        # Build label index for spatial matching (Label->Edit association)
        $sibLabels = @()
        foreach ($sib in $childList) {
            $st = Get-WinFormsControlType $sib.Current.ClassName
            if ($st -eq 'Label' -and $sib.Current.Name) {
                $sr = $sib.Current.BoundingRectangle
                $sibLabels += @{ Name = ($sib.Current.Name -replace ':$', ''); X = [int]$sr.X; Y = [int]$sr.Y; R = [int]($sr.X + $sr.Width); B = [int]($sr.Y + $sr.Height) }
            }
        }

        for ($ci = 0; $ci -lt $childList.Count; $ci++) {
            if ($script:count -ge $MaxElements) { return }
            $ch = $childList[$ci]
            $c = $ch.Current
            $infType = Get-WinFormsControlType $c.ClassName
            $isDyn = Test-Dynamic $c.Name
            $hint = Get-WinFormsActivityHint $infType $c.Name
            $script:count++
            Inc-TypeCount $infType

            $ind = "  " * ($D + 1)
            $nameStr = if ($c.Name) { "'$($c.Name)'" } else { "(empty)" }
            $flags = @()
            if ($isDyn) { $flags += "DYNAMIC" }
            if (-not $c.Name -and $infType -eq 'Edit') { $flags += "EMPTY_FIELD" }
            if (-not $c.IsEnabled) { $flags += "DISABLED" }

            # Smart VERIFY_TYPE - only flag truly ambiguous buttons
            if ($infType -eq 'Button*') {
                $togglePatterns = '(?i)^(on|off|yes|no|enabled?|disabled?|active|inactive|male|female|show|hide)$'
                if (-not $c.Name -or $c.Name -match $togglePatterns) {
                    $flags += "VERIFY_TYPE"
                }
            }

            # Spatial Label->Edit/ComboBox association using BoundingRectangle
            $nearLabel = ""
            if ($infType -in @('Edit','ComboBox','RichTextBox') -and $sibLabels.Count -gt 0) {
                $er = $c.BoundingRectangle
                $eX = [int]$er.X; $eY = [int]$er.Y
                $bestDist = [int]::MaxValue; $bestLabel = ""
                foreach ($lbl in $sibLabels) {
                    $yDiff = [Math]::Abs($lbl.Y - $eY)
                    if ($yDiff -le 15 -and $lbl.R -le $eX) {
                        $dist = $eX - $lbl.R
                        if ($dist -lt $bestDist) { $bestDist = $dist; $bestLabel = $lbl.Name }
                    }
                }
                # Fallback: label directly above (within 30px X tolerance)
                if (-not $bestLabel) {
                    $bestDist = [int]::MaxValue
                    foreach ($lbl in $sibLabels) {
                        $xDiff = [Math]::Abs($lbl.X - $eX)
                        if ($xDiff -le 30 -and $lbl.B -le $eY) {
                            $dist = $eY - $lbl.B
                            if ($dist -lt $bestDist) { $bestDist = $dist; $bestLabel = $lbl.Name }
                        }
                    }
                }
                $nearLabel = $bestLabel
            }
            $nearStr = if ($nearLabel) { " (near: '$nearLabel')" } else { "" }

            $flagStr = if ($flags) { " [!$($flags -join ',')]" } else { "" }
            if ($infType -eq 'Button*' -and 'VERIFY_TYPE' -notin $flags) { $hint = "Click" }
            $hintStr = if ($hint -and $hint -notlike "-- *") { " -> $hint" } else { "" }

            switch ($OutputFormat) {
                "tree" {
                    if ($infType -eq 'Container' -and $c.Name) {
                        Write-Output "${ind}[$($D+1)] === $($c.Name) ==="
                    } elseif ($infType -eq 'Container') {
                        Write-Output "${ind}[$($D+1)] --- container ---"
                    } elseif ($infType -eq 'Label') {
                        Write-Output "${ind}[$($D+1)] Label: $nameStr$flagStr"
                    } else {
                        Write-Output "${ind}[$($D+1)] $infType $nameStr$nearStr$hintStr$flagStr"
                    }
                }
                "flat" {
                    $r = $c.BoundingRectangle
                    $nearCol = if ($nearLabel) { $nearLabel } else { "" }
                    Write-Output "$($D+1)|$infType|$($c.Name)|$($c.ClassName -replace '\.app\.0\.[a-f0-9]+$', '.*')|$([int]$r.X),$([int]$r.Y),$([int]$r.Width),$([int]$r.Height)|$nearCol|$($flags -join ',')"
                }
                "selectors" {
                    # Only emit selectors for actionable types
                    if ($infType -notin @('Label', 'Container', 'Unknown', 'StatusBar', 'ToolBar')) {
                        # Build <ctrl> selector attributes
                        $pts = @()

                        # Use nearLabel as name if element name is empty/dynamic, else use element name
                        $selectorName = $null
                        if ($nearLabel -and (-not $c.Name -or $isDyn)) {
                            $selectorName = $nearLabel
                        } elseif ($c.Name -and -not $isDyn) {
                            $selectorName = $c.Name
                        }

                        if ($selectorName) { $pts += "name='$selectorName'" }

                        # Map WinForms inferred type to UIA role
                        $roleMap = @{
                            'Edit'          = 'editable text'
                            'RichTextBox'   = 'editable text'
                            'Button*'       = 'push button'
                            'ComboBox'      = 'combo box'
                            'TabControl'    = 'tab item'
                            'CheckBox'      = 'check box'
                            'RadioButton'   = 'radio button'
                            'ListView'      = 'list'
                            'TreeView'      = 'tree'
                            'Slider'        = 'slider'
                            'DatePicker'    = 'editable text'
                            'NumericUpDown' = 'spinner'
                        }
                        $role = $roleMap[$infType]
                        if ($role) { $pts += "role='$role'" }

                        if ($pts.Count -gt 0) {
                            $ah = Get-WinFormsActivityHint $infType $c.Name
                            Write-Output ""
                            Write-Output "# $nameStr ($infType)$flagStr"
                            Write-Output "$wndSel"
                            Write-Output "<ctrl $($pts -join ' ') />"
                            if ($ah) { Write-Output "# Activity: $ah" }
                        }
                    }
                }
                "json" {
                    $r = $c.BoundingRectangle
                    $script:jsonElements += @{
                        depth = ($D + 1); controlType = $infType
                        name = $c.Name; className = ($c.ClassName -replace '\.app\.0\.[a-f0-9]+$', '.*')
                        nearLabel = $nearLabel; activityHint = $hint
                        flags = $flags; isEnabled = [bool]$c.IsEnabled
                        rect = @{ x = $(try{[int]$r.X}catch{0}); y = $(try{[int]$r.Y}catch{0}); w = $(try{[int]$r.Width}catch{0}); h = $(try{[int]$r.Height}catch{0}) }
                    }
                }
            }

            Walk-WinForms -El $ch -D ($D + 1)
        }
    }

    # Handle root element
    $rc = $targetWindow.Current
    $rootType = Get-WinFormsControlType $rc.ClassName
    Inc-TypeCount $rootType
    $script:count++

    switch ($OutputFormat) {
        "tree" {
            if ($rootType -eq 'Container' -and $rc.Name) {
                Write-Output "[0] === $($rc.Name) ==="
            } else {
                Write-Output "[0] --- container ---"
            }
        }
        "flat" {
            Write-Output "# Depth|InferredType|Name|ClassPattern|Rect|NearLabel|Flags"
            $r = $rc.BoundingRectangle
            Write-Output "0|$rootType|$($rc.Name)|$($rc.ClassName -replace '\.app\.0\.[a-f0-9]+$', '.*')|$([int]$r.X),$([int]$r.Y),$([int]$r.Width),$([int]$r.Height)||"
        }
        "json" {
            $script:jsonElements += @{
                depth = 0; controlType = $rootType; name = $rc.Name
                className = ($rc.ClassName -replace '\.app\.0\.[a-f0-9]+$', '.*')
                isRoot = $true
            }
        }
    }

    Walk-WinForms -El $targetWindow -D 0

    if ($OutputFormat -eq "json") {
        @{
            window = @{ title = $wc.Name; className = $wc.ClassName; frameworkId = "WinForm"; processName = $processName }
            framework = "WinForms"
            selectorStrategy = "ctrl with name attribute"
            totalElements = $script:count
            typeCounts = $script:typeCounts
            elements = $script:jsonElements
        } | ConvertTo-Json -Depth 5
    } else {
        Write-Output ""
        Write-Output "=== Summary ==="
        Write-Output "Total elements: $($script:count) (max: $MaxElements, depth: $MaxDepth)"
        Write-Output "Framework: WinForms (.NET)"
        $tcStr = ($script:typeCounts.GetEnumerator() | Sort-Object Value -Descending | ForEach-Object { "$($_.Key):$($_.Value)" }) -join ', '
        Write-Output "Controls: $tcStr"
        Write-Output "Selector strategy: <ctrl name='...' role='...' /> (from UIA Name property)"
        Write-Output "  - For ctrlname/automationid selectors, use UiPath UI Explorer"
        Write-Output "  - Use <nav up='N' /> anchors for elements near labeled controls"
    }

} else {
    # ═══════════════════════════════════════════════════════════════════════
    # Standard UIA path (UWP, WPF, Win32, DirectUI)
    # ═══════════════════════════════════════════════════════════════════════

    Write-Output "Scanning..."

    if ($OutputFormat -eq "flat") { Write-Output "# Type|Name|AutomationId|ClassName|FrameworkId|Patterns|Rect|Idx|Flags" }
    Walk-Tree -El $targetWindow -D 0

    if ($OutputFormat -eq "json") {
        @{
            window = @{
                title = $wc.Name; className = $wc.ClassName
                frameworkId = $wc.FrameworkId; processName = $processName
                isUwp = $isUwp; appId = $appId
                selectorTitle = $titleSel
            }
            windowSelector = $wndSel
            totalElements = $script:count
            maxElements = $MaxElements; maxDepth = $MaxDepth
            typeCounts = $script:typeCounts
            duplicateAutomationIds = $script:dupAidTotal
            duplicateNames = $script:dupNameTotal
            elements = $script:jsonElements
        } | ConvertTo-Json -Depth 5
    } else {
        Write-Output ""
        Write-Output "=== Summary ==="
        Write-Output "Total elements: $($script:count) (max: $MaxElements, depth: $MaxDepth)"
        if ($script:dupAidTotal.Count -gt 0) {
            Write-Output "Duplicate AutomationIds:"
            foreach ($kv in $script:dupAidTotal.GetEnumerator()) {
                Write-Output "  '$($kv.Key)' x$($kv.Value) (needs idx)"
            }
        }
        if ($script:dupNameTotal.Count -gt 0) {
            Write-Output "Duplicate Names (no AutomationId):"
            foreach ($kv in $script:dupNameTotal.GetEnumerator()) {
                $nparts = $kv.Key -split '_', 3
                if ($nparts.Count -ge 3) {
                    Write-Output "  '$($nparts[2])' cls=$($nparts[1]) x$($kv.Value) (needs idx)"
                }
            }
        }
    }
}
