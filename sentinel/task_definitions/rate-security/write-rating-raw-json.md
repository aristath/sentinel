Produce the final long-term structural rating for `{{symbol}}` ({{name}}) based on the analysis below.

Rate the **5-10 year structural outlook** on a 0.0 to 1.0 scale. Disregard current pricing, current valuation, current quarterly performance, and short-term sentiment entirely.

Scale:
- 0.0 - 0.3: the underlying exposure or investment thesis is in structural decline, faces existential risks, or is becoming obsolete. The long-term trajectory points down regardless of current results.
- 0.4 - 0.6: average outlook with significant headwinds, weakening structural drivers, intense competition, or an uncertain long-term thesis.
- 0.7 - 0.8: strong outlook, durable advantages, a clear long-term path, and manageable structural risks. The long-term thesis is defensible.
- 0.9 - 1.0: dominant or essential exposure with exceptional long-term tailwinds, unusually durable demand, or visible multi-decade compounding.

As an example, if Huawei has weak current performance but excellent structural prospects, that would justify a 0.7-0.9 rating. Conversely, a company or ETF with strong current performance but eroding structural moats belongs lower. Apply equivalent reasoning to other security types by evaluating the future trajectory of the exposure they provide. The rating is about TRAJECTORY, not current state.

Analysis to base the rating on:

{{analysis}}

Previous validator result (if this is a retry):

{{validatorFeedback}}

Write a single JSON object to this exact file. Use the `write_file` tool with the JSON object as the file content:

`{{ratingRawPath}}`

The JSON object must contain exactly these three keys and no others:

```
{
  "symbol": "{{symbol}}",
  "rating": 0.0,
  "rationale": "..."
}
```

- `rating` must be a number from 0.0 to 1.0.
- `rationale` must be one string containing 2-3 short paragraphs. Use it to state the main durable positives, the main structural risks, and why the final rating lands where it does. Do not invent additional keys (`risks`, `bull_case`, `bear_case`, `verdict`, `conclusion`, `limitations`). Put everything inside the single `rationale` string.

If this is a retry, fix the previous candidate using the validator's error and schema feedback above.

After writing, respond with a short confirmation only.
