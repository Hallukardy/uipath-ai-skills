# HTTP, REST, JSON, and XML Activities

HTTP request activities plus JSON/XML serialization and query helpers from `UiPath.WebAPI.Activities`. Two namespaces appear:
- `ui:` → most activities (`DeserializeJson`, `DeserializeJsonArray`, `DeserializeXml`, `GetNodes`, `GetXMLNodes`, `GetXMLNodeAttributes`, `ExecuteXPath`, `HttpClient`)
- `uwah:` → `NetHttpRequest` (clr-namespace `UiPath.Web.Activities.Http`)
- `uwaj:` → `SerializeJson` (clr-namespace `UiPath.Web.Activities.JSON`)

## Contents
- [When to use](#when-to-use)
- [NetHttpRequest (preferred)](#nethttprequest)
- [HttpClient (legacy — avoid)](#httpclient-legacy)
- [JSON serialization](#json-serialization)
- [XML serialization and querying](#xml-serialization-and-querying)
- [Common pitfalls](#common-pitfalls)

## When to use

For REST/SOAP/HTTP APIs:
- **`NetHttpRequest`** (first choice) — structured response, built-in retry, OAuth1/OAuth2/Windows auth, file upload/download, explicit proxy settings. Do NOT wrap in `RetryScope` — its retry is built in via `RetryCount` / `RetryPolicyType`.
- **`HttpClient`** (legacy) — only for migrating old workflows. Missing structured retry; weaker response-shape contract. When porting legacy workflows, default to swapping for `NetHttpRequest`.

For Orchestrator assets/credentials/queues: see `xaml-orchestrator.md` (those are different activities, not HTTP).

For JSON/XML shaping inside a workflow — post-response or pre-request — use the Serialize/Deserialize family below. LINQ-to-XML / LINQ-to-JSON expressions inside `Assign` also work for trivial lookups; use the activities when you want the transform on the canvas for visibility.

## NetHttpRequest
→ **Use `gen_net_http_request()`** — generates correct XAML deterministically.

Modern HTTP request activity. Returns an `HttpResponseSummary` with status code, headers, and body.

**Must have:**
- `Method` — `GET` / `POST` / `PUT` / `PATCH` / `DELETE`
- `RequestUrl` — full URL (from Config, never hardcoded)
- `Result` — `HttpResponseSummary` output variable

**Retry:** `RetryCount`, `RetryPolicyType` (`Basic` / `Exponential`), `InitialDelay`, `Multiplier`, `MaxRetryAfterDelay`, `UseJitter`, `RetryStatusCodes`. Do NOT wrap in `RetryScope`.

**Body:**
- `TextPayload` + `TextPayloadContentType` (default `application/json`) for JSON/XML/text
- `BinaryPayload` for binary uploads
- `FormData` / `FormDataParts` for multipart form uploads
- `FilePath` or `ResourceFiles` for file attachments

**Auth:** `AuthenticationType`: `None` | `Basic` | `OAuth1` | `OAuth2` | `WindowsIntegrated`. Supply corresponding `BasicAuthUsername`/`BasicAuthSecurePassword`, `OAuthToken`, or `UseOsNegotiatedAuthCredentials`. Pull credentials from Orchestrator via `GetRobotCredential`, not hardcoded.

**Response handling:**
- `SaveResponseAsFile="True"` + `OutputFileName` streams to disk instead of loading in memory
- `SaveRawRequestResponse="True"` logs wire traffic (use for debugging, turn off in production)

## HttpClient (legacy)

Legacy HTTP activity kept for backward compatibility. Has 5 dictionary child elements (Attachments, Cookies, Headers, Parameters, UrlSegments) that the data-driven generator emits as empty templates by default.

**Prefer `NetHttpRequest` for new work.** The only reason to emit `HttpClient` is when porting an existing workflow where replacing it is out of scope.

If you must emit it, use `gen_http_client` via annotation fallback:
```json
{
  "gen": "httpclient",
  "args": {
    "endpoint_variable": "strApiUrl",
    "method": "GET",
    "authentication_type": "Basic",
    "username_variable": "cred_User",
    "password_variable": "cred_Pass",
    "result_variable": "strBody",
    "status_code_variable": "intStatus"
  }
}
```

Requires `xmlns:scg="clr-namespace:System.Collections.Generic;assembly=System.Private.CoreLib"` at the XAML root for the dictionary children.

## JSON serialization

### SerializeJson
Converts a `JObject` / `JArray` / any object graph to a JSON string.

```json
{
  "gen": "serializejson",
  "args": {
    "input_object_variable": "jo_Payload",
    "output_variable": "strJson"
  }
}
```

Namespace `uwaj:` — distinct from `ui:`.

### DeserializeJson
Parses a JSON string into a `JObject` (default `x:TypeArguments="njl:JObject"`).

```json
{
  "gen": "deserialize_json",
  "args": {
    "json_string_variable": "strResponseBody",
    "output_variable": "jo_Response"
  }
}
```

For custom POCO types, override `type_argument` in the spec.

### DeserializeJsonArray
Parses a JSON string into a `JArray`.

```json
{
  "gen": "deserializejsonarray",
  "args": {
    "json_string_variable": "strItems",
    "output_variable": "ja_Items"
  }
}
```

Once you have the `JArray`, iterate with `ForEach` (type `njl:JToken`) to access each element.

## XML serialization and querying

### DeserializeXml
Parses an XML string into a `System.Xml.Linq.XDocument`.

```json
{ "gen": "deserializexml", "args": { "xml_string_variable": "strXml", "output_variable": "xd_Doc" } }
```

### GetNodes / GetXMLNodes
Return `IEnumerable<XElement>` matching an XPath. Both accept either `XMLString` or `ExistingXML` (parsed XDocument) — pass exactly one; leave the other unset.

```json
{
  "gen": "getnodes",
  "args": {
    "existing_xml_variable": "xd_Doc",
    "output_variable": "lst_Items"
  }
}
```

`GetNodes` vs `GetXMLNodes` semantics are subtly different — confirm against Studio docs for your scenario. When in doubt, prefer LINQ-to-XML expressions inside an `Assign` (`xd_Doc.Descendants("item")`).

### GetXMLNodeAttributes
Returns the `IEnumerable<XAttribute>` collection of a single `XElement`.

```json
{
  "gen": "getxmlnodeattributes",
  "args": {
    "existing_xml_node_variable": "elItem",
    "output_variable": "attrs"
  }
}
```

### ExecuteXPath
Evaluates an XPath expression against an XML string or parsed XDocument. Returns the string value of the match.

```json
{
  "gen": "executexpath",
  "args": {
    "xml_string_variable": "strXml",
    "xpath_expression": "//customer[@id='42']/name/text()"
  }
}
```

Pass exactly one of `xml_string_variable` or `existing_xml_variable`. Mutual-exclusion is not yet enforced by the generator — caller responsibility.

## Common pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Wrapping NetHttpRequest in RetryScope | Double retry, incorrect jitter behavior | Use built-in `RetryCount` / `RetryPolicyType` on NetHttpRequest |
| Hardcoding URLs or tokens | lint warning, security review fail | URLs from Config.xlsx; credentials from Orchestrator via `GetRobotCredential` |
| Passing both `XMLString` and `ExistingXML` | Studio error / undefined behavior | Provide exactly one; leave the other unset |
| SerializeJson emitting `uwaj:` without namespace | XAML fails to compile | `scripts/generate_workflow.py` adds `xmlns:uwaj` automatically; if hand-editing, add it to the root |
| DeserializeJson with wrong `x:TypeArguments` | InvalidCastException at runtime | Match generic to actual JSON shape — `JObject` for `{...}`, `JArray` for `[...]`, `JToken` when uncertain |
| Using HttpClient for new work | tech debt, harder to migrate later | Use NetHttpRequest from day one |
| AcceptFormat / BodyFormat mismatch on NetHttpRequest | 415 / 406 from API | Set both; default `application/json` is common but not universal |
| OAuth token stored in variable as plaintext | appears in logs | Use `SecureString` and `GetRobotCredential`; disable `SaveRawRequestResponse` in prod |

## Template selection

These activities have no golden templates — emission is via hand-written `gen_net_http_request` (for NetHttpRequest) and data-driven generators (for everything else in this file). Reference harvested shapes under `references/studio-ground-truth/UiPath.WebAPI.Activities/2.4/`.
