# App Integrations

Excel Classic Workbook (ReadRange, WriteRange, WriteCell), Email/Integration Service (GetIMAPMailMessages, SendMail, SaveMailAttachments), PDF (ReadPDFText, ReadPDFWithOCR, native+OCR fallback), Database (DatabaseConnect, ExecuteQuery, ExecuteNonQuery), Screenshot (TakeScreenshot, SaveImage).

## Contents
  - [Read Range (Workbook)](#read-range-workbook)
  - [Write Range (Workbook)](#write-range-workbook)
  - [Common Excel Pattern — Read, Process, Write](#common-excel-pattern-read-process-write)
  - [Write Cell (Workbook)](#write-cell-workbook)
- [Email Activities (Integration Service)](#email-activities-integration-service)
  - [Get IMAP Mail Messages (GetIMAPMailMessages)](#get-imap-mail-messages-getimailmessages)
  - [For Each Email (loop pattern)](#for-each-email-loop-pattern)
  - [Send Mail (SendMail)](#send-mail-sendmail)
  - [MailMessage Properties (in expressions)](#mailmessage-properties-in-expressions)
  - [Save Mail Attachments (SaveMailAttachments)](#save-mail-attachments-savemailattachments)
- [PDF Activities](#pdf-activities)
  - [Read PDF Text (native/digital PDFs)](#read-pdf-text-nativedigital-pdfs)
  - [Read PDF With OCR (scanned/image PDFs)](#read-pdf-with-ocr-scannedimage-pdfs)
  - [Common PDF Pattern — Native + OCR Fallback](#common-pdf-pattern-native-+-ocr-fallback)
- [Database Activities](#database-activities)
  - [DatabaseConnect](#databaseconnect)
  - [ExecuteQuery (SELECT → DataTable)](#executequery-select-datatable)
  - [ExecuteNonQuery (INSERT/UPDATE/DELETE)](#executenonquery-insertupdatedelete)
- [Screenshot Activities](#screenshot-activities)
  - [TakeScreenshot + SaveImage](#takescreenshot-saveimage)
- [Modern UI Automation (uix: namespace)](#modern-ui-automation-uix-namespace)


These are the classic workbook activities (`ui:` namespace) — they work without Excel installed, operating directly on .xlsx files. For Modern Excel activities (UseExcelFile), see separate section below.

### Read Range (Workbook)
→ **Use `gen_read_range()`** — generates correct XAML deterministically.

Properties:
- `WorkbookPath` — VB.NET expression for file path: `[str_ExcelFilePath]` or `["C:\path\file.xlsx"]`
- `SheetName` — VB.NET expression: `[str_Sheet]` or `["Sheet1"]`
- `Range="{x:Null}"` — reads entire sheet. Or specify range: `Range="A1:D100"`
- `AddHeaders="True"` — first row becomes column names in DataTable
- `DataTable="[dt_Output]"` — output DataTable variable
- `WorkbookPathResource="{x:Null}"` — no linked resource file

### Write Range (Workbook)
→ **Use `gen_write_range()`** — generates correct XAML deterministically.

Properties:
- `WorkbookPath` — output file path. Creates file if it doesn't exist
- `SheetName` — can be literal string `"Sheet1"` or VB expression `[str_Sheet]`
- `StartingCell="{x:Null}"` — writes from A1. Or specify: `StartingCell="B2"`
- `DataTable="[dt_Input]"` — DataTable to write

### Common Excel Pattern — Read, Process, Write

**Bulk write (preferred for performance):** Read → process into DataTable → WriteRange once.
→ **Use `gen_read_range()` + processing logic + `gen_write_range()`** — generates correct XAML deterministically.


**Per-cell write (simpler but slower):** WriteCell inside a loop. Opens/closes file each call — avoid for large datasets. Use AddDataRow + WriteRange instead.

### Write Cell (Workbook)
→ **Use `gen_write_cell()`** — generates correct XAML deterministically.

Properties:
- `Cell` — VB.NET expression for cell address. Dynamic: `[&quot;F&quot;+intRow.ToString]` builds "F2", "F3", etc. Static: `"A1"`
- `Text` — value to write (VB.NET expression)
- `SheetName` — target sheet name (literal string)
- `WorkbookPath` — path to the workbook (VB.NET expression)
- **Performance note:** Each WriteCell call opens and closes the file. For writing multiple cells per row, prefer building a DataRow and using AddDataRow + a single WriteRange at the end

## Email Activities (Integration Service)

Requires `UiPath.Mail.Activities` package. Uses Orchestrator Integration Service connections — no Outlook Desktop dependency. The generators handle all required xmlns declarations (`umae:`, `umame:`, `usau:`, `snm:`) automatically.

**⚠️ Do NOT use Outlook-specific activities:** `OutlookApplicationCard`, `ForEachEmailX`, `GetOutlookMailMessages`, `MoveOutlookMessage`, `SendOutlookMailMessage`. These require Outlook Desktop installed and are not portable. Use `ui:SendMail` (SMTP via Integration Service) instead of `SendOutlookMailMessage`.

### Get IMAP Mail Messages (GetIMAPMailMessages)

Retrieves emails via Integration Service IMAP connection. Works with any email provider (Gmail, Outlook 365, Exchange) configured in Orchestrator Integration Service. Supports folder access, server-side filtering, and unread/read state.

→ **Use `gen_get_imap_mail()`** — generates correct XAML deterministically.

Properties:
- `Messages` — OutArgument receiving `List(MailMessage)`
- `ConnectionMode="IntegrationService"` + `UseISConnection="True"` — Orchestrator Integration Service connection (no hardcoded credentials)
- `MailFolder` — IMAP folder name (e.g. `"Inbox"`, `"Sent"`, `"Archive"`)
- `Top` — max number of emails to retrieve
- `OnlyUnreadMessages` — filter to unread only
- `OrderByDate` — `"NewestFirst"` or `"OldestFirst"`
- `FilterExpression` — IMAP search filter (e.g. `"SUBJECT \"Invoice\""`, `"FROM \"noreply@example.com\""`)
- `FilterExpressionCharacterSet` — `"US-ASCII"` (default)
- `SecureConnection` — `"Auto"`, `"SSL"`, or `"None"`
- The `ConnectionDetailsBackupSlot` block is required boilerplate for Integration Service mode

### For Each Email (loop pattern)

Use `ui:ForEach` with `TypeArguments="snm:MailMessage"` to iterate the retrieved mail list. Requires `xmlns:snm="clr-namespace:System.Net.Mail;assembly=System.Net.Mail"`.

→ **Use `gen_foreach()`** with `item_type="snm:MailMessage"` — generates correct XAML deterministically.

Notes:
- The delegate variable name (`currentMailMessage`) is used in expressions inside the loop
- `Values` points to the `List(MailMessage)` output from GetIMAPMailMessages
- This is a standard `ui:ForEach` with typed argument — same pattern works for any `List(T)`

### Send Mail (SendMail)

Sends email via Integration Service SMTP connection.

→ **Use `gen_send_mail()`** — generates correct XAML deterministically.

Properties:
- `To`, `Cc`, `Bcc` — recipient addresses (comma-separated for multiple)
- `Subject`, `Body` — email content
- `IsBodyHtml` — set True for HTML body
- `ResourceAttachments` — `String[]` array of file paths to attach
- `AttachmentInputMode="Existing"` — attach files from disk
- `ConnectionMode="IntegrationService"` + `UseISConnection="True"` — Integration Service connection
- The `AttachmentsBackup`, `ConnectionDetailsBackupSlot`, and `Files` child elements are required boilerplate

Additional namespace for SendMail attachments:
```
xmlns:umame="clr-namespace:UiPath.MicrosoftOffice365.Activities.Mail.Enums;assembly=UiPath.Mail.Activities"
```

### MailMessage Properties (in expressions)
```vb
CurrentMail.Subject                    ' Email subject line
CurrentMail.Body                       ' Email body (HTML if HTML email)
CurrentMail.From.Address               ' Sender email address
CurrentMail.From.DisplayName           ' Sender display name
CurrentMail.To(0).Address              ' First recipient
CurrentMail.CC                         ' CC recipients collection
CurrentMail.Attachments(0).Name        ' First attachment filename
CurrentMail.Headers("Date")            ' Email date header
CurrentMail.IsBodyHtml                 ' Boolean
```

### Save Mail Attachments (SaveMailAttachments)
Saves email attachments to disk in a single activity. **Use this instead of manual InvokeCode with FileStream.**
→ **Use `gen_save_mail_attachments()`** — generates correct XAML deterministically.

Variable for Attachments output: type `scg:IEnumerable(x:String)`, name `list_Attachments`. Declare in the JSON spec `variables` array with type `"scg:IEnumerable(x:String)"`.
Properties:
- `Message` — the MailMessage to extract attachments from (e.g. `[in_mmMail]`)
- `FolderPath` — destination folder path
- `Filter` — wildcard filter: `"*.pdf"`, `"*.xlsx"`, `"*.*"` (all). Leave empty or `"*.*"` for all attachments
- `Attachments` — (optional) output receiving saved file paths. **⚠️ Type is `IEnumerable(x:String)`, NOT `List(String)`.**
- `ExcludeInlineAttachments` — skip embedded images (usually False)
- `OverwriteExisting` — overwrite if file exists

**⚠️ Do NOT use InvokeCode to manually save attachments.** `SaveMailAttachments` handles file streams, naming conflicts, and filtering in a single activity.

## PDF Activities

Requires `UiPath.PDF.Activities` package. Add namespace `xmlns:ui="http://schemas.uipath.com/workflow/activities"` (same as core activities — PDF activities are in the `ui:` prefix). Also needs these assembly references:
```
<AssemblyReference>UiPath.PDF.Activities</AssemblyReference>
```
And these namespace imports:
```
<x:String>UiPath.PDF.Activities</x:String>
```

### Read PDF Text (native/digital PDFs)

Extracts text from native (digitally-created) PDF files. Fast and accurate but returns empty string for scanned/image PDFs.

→ **Use `gen_read_pdf_text()`** — generates correct XAML deterministically.

Properties:
- `FileName` — VB.NET expression for the PDF file path (e.g., `[CurrentFile.FullName]`)
- `Text` — output variable to receive extracted text (String)
- `Range` — page range: `"All"`, `"1"`, `"1-3"`, `"1,3,5"`
- `PreserveFormatting="{x:Null}"` — default; set to `True` to keep original layout spacing

### Read PDF With OCR (scanned/image PDFs)

Extracts text from scanned PDFs using an OCR engine. Slower than ReadPDFText but works on image-based PDFs. Uses an `ActivityFunc` delegate pattern for the OCR engine — this is a real export structure, not simplified.

**Requires both** `UiPath.PDF.Activities` AND `UiPath.UIAutomation.Activities` (the Tesseract OCR engine `ui:GoogleOCR` lives in UIAutomation).

→ **Use `gen_read_pdf_with_ocr()`** — generates correct XAML deterministically.

Properties:
- `FileName`, `Range`, `Text` — same as ReadPDFText
- `ImageDpi` — DPI for rendering pages to images before OCR (default `300`, lower = faster but less accurate; `150` is a common tradeoff)
- `DegreeOfParallelism` — `-1` for automatic threading, or a specific number
- **OCR Engine delegate pattern:** The `.OCREngine` child uses `ActivityFunc` with specific type arguments that include System.Drawing types. This requires these namespaces:
  - `xmlns:sd="clr-namespace:System.Drawing;assembly=System.Drawing.Common"`
  - `xmlns:sd1="clr-namespace:System.Drawing;assembly=System.Drawing.Primitives"`
- **OCR engine element:** Despite the class name `ui:GoogleOCR`, the `DisplayName` may say `"Tesseract OCR"` — UiPath reuses this element for both engines. The `Profile` attribute controls the engine mode
- **Package:** `ui:GoogleOCR` (Tesseract) is part of `UiPath.UIAutomation.Activities` — this package MUST be added to project.json for the OCR engine to work. `UiPath.OCR.Activities` is a separate package for advanced OCR engines (OmniPage, Google Cloud Vision, Microsoft OCR) used in Document Understanding workflows
- `Image="[Image]"` — must reference the delegate argument name `Image`

### Common PDF Pattern — Native + OCR Fallback

Standard pattern: try ReadPDFText first, if result is empty (scanned PDF), fall back to ReadPDFWithOCR:
→ **Use `gen_read_pdf_text()` + `gen_if()` + `gen_read_pdf_with_ocr()`** — compose the fallback chain.

Notes:
- Different regex patterns may be needed for native vs scanned PDFs (different text formatting)
- `String.IsNullOrEmpty()` is the **only** correct check — ReadPDFText returns empty string (not Nothing) for scanned PDFs
- **⚠️ Do NOT add length checks** like `OrElse strText.Length < 50` — short text is legitimate (cover pages, one-line invoices). Only truly scanned PDFs return empty/null.
- For bulk extraction, combine with ForEachFileX + BuildDataTable + AddDataRow + WriteRange

## Database Activities

Requires NuGet: `UiPath.Database.Activities`. Namespace: `xmlns:ui="http://schemas.uipath.com/workflow/activities"` (same as core activities).

**⚠️ Do NOT use InvokeCode with SqlConnection/SqlClient for database operations.** Use the dedicated database activities below — they handle connection pooling, parameterized queries, and proper disposal.

### DatabaseConnect
```json
{
  "gen": "database_connect",
  "args": {
    "connection_variable": "secstrConnectionString",
    "output_variable": "dbConnection"
  }
}
```
Properties:
- `provider` — `"Microsoft.Data.SqlClient"` (default, SQL Server), `"System.Data.Odbc"` (ODBC), `"Oracle.ManagedDataAccess.Client"` (Oracle)
- `connection_variable` — connection string as SecureString (from GetRobotCredential or asset)
- `output_variable` — output `DatabaseConnection` variable for reuse in ExecuteQuery/ExecuteNonQuery

### ExecuteQuery (SELECT → DataTable)

```json
{
  "gen": "execute_query",
  "args": {
    "sql": "SELECT * FROM ProcessLog WHERE Status = @status",
    "output_variable": "dt_Output",
    "connection_string_variable": "secstrConnectionString",
    "parameters": [{"name": "status", "type": "x:String", "value": "[strStatus]"}]
  }
}
```
Properties:
- `sql` — SQL query string (use `@paramName` for parameterized queries)
- `output_variable` — output DataTable variable
- `connection_variable` — reuse a `DatabaseConnect` output (alternative to `connection_string_variable`)
- `parameters` — typed params for parameterized queries (prevents SQL injection)

### ExecuteNonQuery (INSERT/UPDATE/DELETE)
```json
{
  "gen": "execute_non_query",
  "args": {
    "sql": "INSERT INTO ProcessLog (Amount, ProcessedAt) VALUES (@amt, GETDATE())",
    "connection_variable": "dbConnection",
    "parameters": [{"name": "amt", "type": "x:Decimal", "value": "[dblAmount]"}]
  }
}
```
Properties:
- `sql` — INSERT/UPDATE/DELETE statement with `@paramName` placeholders
- `affected_records_variable` — (optional) Int32 output of rows affected
- `connection_variable` — reuse DatabaseConnect output for multiple operations in same connection

## Screenshot Activities

Requires NuGet: `UiPath.UIAutomation.Activities`. These activities use the `ui:` namespace (`xmlns:ui="http://schemas.uipath.com/workflow/activities"`).

### TakeScreenshot + SaveImage
For error screenshots, use the built-in `TakeScreenshot` + `SaveImage` activities. In REFramework projects, call `Framework/TakeScreenshot.xaml` via InvokeWorkflowFile.

**⚠️ Do NOT use InvokeCode with System.Drawing.Graphics.CopyFromScreen.** The activities handle DPI scaling, multi-monitor setups, and memory disposal correctly.

```json
{
  "gen": "take_screenshot_and_save",
  "args": {
    "screenshot_variable": "imgScreenshot",
    "save_path_variable": "strScreenshotPath"
  }
}
```
Properties:
- `screenshot_variable` — intermediate `ui:Image` variable (declare as variable type `ui:Image`)
- `save_path_variable` — file path to save the screenshot- `Target` — `{x:Null}` selector captures full screen; provide a selector for specific window/element
- `SaveImage.FileName` — output file path (`.png` recommended)
- `SaveImage.Image` — the `ui:Image` from TakeScreenshot

## Modern UI Automation (uix: namespace)
