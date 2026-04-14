"""Data structure and miscellaneous lint rules."""

import os
import re
from collections import Counter

from ._registry import lint_rule
from ._context import FileContext, ValidationResult
from ._constants import _RE_VARIABLE_DECL, _RE_CATCH_TYPE, X_ACTIVITIES_NO_CONTINUE_ON_ERROR, EXCEPTION_SPECIFICITY

from plugin_loader import get_extra_key_activities

# Pre-compiled re.DOTALL pattern for AddQueueItem ItemInformation validation (lint 20)
_RE_ITEM_INFO_XSTRING = re.compile(r'ItemInformation>.*?<x:String\s', re.DOTALL)


@lint_rule(2)
def lint_catch_ordering(ctx: FileContext, result: ValidationResult):
    """Lint 2: Catch blocks must be ordered most-specific to least-specific."""
    content = ctx.active_content

    # Find all TryCatch blocks and their Catch sequences
    # Pattern: consecutive <Catch x:TypeArguments="..."> within <TryCatch.Catches>
    catches_blocks = re.findall(
        r'<TryCatch\.Catches>(.*?)</TryCatch\.Catches>', content, re.DOTALL
    )

    for block in catches_blocks:
        types = _RE_CATCH_TYPE.findall(block)
        if len(types) < 2:
            continue

        # Check ordering
        for i in range(len(types) - 1):
            curr_spec = EXCEPTION_SPECIFICITY.get(types[i], 5)
            next_spec = EXCEPTION_SPECIFICITY.get(types[i + 1], 5)
            if curr_spec > next_spec:
                result.warn(
                    f"Catch block ordering: '{types[i]}' (generic) before '{types[i+1]}' (specific) "
                    f"— the specific catch will never execute"
                )
                break
        else:
            result.ok(f"Catch ordering OK: {' \u2192 '.join(types)}")


@lint_rule(3)
def lint_retry_scope(ctx: FileContext, result: ValidationResult):
    """Lint 3: RetryScope should have an action body, condition is optional."""
    content = ctx.active_content

    retry_scopes = re.findall(
        r'<ui:RetryScope[^>]*>(.*?)</ui:RetryScope>', content, re.DOTALL
    )

    for i, rs in enumerate(retry_scopes, 1):
        has_body = "RetryScope.ActivityBody" in rs
        if not has_body:
            result.error(f"RetryScope #{i}: missing ActivityBody — nothing to retry")

        has_condition = "RetryScope.Condition" in rs
        empty_condition = '<ActivityFunc x:TypeArguments="x:Boolean" />' in rs
        if not has_condition:
            result.warn(f"RetryScope #{i}: no Condition block — will only retry on exception")
        elif empty_condition:
            result.ok(f"RetryScope #{i}: empty condition (retry on exception only) — OK")


@lint_rule(4, golden_suppressed=True)
def lint_display_names(ctx: FileContext, result: ValidationResult):
    """Lint 4: Key activities should have DisplayName for readability."""
    content = ctx.active_content

    # Activities that really should have DisplayNames
    key_activities = [
        "Sequence", "If", "TryCatch", "Assign", "Throw",
        "ui:LogMessage", "ui:InvokeWorkflowFile", "ui:RetryScope",
        "ui:ForEachRow", "ui:MultipleAssign", "ui:WriteCell",
        "ui:InvokeCode", "ui:HttpClient",
        "ui:CopyFile", "ui:MoveFile", "ui:CreateDirectory",
        "uix:NApplicationCard", "uix:NClick", "uix:NTypeInto",
        "uix:NGetText", "uix:NSelectItem", "uix:NCheckState",
        # Plugin-registered key activities merged below
    ]
    key_activities.extend(get_extra_key_activities())

    missing_count = 0
    for act in key_activities:
        # Find instances of this activity without DisplayName
        # Pattern: <Activity ...> where there's no DisplayName= before the >
        pattern = rf'<{re.escape(act)}\s+(?!.*DisplayName=)[^>]*>'
        matches = re.findall(pattern, content)
        if matches:
            missing_count += len(matches)

    if missing_count > 0:
        result.warn(f"{missing_count} key activities missing DisplayName")
    else:
        result.ok("All key activities have DisplayName")


