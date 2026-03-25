# Error Handling

TryCatch, Throw/Rethrow, exception types, RetryScope.

## Contents
  - [Try Catch](#try-catch)
  - [Throw / Rethrow](#throw-rethrow)
  - [Exception Types — When to Use Which](#exception-types-when-to-use-which)
  - [Common Specific Exception Types](#common-specific-exception-types)
  - [Exception Property Access](#exception-property-access)
  - [Error Handling Best Practices](#error-handling-best-practices)
  - [Retry Scope](#retry-scope)

### Try Catch
→ **Use `gen_try_catch()`** — generates correct XAML deterministically. Handles Catch block ordering, exception TypeArguments, and ActivityAction wrappers.

**⚠️ TypeArguments must use xmlns prefix, never fully-qualified CLR names.**
Wrong: `<Catch x:TypeArguments="System.Exception">` — XAML parser cannot resolve dotted CLR names.
Right: `<Catch x:TypeArguments="s:Exception">` — using the `s:` xmlns prefix.
Same applies to `ActivityAction`, `DelegateInArgument`, `Variable`, and any element with `x:TypeArguments`.
Common mappings: `System.Exception` → `s:Exception`, `System.Data.DataTable` → `sd:DataTable`, `UiPath.Core.Activities.BusinessRuleException` → `ui:BusinessRuleException`.
Lint 99 catches this.


### Throw / Rethrow

**Throw expression syntax:** `[New ExceptionType("message")]` — always VB.NET `New` keyword, always wrapped in `[...]` brackets. The Throw activity's `Exception=` attribute takes a VB.NET expression that creates the exception object.

→ **Use `gen_throw()`** — generates correct XAML deterministically.


**Common mistakes to avoid:**
- ❌ `throw new BusinessRuleException(...)` — this is C# syntax, UiPath uses VB.NET
- ❌ `Throw New BusinessRuleException(...)` — the `Throw` keyword is the activity, not part of the expression
- ❌ `[BusinessRuleException("msg")]` — missing `New` keyword
- ❌ `[New BRE("msg")]` or `[New BusinessException("msg")]` — wrong type name
- ❌ `[New UiPath.Core.Activities.BusinessRuleException("msg")]` — fully-qualified namespace, Studio cannot resolve
- ❌ `[New System.Exception("msg")]` — same issue, use short form
- ✅ `[New BusinessRuleException("msg")]` — correct
- ✅ `[New Exception("msg")]` — correct for system exceptions

Notes:
- `Throw` is self-closing (no child elements)
- Inside a Catch block, `exception` (or whatever the `DelegateInArgument` is named) provides access to the caught exception
- Common pattern: wrap in new Exception with context: `New Exception("Context message. " + exception.Message)`
- `Rethrow` only valid inside a Catch block — re-raises the caught exception with original stack trace

### Exception Types — When to Use Which

**BusinessRuleException** (`ui:BusinessRuleException`)
- Data is incomplete, invalid, or violates a business rule
- Examples: missing phone digit, invalid email format, required field empty, duplicate record
- Retrying will NOT help — the data itself is the problem
- Orchestrator does NOT auto-retry queue items failed with BRE
- Action: log the issue, skip transaction, notify human user
- Throw: `[New BusinessRuleException("Phone number missing digit")]`
- Catch type: `<Catch x:TypeArguments="ui:BusinessRuleException">`

**ApplicationException** (`s:ApplicationException` — System namespace)
- Technical/infrastructure issue — app froze, element not found, timeout, network error
- Examples: browser crash, application not responding, selector timeout, API 500 error
- Retrying MAY help — the problem could be transient
- Orchestrator WILL auto-retry queue items failed with ApplicationException (if Auto Retry = Yes on queue)
- Action: retry transaction, restart application if needed
- Throw: `[New ApplicationException("Financial app not responding")]`
- Catch type: `<Catch x:TypeArguments="s:ApplicationException">`
- Requires: `xmlns:s="clr-namespace:System;assembly=System.Private.CoreLib"`

**System.Exception** (`s:Exception`)
- Generic catch-all — catches both BRE and ApplicationException
- Use as the last Catch block to handle unexpected errors
- In REFramework SetTransactionStatus: determines retry behavior based on exception type

**Catch block ordering rule:** Most specific first, most general last.
```xml
<TryCatch.Catches>
  <!-- 1. Business rule issues (no retry) -->
  <Catch x:TypeArguments="ui:BusinessRuleException">...</Catch>
  <!-- 2. Application/technical issues (may retry) -->
  <Catch x:TypeArguments="s:ApplicationException">...</Catch>
  <!-- 3. Catch-all for anything unexpected -->
  <Catch x:TypeArguments="s:Exception">...</Catch>
</TryCatch.Catches>
```

**REFramework SetTransactionStatus decision logic:**
```
Exception caught
├─ Is BusinessRuleException?
│   ├─ Yes → Set status = Failed (BRE), log, move to next transaction
│   └─ No → Is retry limit reached?
│       ├─ Yes → Set status = Failed (Application), log, restart apps
│       └─ No → Increment retry counter, restart apps, retry same transaction
```

### Common Specific Exception Types

| Exception | Namespace | Typical Cause | Action |
|---|---|---|---|
| `ui:BusinessRuleException` | `ui:` | Invalid data, business rule violation | Skip transaction, notify |
| `s:ApplicationException` | `s:` | App crash, infra failure | Retry, restart app |
| `s:TimeoutException` | `s:` | Operation exceeded time limit | Retry with longer timeout |
| `s:NullReferenceException` | `s:` | Accessing null variable/object | Fix logic, add null checks |
| `s:ArgumentException` | `s:` | Invalid argument to method | Fix input data/logic |
| `s:FormatException` | `s:` | Parse failure (CInt, CDate on bad data) | Validate input first |
| `s:IO.IOException` | `s:` | File locked, disk full, path not found | Retry, check permissions |
| `s:Net.WebException` | `s:` | HTTP request failed, DNS error | Retry with backoff |

UiPath-specific (from `uix:` namespace):
- Selector not found → caught as generic `s:Exception` with message containing "selector"
- Element not interactable → usually `s:Exception` from UI automation

### Exception Property Access
```vb
' In Catch block, the exception variable (e.g., "exception") has:
exception.Message                    ' Error description
exception.GetType.Name               ' "BusinessRuleException", "ApplicationException"
exception.Source                     ' Assembly that threw
exception.StackTrace                 ' Full stack trace
exception.InnerException             ' Nested exception (can be Nothing)
exception.InnerException?.Message    ' Safe inner message access (C# only)

' VB.NET safe inner exception
If(exception.InnerException IsNot Nothing, exception.InnerException.Message, "")

' Check exception type in expressions (e.g., in If condition)
TypeOf exception Is BusinessRuleException
TypeOf exception Is ApplicationException
```

### Error Handling Best Practices

**1. Where to put TryCatch:**
- Around individual risky operations (API calls, file operations, UI interactions)
- NOT around the entire Process.xaml — that's REFramework's job
- Around groups of related steps that should fail together

**2. When to Rethrow vs handle:**
- In Process.xaml: Rethrow — let REFramework handle retry/status logic
- In utility workflows: Rethrow with context — `Throw New ApplicationException("Failed to login: " + exception.Message, exception)`
- In non-REFramework: Handle locally if you have recovery logic

**3. Logging pattern:**
```vb
' Always include: what failed + exception message + relevant context
"[ERROR] Failed to process invoice " + strInvoiceId + ": " + exception.Message
"[ERROR] API call failed for endpoint " + strEndpoint + " - Status: " + intStatusCode.ToString + " - " + exception.Message
```

**4. Throw with inner exception (preserves stack trace):**
→ **Use `gen_throw()`** — generates correct XAML deterministically.

The second parameter wraps the original exception as `InnerException`.

### Retry Scope
→ **Use `gen_retryscope()`** — generates correct XAML deterministically.

Properties:
- `NumberOfRetries` — max retry attempts (default: 3). Omit to use default
- `RetryInterval` — delay between retries. Generator omits this (uses Studio default)
- `LogRetriedExceptions="{x:Null}"` — suppress retry exception logging
- Condition uses `ActivityFunc x:TypeArguments="x:Boolean"` (NOT `ActivityAction`)
- `ui:CheckTrue Expression="[...]"` — VB.NET boolean expression. If False, retry continues

**Empty condition variant** — retry on any exception, no success check:
→ **Use `gen_retryscope()`** — generates correct XAML deterministically.

Use empty condition when you just want to retry on exception without validating a result.

**Best practice — Navigation retry with NCheckState condition:**

When retrying UI navigation, use `NCheckState` inside the Condition to verify the target page actually loaded. This is better than empty condition because it catches silent navigation failures (page didn't load but no exception thrown).

**⛔ The element in NCheckState must be the FIRST element the next workflow will interact with** (click, type into, get text, etc.) — NOT a generic page title or header. This guarantees the page is ready for the next action. Example: if the next step types into a search box, check for that search box; if the next step clicks an "Update" button, check for that button.
→ **Use `gen_ncheckstate()`** — generates correct XAML deterministically.

Use this pattern for: navigation retries, login verification (check for first dashboard element to interact with), page load confirmations. The NCheckState returns True if the element is found (success = stop retrying) or False if not found (keep retrying). Always target the first element the next workflow step will interact with — never a generic header or page title.

Common pattern — RetryScope wrapping TryCatch:
→ **Use `gen_retryscope()` with `gen_try_catch()` nested inside** — generates correct XAML deterministically.


**⚠️ ALWAYS wrap API-interacting activities in RetryScope.** Any activity that makes a network/API call can fail due to transient issues (timeouts, rate limits, DNS, connectivity). This includes:
- `NetHttpRequest` (HTTP Request) — REST/SOAP calls
- `AddQueueItem` — Orchestrator API behind the scenes
- `GetQueueItem` / `SetTransactionStatus` — Orchestrator API
- `GetRobotAsset` / `GetRobotCredential` — Orchestrator API
- `QueryEntityRecords` (Data Service) — Orchestrator API
- Any Integration Service activity — external API calls
- `SendMail` / `GetMailMessages` — SMTP/IMAP connections

Use empty condition (retry on any exception) for simple cases, or add a Condition with `CheckTrue` when you need to validate the response. Default: `NumberOfRetries="3"`, `RetryInterval` omitted (Studio default). If you need custom intervals for external APIs with rate limits, set manually in Studio.

**Exception: Activities already inside REFramework's Process.xaml** — the framework's own retry mechanism (via `SetTransactionStatus` → Retry) handles transaction-level retries. But if `Process.xaml` makes multiple API calls, each individual call should still be wrapped in its own RetryScope to handle transient failures within a single transaction attempt.
