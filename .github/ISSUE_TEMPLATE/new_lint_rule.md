---
name: New lint rule
about: Propose a lint rule for an LLM hallucination or error pattern
labels: lint rule
---

## Hallucination pattern

Describe what LLMs get wrong when generating this XAML.

## Example bad XAML

```xml
<!-- Paste the broken/incorrect XAML output -->
```

## Expected correct XAML

```xml
<!-- Paste what the XAML should look like -->
```

## Suggested severity

- [ ] ERROR - Studio crash or compile failure
- [ ] WARN - Runtime failure or silent data loss
- [ ] INFO - Best practice violation

## Studio behavior

What happens when the bad XAML is opened in UiPath Studio (crash, compile error, runtime failure, etc.).