@lint_rule(6)
def lint_empty_bodies(ctx: FileContext, result: ValidationResult):
    """Lint 6: Detect empty Sequence/TryCatch.Try bodies (placeholder noise)."""
    content = ctx.active_content

    # Empty TryCatch.Try
    empty_try = re.findall(
        r'<TryCatch\.Try>\s*<Sequence[^>]*/>\s*</TryCatch\.Try>', content
    )
    if empty_try:
        result.warn(f"{len(empty_try)} empty TryCatch.Try block(s)")

    # Empty TryCatch.Finally (not an error, just noise)
    empty_finally = re.findall(
        r'<TryCatch\.Finally>\s*<Sequence[^>]*/>\s*</TryCatch\.Finally>', content
    )
    if empty_finally:
        result.warn(f"{len(empty_finally)} empty TryCatch.Finally block(s) — remove if unused")


@lint_rule(7)
def lint_throw_expression(ctx: FileContext, result: ValidationResult):
    """Lint 7: Throw activities must have a valid Exception expression.
    
    Valid patterns:
      [New BusinessRuleException("message")]
      [New ApplicationException("message")]  
      [New Exception("message")]
      [New Exception("context. " + exception.Message)]
      [exception]  (rethrowing caught exception variable)
    
    Common mistakes:
      - Missing Exception= attribute entirely
      - Using 'throw new' (C# syntax) instead of 'New' (VB.NET)
      - Using 'Throw New' with capital T (VB keyword, not valid in expression)
      - Missing 'New' keyword: [BusinessRuleException("msg")]
      - Wrong type: [New BRE("msg")] or [New BusinessException("msg")]
    """
    content = ctx.active_content

    # Find <Throw without Exception=
    throws_no_expr = re.findall(r'<Throw\s+(?!.*Exception=)[^>]*/>', content)
    if throws_no_expr:
        result.error(f"{len(throws_no_expr)} Throw activit(ies) missing Exception expression")

    # Check that Throw expressions use proper patterns
    throw_exprs = re.findall(r'<Throw[^>]*Exception="\[([^"]*)\]"', content)
    VALID_EXCEPTION_TYPES = [
        "BusinessRuleException",
        "ApplicationException", 
        "Exception",
        "ArgumentException",
        "InvalidOperationException",
        "TimeoutException",
    ]
    # Fully-qualified namespaces that Claude hallucinates — Studio crashes
    FQDN_PATTERNS = [
        (r'UiPath\.Core\.Activities\.BusinessRuleException', "BusinessRuleException"),
        (r'UiPath\.Core\.Activities\.ApplicationException', "ApplicationException"),
        (r'System\.Exception', "Exception"),
    ]
    for expr in throw_exprs:
        # Skip rethrow variable patterns like [exception] or [breException]
        if re.match(r'^[a-zA-Z_]\w*$', expr.strip()):
            continue
        # Check for fully-qualified namespace (common hallucination)
        for fqdn_re, short_name in FQDN_PATTERNS:
            if re.search(fqdn_re, expr):
                result.error(
                    f"[lint 7] Throw uses fully-qualified '{fqdn_re.replace(chr(92), '')}' — "
                    f"Studio cannot resolve this. Use short form: "
                    f"[New {short_name}(\"message\")]"
                )
                break
        # Must start with "New " (VB.NET syntax, case-insensitive)
        if not expr.strip().lower().startswith("new "):
            if expr.strip().lower().startswith("throw "):
                result.error(
                    f"Throw expression uses C# syntax 'throw new' — UiPath uses VB.NET: "
                    f"[New BusinessRuleException(\"message\")] not [throw new ...]"
                )
            else:
                result.warn(
                    f"Throw expression '{expr[:60]}' — expected "
                    f"'New BusinessRuleException/ApplicationException(...)' or rethrow variable"
                )


