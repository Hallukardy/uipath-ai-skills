# Testing Activities

Assertions, mocking, comparison, and test-data-queue activities from `UiPath.Testing.Activities`. Namespace prefix: `uta:` (clr-namespace `UiPath.Testing.Activities`).

## Contents
- [When to use](#when-to-use)
- [Assertions](#assertions)
- [Mocking](#mocking)
- [Test data queues](#test-data-queues)
- [File and text comparison](#file-and-text-comparison)
- [Synthetic data](#synthetic-data)
- [Common pitfalls](#common-pitfalls)

## When to use

These activities power UiPath's Test Manager / Test Suite workflows. Reach for them when:
- The PDD specifies acceptance tests or regression tests
- You're building a test case `.xaml` (file lives under `Tests/` folder in the project)
- A workflow needs deterministic synthetic inputs (random names, IDs, dates)

For production automation logic, prefer:
- Data validation → `xaml-data.md` (FilterDataTable, compare DataRows directly)
- Error handling → `xaml-error-handling.md` (TryCatch, Throw)
- Conditional branching → `xaml-control-flow.md` (If, IfElseIfV2)

Testing activities are about **verifying** and **simulating**, not driving the business process.

## Assertions

### VerifyExpression
Asserts a single boolean expression. Failure stops or continues based on `ContinueOnFailure`.

```json
{
  "gen": "verifyexpression",
  "args": {
    "expression": "intRecords > 0",
    "result_variable": "boolRecordsExist",
    "continue_on_failure": "True"
  }
}
```

`result_variable` receives `True`/`False` so downstream activities can branch on the outcome even when `ContinueOnFailure="True"`.

### VerifyExpressionWithOperator
Asserts a comparison between two expressions using a named operator (`Equal`, `NotEqual`, `GreaterThan`, `LessThan`, `GreaterThanOrEqual`, `LessThanOrEqual`). Clearer diagnostics than `VerifyExpression` when the assertion fails because the message names both operands.

### VerifyRange
Asserts that a numeric expression falls inside `[MinValue, MaxValue]`.

### VerifyControlAttribute
Asserts that a UI control's attribute matches an expected value. Combines UIAutomation element targeting with an equality check. Useful inside test cases that interact with real apps.

## Mocking

### MockActivity
Wraps a child activity and substitutes a deterministic output for testing. At runtime in Test Manager, the wrapped activity does NOT execute — the mock's `MockOutput` is assigned directly to `Result`.

Use when:
- Testing a workflow that calls a real API / database / Orchestrator, and you need to run the test without that dependency
- You want to force a specific error path (mock returns the error case)

Do NOT leave `MockActivity` in production runtime paths — it silently skips the wrapped activity outside Test Manager context.

## Test data queues

Test Manager stores structured test inputs in Test Data Queues (distinct from production Orchestrator queues). These activities feed synthetic or curated data rows into a test case.

- **`BulkAddTestDataQueue`** — push many rows from a DataTable
- **`NewAddTestDataQueueItem`** — push a single row from a dictionary
- **`GetTestDataQueueItem`** — fetch the next row for the current test iteration
- **`GetTestDataQueueItems`** — fetch a batch
- **`DeleteTestDataQueueItems`** — clear queue between runs

Use these when the test case is **data-driven** — i.e., "run this test once per row in the queue." Test Manager orchestrates the iteration.

## File and text comparison

### CompareText
Asserts string equality, optionally ignoring whitespace, case, or specific characters. Richer than a VB `=` comparison for human-readable diff output when it fails.

### ComparePdfDocuments
Diffs two PDF files, optionally excluding regions (by coordinates or by matching a comparison rule). Returns details of each mismatched region. Use when comparing "before/after" PDF artifacts — receipts, invoices, generated reports.

### CreateComparisonRule
Builds a reusable comparison rule (ignored regions, tolerance thresholds) for feeding into `ComparePdfDocuments`. Define once per test suite, reuse across cases.

### AttachDocument
Attaches a file to the current test result for later review. Useful when `ComparePdfDocuments` fails — attach both the expected and actual PDF so a reviewer can diff visually.

## Synthetic data

Deterministic random generators for test inputs. Each accepts a `Seed` for reproducibility — same seed produces the same value every run, so failing tests stay failing until fixed.

- **`RandomString`** — string of given length / character class
- **`RandomNumber`** — integer in range
- **`RandomDate`** — date in range, optional weekday constraints
- **`RandomValue`** — pick from an enumerated list
- **`GivenName` / `LastName` / `Address`** — locale-aware person/address names. Useful for PII-safe test fixtures.

**Always seed when the test is expected to be deterministic.** An unseeded `RandomNumber` makes the test non-reproducible — the next run may pass where the previous failed.

## Common pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| `MockActivity` left in production workflow | activity is silently skipped | Scope mocks to `Tests/` .xaml files only; never `InvokeWorkflowFile` a mock-bearing test from prod Main |
| Unseeded random values in assertion | flaky tests | Pass a fixed `Seed` to Random* activities |
| `ContinueOnFailure="False"` inside a loop | one failure aborts all iterations | Set `ContinueOnFailure="True"` when iterating, aggregate failures, assert in summary after the loop |
| Confusing Test Data Queue with production queue | test data leaks into prod queue | Test data activities target Test Manager queues; production uses `AddQueueItem`/`GetQueueItem` (see `xaml-orchestrator.md`) |
| `ComparePdfDocuments` with no tolerance / excluded regions | every run fails on timestamps/dynamic content | Use `CreateComparisonRule` to ignore date/time regions |
| `VerifyExpression` expression using `=` instead of `==` on non-VB context | unexpected assignment semantics | Expressions are VB; use `=` for equality. For C#, use `==` (specify via language setting) |
| Testing activities in a workflow that's never invoked by Test Manager | activities never execute | Test activities only run under Test Manager execution context — put them in `Tests/` workflows, not in `Main.xaml` |

## Template selection

No golden templates for testing activities yet. Emission is via the data-driven `gen_from_annotation` engine using entries in `references/annotations/testing.json`. Reference harvested shapes under `references/studio-ground-truth/UiPath.Testing.Activities/25.10/`.
