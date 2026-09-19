You are assessing these securities for a 5-10 year portfolio allocation. The goal is to decide which securities to buy more of and which to sell. This is a relative comparison — you're deciding where the money should go.

The scale is 0.0 to 1.0 and reflects **structural trajectory over 5-10 years**, not current performance or valuation:
- 0.0 - 0.3: the underlying exposure or thesis is in structural decline, faces existential risks, or is becoming obsolete
- 0.3 - 0.6: average outlook, significant headwinds, weakening structural drivers, or an uncertain thesis
- 0.6 - 0.9: strong outlook, durable advantages, a clear long-term path, and manageable risks
- 0.9 - 1.0: dominant or essential exposure with exceptional tailwinds or visible multi-decade compounding

For an operating-company example, Huawei's weak current results should not obscure its excellent structural prospects, so it belongs high. Conversely, an operating company with strong current results but eroding structural moats belongs lower. Apply equivalent reasoning to every security type by judging the future trajectory of the exposure it provides. The signal is trajectory, not current state.

Below are concise assessments of each security in the portfolio. Each assessment starts with metadata:
- `symbol`: copy this exact value into the JSON `symbol` field.
- `name`: use this to understand which security and underlying exposure the assessment describes.

Read all assessments, then rate them relative to each other.
DO NOT rate each security in isolation. We need to account for the entire global financial and socioeconomic situation as described in the assessments below, and then rate the securities relative to the entire portfolio, taking into account NOT where the world is now, but where we think the world will be 5-10 years from now. Securities should be viewed as part of a portfolio, not as part of an industry or country etc. We rate securities in the portfolio against other securities in the same portfolio, not against securities in their industry etc.

{{compiledText}}

Previous validation errors, if any:

{{validationFeedback}}

Write a single JSON object to this exact file. Use the `write_file` tool with the JSON object as the file content:

`{{ratingsRawPath}}`

The JSON object must use this exact shape:

```json
{
  "ratings": [
    {
      "symbol": "SYMBOL",
      "rating": 0.85,
      "rationale": "Brief reason in one sentence."
    }
  ]
}
```

List all {{count}} securities exactly once. Use the exact `symbol` values from the assessment metadata. Ratings must be numbers from 0.0 to 1.0. Be honest about the differences — when two securities provide comparable exposure, the structurally stronger one should rate higher.

If this is a retry, fix the previous candidate using the validator feedback above.

After writing, respond with a short confirmation only.