@lint_rule(8, golden_suppressed=True)
def lint_config_references(ctx: FileContext, result: ValidationResult):
    """Lint 8: Config dictionary access patterns."""
    content = ctx.active_content

    # Find in_Config references (both &quot; in attributes and " in element content)
    config_refs = re.findall(r'in_Config\(&quot;([^&]*)&quot;\)', content)
    config_refs += re.findall(r'in_Config\("([^"]+)"\)', content)
    if not config_refs:
        return

    # Check for .ToString on Config access (common omission)
    raw_config = re.findall(r'in_Config\(&quot;[^&]*&quot;\)(?!\.ToString)', content)
    raw_config += re.findall(r'in_Config\("[^"]+"\)(?!\.ToString)', content)
    if raw_config:
        result.warn(
            f"{len(raw_config)} in_Config() access(es) without .ToString — "
            f"Config values are Object type, use .ToString for string operations"
        )


@lint_rule(15)
def lint_input_dialog(ctx: FileContext, result: ValidationResult):
    """Lint 15: InputDialog — check for common mistakes."""
    try:
        content = ctx.active_content
    except Exception:
        return

    if "InputDialog" not in content:
        return

    # Anti-pattern: using Options with VB array instead of OptionsString with semicolons
    # Wrong: Options="[{&quot;January&quot;, &quot;February&quot;}]"
    # Right: OptionsString="January;February"
    bad_options = re.findall(
        r'Options="\[.*?\]"', content
    )
    for match in bad_options:
        if '{x:Null}' not in match:
            result.error(
                f"InputDialog uses Options with VB array expression — "
                f"use OptionsString with semicolons instead (e.g. OptionsString=\"A;B;C\")"
            )

    # Anti-pattern: inline Result attribute instead of child element
    # Wrong: Result="[strVar]"
    # Right: <ui:InputDialog.Result><OutArgument x:TypeArguments="x:String">[strVar]</OutArgument></ui:InputDialog.Result>
    inline_result = re.findall(
        r'<ui:InputDialog[^>]*\sResult="[^"]*"', content
    )
    if inline_result:
        result.warn(
            f"InputDialog uses inline Result attribute — "
            f"use child element <ui:InputDialog.Result><OutArgument> instead"
        )


@lint_rule(17)
def lint_inline_result(ctx: FileContext, result: ValidationResult):
    """Lint 17: Detect incorrect Result= on UiX activities that use different property names.

    Modern UiPath UI activities do NOT have a 'Result' property. Each activity
    has its own output property name:
        - NExtractDataGeneric → ExtractedData="[dt_var]"
        - NGetText → TextString="[str_var]"
    Using Result= causes Studio error: 'Could not find member Result in type ...'
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    # NExtractDataGeneric: must use ExtractedData, not Result or DataTable in any form
    if "NExtractDataGeneric" in content:
        if re.search(r'<uix:NExtractDataGeneric[^>]*\sResult="', content):
            result.error(
                "NExtractDataGeneric uses Result= attribute — property does not exist. "
                "Use ExtractedData=\"[dt_variable]\" instead"
            )
        if "<uix:NExtractDataGeneric.Result>" in content:
            result.error(
                "NExtractDataGeneric uses .Result child element — property does not exist. "
                "Use inline ExtractedData=\"[dt_variable]\" attribute instead"
            )
        if re.search(r'<uix:NExtractDataGeneric[^>]*\sDataTable="', content):
            result.error(
                "[lint 17] NExtractDataGeneric uses DataTable= attribute — property does not exist. "
                "Use ExtractedData=\"[dt_variable]\" instead. "
                "The x:TypeArguments=\"sd2:DataTable\" is the generic type parameter, NOT a property."
            )
        if "<uix:NExtractDataGeneric.DataTable>" in content:
            result.error(
                "[lint 17] NExtractDataGeneric uses .DataTable child element — property does not exist. "
                "Use inline ExtractedData=\"[dt_variable]\" attribute instead"
            )
        if not re.search(r'ExtractedData="', content) and "NExtractDataGeneric" in content:
            result.warn(
                "NExtractDataGeneric has no ExtractedData attribute — "
                "output DataTable will not be captured"
            )

    # NGetText: must use TextString, not Result
    if re.search(r'<uix:NGetText[^>]*\sResult="', content):
        result.error(
            "NGetText uses Result= attribute — property does not exist. "
            "Use TextString=\"[str_variable]\" instead"
        )


@lint_rule(19)
def lint_old_foreach(ctx: FileContext, result: ValidationResult):
    """Lint 19: Detect old ForEach (System.Activities) instead of modern ui:ForEach.
    
    Old <ForEach> doesn't allow setting item name in Studio UI and lacks
    CurrentIndex property. Modern <ui:ForEach> is required for all new projects.
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    # Match <ForEach that is NOT <ui:ForEach (avoid ForEachRow, ForEachFileX, etc.)
    old_matches = re.findall(r'<ForEach[\s>]', content)
    modern_matches = re.findall(r'<ui:ForEach[\s>]', content)
    # Subtract ForEachRow/ForEachFileX/etc. — those only exist as ui: prefix
    # Only plain <ForEach has an old vs modern distinction
    if old_matches:
        count = len(old_matches)
        result.warnings.append(
            f"{count} old <ForEach> found — use <ui:ForEach> with "
            f"<ui:ForEach.Body> wrapper and CurrentIndex property"
        )


