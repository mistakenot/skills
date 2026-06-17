# Eval Report

- **Case**: calculator-cli
- **Model**: claude-sonnet-4-20250514
- **Skill version**: 0c9298f
- **Timestamp**: 2026-06-17 09:41:15 UTC

- **baseline cost**: $0.0000
- **withskill cost**: $0.0006
- **Skill invoked**: **NO** (skill was available but not triggered)

## Mechanical Scorecard

| Check | Baseline | With-skill |
|-------|----------|------------|
| Testing doc | False | False |
| Verify entry point | False | False |
| Tests directory | False | False |
| Test command (T2) | absent | absent |

## Gotcha Probes

Mechanical anti-pattern checks (a defect when triggered). See `graders/gotchas.md`.

| Gotcha | Baseline | With-skill |
|--------|----------|------------|
| G1 Fake PBT (claims properties, no PBT library) | no | no |
| G2 Over-prescribed property layer | no | no |
| G3 Randomness without determinism | n/a | n/a |

## Grader Scores

**grader: parse failed**

Raw grader output:

```
{"type":"result","subtype":"success","is_error":true,"api_error_status":404,"duration_ms":1286,"duration_api_ms":1275,"num_turns":1,"result":"There's an issue with the selected model (claude-sonnet-4-20250514). It may not exist or you may not have access to it. Run --model to pick a different model.","stop_reason":"stop_sequence","session_id":"7b4c5363-3c07-4eda-89a1-a1507b0313b5","total_cost_usd":0.0013189999999999999,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_tool_use":{"web_search_requests":0,"web_fetch_requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"claude-haiku-4-5-20251001":{"inputTokens":1254,"outputTokens":13,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0.0013189999999999999,"contextWindow":200000,"maxOutputTokens":32000}},"permission_denials":[],"terminal_reason":"completed","fast_mode_state":"off","uuid":"d20dd1b1-18dd-4095-8000-f0cb26919afd"}
```

## Human verdict

<!-- Write your assessment here after reviewing the run artifacts. -->