@lint_rule(20)
def lint_addqueueitem_reserved_keys(ctx: FileContext, result: ValidationResult):
    """Lint 20: Detect reserved property names used as x:Key in AddQueueItem.ItemInformation.
    
    AddQueueItem has built-in properties (DueDate, DeferDate, Reference, Priority).
    Using these as x:Key in ItemInformation causes Studio error:
    'A variable, RuntimeArgument or a DelegateArgument already exists with the name ...'
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    if "AddQueueItem" not in content:
        return

    RESERVED = {"DueDate", "DeferDate", "Reference", "Priority",
                "QueueType", "FolderPath", "ServiceBaseAddress", "TimeoutMS"}
    keys = re.findall(r'<InArgument[^>]+x:Key="([^"]+)"', content)
    conflicts = [k for k in keys if k in RESERVED]
    if conflicts:
        result.errors.append(
            f"AddQueueItem ItemInformation uses reserved key(s): "
            f"{', '.join(conflicts)} — rename to avoid 'RuntimeArgument already exists' error "
            f"(e.g. InvoiceDueDate instead of DueDate)"
        )

    # Detect wrong element type inside ItemInformation
    # ItemInformation expects Dictionary(String, InArgument) — entries must be
    # <InArgument x:TypeArguments="x:String" x:Key="..."> NOT <x:String x:Key="...">
    if _RE_ITEM_INFO_XSTRING.search(content):
        result.error(
            "[lint 20] AddQueueItem.ItemInformation contains <x:String> elements — "
            "wrong type. ItemInformation expects Dictionary(String, InArgument). "
            "Each entry must be: <InArgument x:TypeArguments=\"x:String\" x:Key=\"FieldName\">"
            "[value]</InArgument> — NOT <x:String x:Key=\"...\">value</x:String>"
        )

    # Detect ItemInformation with a single InArgument wrapping a New Dictionary expression.
    # This is a hallucination where the LLM puts a VB Dictionary expression as the value
    # instead of using keyed InArgument elements. Crashes with:
    # "Missing key value on 'InArgument' object"
    # Wrong:  <InArgument x:TypeArguments="scg:Dictionary(x:String, x:Object)">[New Dictionary(...)]</InArgument>
    # Right:  <scg:Dictionary x:TypeArguments="x:String, InArgument">
    #           <InArgument x:TypeArguments="x:String" x:Key="Field">[value]</InArgument>
    #         </scg:Dictionary>
    item_info_blocks = re.findall(
        r'<ui:AddQueueItem\.ItemInformation>(.*?)</ui:AddQueueItem\.ItemInformation>',
        content, re.DOTALL
    )
    for block in item_info_blocks:
        # Check for InArgument with Dictionary TypeArguments (the hallucinated pattern)
        if re.search(r'<InArgument\s+x:TypeArguments="scg:Dictionary', block):
            result.error(
                "[lint 20] AddQueueItem.ItemInformation contains InArgument with Dictionary "
                "TypeArguments — this crashes Studio with 'Missing key value on InArgument'. "
                "ItemInformation expects <scg:Dictionary x:TypeArguments=\"x:String, InArgument\"> "
                "with individual keyed <InArgument x:Key=\"FieldName\"> entries, "
                "NOT a single InArgument wrapping a New Dictionary(...) expression. "
                "Use gen_invoke_workflow() from scripts/generate_activities.py"
            )
        # Check for Dictionary wrapper using 'Argument' type (not 'InArgument')
        # Crashes: "Could not resolve type 'Dictionary(String,Argument)'"
        if re.search(r'Dictionary\s+x:TypeArguments="x:String,\s*(?:ui:)?Argument"', block):
            result.error(
                "[lint 20] AddQueueItem.ItemInformation uses Dictionary(String, Argument) — "
                "'Argument' type does not exist. Correct wrapper is: "
                "<scg:Dictionary x:TypeArguments=\"x:String, InArgument\"> with "
                "<InArgument x:TypeArguments=\"x:String\" x:Key=\"Field\">[value]</InArgument>"
            )
        # Check for ui:InArgument (wrong namespace prefix — InArgument is in default ns)
        if re.search(r'<ui:InArgument', block):
            result.error(
                "[lint 20] AddQueueItem.ItemInformation uses <ui:InArgument> — "
                "InArgument is in the default XAML activities namespace, not ui:. "
                "Use: <InArgument x:TypeArguments=\"x:String\" x:Key=\"Field\">[value]</InArgument>"
            )


@lint_rule(21)
def lint_json_markup_extension_escape(ctx: FileContext, result: ValidationResult):
    """Lint 21: Detect JSON attribute values missing XAML {} escape prefix.
    
    When a XAML attribute value starts with { and contains JSON (not a markup
    extension like {x:Null} or {Binding}), the XAML parser crashes with:
    'Quote characters or are only allowed at the start of values'
    
    Fix: prefix with {} (empty curly braces = literal escape):
      FormLayout="{}{&quot;components&quot;:...}"
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    # Find attributes whose value starts with { followed by &quot; (JSON pattern)
    # but NOT with {} escape prefix, and NOT known markup extensions
    # Pattern: attr="{&quot; without preceding {}
    matches = re.findall(
        r'(\w+)="(\{)(&quot;|&amp;quot;)',
        content
    )
    for attr_name, brace, _quote in matches:
        # Skip known XAML markup extensions that legitimately start with {
        # These are followed by x:, Binding, Static, etc.
        pass
    
    # More precise: find attrs starting with {" or {&quot; but NOT {}{
    bad = re.findall(
        r'(\w+)="\{&quot;',
        content
    )
    if bad:
        attrs = list(set(bad))
        result.errors.append(
            "JSON attribute(s) missing XAML {} escape prefix: "
            + ", ".join(attrs)
            + " -- value starts with '{&quot;' which XAML interprets as "
            + "markup extension. Fix: prefix value with '{}' escape "
            + '(e.g. FormLayout="{}{&quot;components&quot;:...")'
        )


@lint_rule(72)
def lint_separate_login_file(ctx: FileContext, result: ValidationResult):
    """Lint 72: Login workflows must not be separate files.

    Rule 4: Login always lives inside AppName_Launch.xaml — NEVER create
    a separate AppName_Login.xaml. The Launch workflow handles everything:
    open browser/app → login (if needed) → verify ready state.
    """
    basename = os.path.basename(ctx.filepath)
    if re.match(r'.*_Login\.xaml$', basename, re.IGNORECASE):
        app_name = basename.replace("_Login.xaml", "").replace("_login.xaml", "")
        result.error(
            f"[lint 72] Separate login file '{basename}' — Rule 4 violation. "
            f"Login must live inside '{app_name}_Launch.xaml', not a separate file. "
            f"The Launch workflow handles: open app → login → verify ready state. "
            f"Move all login logic into {app_name}_Launch.xaml and delete this file."
        )


@lint_rule(31)
def lint_continue_on_error_x_activities(ctx: FileContext, result: ValidationResult):
    """Lint 31: ContinueOnError on newer 'X' activities that don't support it.
    
    DeleteFileX, ForEachFileX etc. are newer activities that don't inherit from
    legacy ActivityBase. They lack ContinueOnError — Studio crashes with
    'Could not find member ContinueOnError'.
    """
    try:
        content = ctx.active_content
    except Exception:
        return
    
    for activity in X_ACTIVITIES_NO_CONTINUE_ON_ERROR:
        pattern = rf'<ui:{activity}\b[^>]*ContinueOnError='
        for match in re.finditer(pattern, content):
            result.error(
                f"[lint 31] {activity} has ContinueOnError — this property does NOT exist "
                f"on {activity} (newer 'X' activity). Studio crashes with "
                f"'Could not find member ContinueOnError in type {activity}'. "
                f"Remove ContinueOnError. Wrap in TryCatch if error suppression is needed."
            )


@lint_rule(32)
def lint_special_folder_temp(ctx: FileContext, result: ValidationResult):
    """Lint 32: Environment.SpecialFolder.Temp does not exist.
    
    Common hallucination: SpecialFolder.Temp — not a valid enum value.
    Use Path.GetTempPath() instead.
    """
    try:
        content = ctx.active_content
    except Exception:
        return
    
    if "SpecialFolder.Temp" in content:
        count = content.count("SpecialFolder.Temp")
        result.error(
            f"[lint 32] Environment.SpecialFolder.Temp x{count} — not a valid enum value "
            f"(BC30456: 'Temp' is not a member of 'Environment.SpecialFolder'). "
            f"Use Path.GetTempPath() instead."
        )


@lint_rule(35)
def lint_password_securetext(ctx: FileContext, result: ValidationResult):
    """Lint 35: NTypeInto for password fields must use SecureText, not Text.
    
    Detects NTypeInto activities with 'Password' in DisplayName that use
    Text= instead of SecureText=. Passwords from GetRobotCredential are
    SecureString and must be typed via SecureText to avoid plaintext exposure.
    Also checks for GetRobotCredential placed outside NApplicationCard.Body
    (credential scope should be minimal — inside the app session).
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    # Check NTypeInto with "Password" in DisplayName using Text= instead of SecureText=
    password_typeintos = re.finditer(
        r'<uix:NTypeInto\b[^>]*DisplayName="[^"]*[Pp]assword[^"]*"[^>]*', content
    )
    for match in password_typeintos:
        element = match.group(0)
        if ' Text="' in element and ' SecureText="' not in element:
            result.error(
                "[lint 35] NTypeInto for password field uses Text= instead of SecureText=. "
                "Passwords from GetRobotCredential are SecureString — use "
                "SecureText=\"[secstrPassword]\" to avoid plaintext exposure in logs."
            )

    # Check if GetRobotCredential appears before/outside NApplicationCard
    if 'GetRobotCredential' in content and 'NApplicationCard' in content:
        cred_pos = content.find('GetRobotCredential')
        card_body_pos = content.find('NApplicationCard.Body')
        if cred_pos < card_body_pos:
            result.warn(
                "[lint 35] GetRobotCredential appears before NApplicationCard.Body — "
                "credentials should be retrieved at minimal scope INSIDE the app/browser "
                "session, not outside it. See golden sample WebAppName_Launch.xaml."
            )


@lint_rule(51)
def lint_getqueueitem_in_dispatcher(ctx: FileContext, result: ValidationResult):
    """Lint 51: Detect GetQueueItem in GetTransactionData with non-QueueItem TransactionItem type.

    A dispatcher iterates local data (DataTable rows, strings, etc.) — it should
    NOT use GetQueueItem. This catches the common mistake of scaffolding a dispatcher
    without replacing the performer's GetQueueItem logic.
    """
    basename = os.path.basename(ctx.filepath)
    if "GetTransactionData" not in basename:
        return
    try:
        content = ctx.active_content
    except Exception:
        return

    has_getqueueitem = "GetQueueItem" in content or "ui:GetQueueItem" in content
    if not has_getqueueitem:
        return

    # Check if out_TransactionItem type is NOT QueueItem (i.e., this is a dispatcher)
    non_queue_types = ["sd:DataRow", "x:String", "snm:MailMessage",
                       "scg:Dictionary(x:String, x:Object)"]
    is_dispatcher = any(
        f'Name="out_TransactionItem" Type="OutArgument({t})"' in content
        for t in non_queue_types
    )
    if is_dispatcher:
        result.error(
            "[lint 51] GetTransactionData.xaml contains GetQueueItem but TransactionItem "
            "type is not QueueItem — this is a dispatcher project. Dispatchers should use "
            "DataTable row indexing (If in_TransactionNumber <= Rows.Count) instead of "
            "GetQueueItem. Re-scaffold with --variant dispatcher to fix."
        )


@lint_rule(57)
def lint_references_collection_type(ctx: FileContext, result: ValidationResult):
    """Lint 57: ReferencesForImplementation must use AssemblyReference, not x:String.

    Studio crashes on open with XamlObjectWriterException when
    TextExpression.ReferencesForImplementation contains
    <sco:Collection x:TypeArguments="x:String"> with <x:String> children
    instead of <sco:Collection x:TypeArguments="AssemblyReference"> with
    <AssemblyReference> children.

    Error: 'The value "Collection`1[System.String]" is not of type
    "AssemblyReference" and cannot be used in this generic collection.'

    Common sub-agent hallucination: the agent confuses the pattern for
    NamespacesForImplementation (which correctly uses x:String) with
    ReferencesForImplementation (which requires AssemblyReference).
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    if "TextExpression.ReferencesForImplementation" not in content:
        return

    refs_blocks = re.findall(
        r'<TextExpression\.ReferencesForImplementation>(.*?)</TextExpression\.ReferencesForImplementation>',
        content, re.DOTALL
    )
    for block in refs_blocks:
        if 'x:TypeArguments="x:String"' in block:
            result.error(
                '[lint 57] STUDIO CRASH: TextExpression.ReferencesForImplementation uses '
                'x:TypeArguments="x:String" — must be x:TypeArguments="AssemblyReference". '
                'Child elements must be <AssemblyReference>...</AssemblyReference>, '
                'not <x:String>...</x:String>. Studio throws XamlObjectWriterException on open. '
                'NOTE: NamespacesForImplementation correctly uses x:String — do not confuse the two.'
            )
            return

        if '<x:String>' in block and '<AssemblyReference>' not in block:
            result.error(
                '[lint 57] STUDIO CRASH: TextExpression.ReferencesForImplementation contains '
                '<x:String> elements instead of <AssemblyReference> elements. '
                'Studio throws XamlObjectWriterException on open.'
            )
            return


@lint_rule(58)
def lint_orphaned_scoped_activities(ctx: FileContext, result: ValidationResult):
    """Lint 58: Modern UI activities outside NApplicationCard scope.

    Modern Design activities (NGoToUrl, NTypeInto, NClick, NGetText,
    NExtractDataGeneric, NSelectItem, NGetAttribute, NCheckAppState,
    NHover, NKeyboardShortcut, NScrollTo) are scoped — they must run
    inside an NApplicationCard that provides the browser/app context.

    Without a scope container, UiPath has no target application and the
    activity throws a runtime exception immediately.
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    # Scoped activities that require NApplicationCard parent
    SCOPED = [
        "NGoToUrl", "NTypeInto", "NClick", "NGetText", "NGetAttribute",
        "NSelectItem", "NExtractDataGeneric", "NCheckAppState", "NHover",
        "NKeyboardShortcut", "NScrollTo", "NHighlightElement",
    ]

    found_scoped = []
    for act in SCOPED:
        if f"<uix:{act}" in content or f"<uix:{act} " in content:
            found_scoped.append(act)

    if not found_scoped:
        return

    has_scope = "<uix:NApplicationCard" in content
    if not has_scope:
        result.error(
            f"[lint 58] Orphaned scoped activit(ies) without NApplicationCard: "
            f"{', '.join(found_scoped)}. Modern UI activities must run inside a "
            f"Use Application/Browser (NApplicationCard) scope that provides the "
            f"browser/app context. Without it, UiPath has no target and throws "
            f"a runtime exception. Wrap in NApplicationCard or move to a workflow "
            f"that has one."
        )


@lint_rule(104)
def lint_hardcoded_user_path(ctx: FileContext, result: ValidationResult):
    """Lint 104: Hardcoded user-specific path in FilePath attribute or element.

    Paths containing C:\\Users\\<username>\\ are machine-specific and will
    fail on other environments. Use a variable with Config or argument instead.
    """
    content = ctx.active_content
    # Attribute form: FilePath="[&quot;C:\Users\...&quot;]"
    hits = re.findall(
        r'FilePath="[^"]*(?:C:\\Users\\|C:/Users/)[^"]*"',
        content, re.IGNORECASE
    )
    # Child element form: <uix:TargetApp.FilePath>...[\"C:\Users\...\"]...</uix:TargetApp.FilePath>
    hits_elem = re.findall(
        r'<uix:TargetApp\.FilePath>.*?(?:C:\\Users\\|C:/Users/).*?</uix:TargetApp\.FilePath>',
        content, re.IGNORECASE | re.DOTALL
    )
    hits.extend(hits_elem)
    if hits:
        result.warn(
            f"[lint 104] FilePath contains user-specific path 'C:\\Users\\...' "
            f"({len(hits)}x) — this will fail on other machines. Use a variable "
            f"from Config or an InArgument instead: "
            f'FilePath="[in_Config(\\"AppPath\\").ToString]".'
        )


# Matches a bare VB array literal `{...}` inside an expression-bracketed
# attribute value (ArrayRow / Values / Collection). The negative lookahead
# skips the correct form, `New <Type>() {...}`, so only un-typed literals
# are flagged. VB.NET has no dict/set literal syntax, so there is no
# false-positive surface for standalone `{…}` in an expression.
_RE_BARE_VB_ARRAY_LITERAL = re.compile(
    r'(ArrayRow|Values|Collection)="\[\s*(?!New\s+\w+\s*\()\{[^}]*\}\s*\]"'
)


@lint_rule(114)
def lint_bare_vb_array_literal(ctx: FileContext, result: ValidationResult):
    """Lint 114: Bare VB array literal `{...}` in an expression attribute.

    A raw `{"a", "b", 4, 4.0}` in an `ArrayRow` / `Values` / `Collection`
    expression has mixed element types and VB.NET refuses to infer a common
    one — Studio rejects the XAML with compile error BC36915 ("Cannot infer
    an element type because more than one type is possible"). The type-safe
    form is `New Object() {...}` or a narrower typed array like
    `New String() {...}`.

    Catches what the generator didn't — a defence-in-depth check for
    generators that still hand-build bare array literals.
    """
    content = ctx.active_content

    hits = _RE_BARE_VB_ARRAY_LITERAL.findall(content)
    if hits:
        attrs = sorted(set(hits))
        result.error(
            f"[lint 114] {len(hits)} bare VB array literal(s) in "
            f"{'/'.join(attrs)} expression attribute(s) — will fail Studio "
            f"compile with BC36915 on heterogeneous rows. Wrap with "
            f'"New Object() {{...}}" or a narrower typed array like '
            f'"New String() {{...}}".'
        )

