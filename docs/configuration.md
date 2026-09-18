# Configuration

Sentinel stores runtime settings in the SQLite `settings` table. `Settings.all()`
merges stored values over `DEFAULTS` from `sentinel/settings.py`. The web UI and
`/api/settings` expose this merged view.

Most settings can be updated with:

```http
PUT /api/settings/{key}
Content-Type: application/json

{"value": "new value"}
```

The multi-setting `PUT /api/settings` endpoint is limited to the validated
strategy-tuning form documented in [Settings API](api/settings.md).

## Core portfolio settings

| Key | Default | Purpose |
|---|---:|---|
| `trading_mode` | `research` | `research` calculates only; `live` permits broker orders |
| `transaction_fee_fixed` | `2.0` | Fixed estimated fee per trade in EUR |
| `transaction_fee_percent` | `0.2` | Percentage fee estimate |
| `max_position_pct` | `25` | Hard per-security allocation cap |
| `min_position_pct` | `2` | Minimum meaningful position size |
| `min_trade_value` | `400.0` | Minimum practical trade value in EUR |
| `min_cash_buffer` | `0.005` | Cash ratio reserved from buy budgets |
| `target_cash_pct` | `0` | Long-term target cash allocation |
| `simulated_cash_eur` | `null` | Research-mode cash override; `null` uses real cash |
| `rebalance_threshold_pct` | `5` | Portfolio-alignment threshold |
| `performance_benchmark_symbol` | `VWCE.EU` | Investable benchmark overlaid on portfolio performance |
| `max_dividend_reinvestment_boost` | `0.15` | Maximum opportunity-score boost from undeployed dividends |
| `ui_securities_table_columns` | seven default columns | Persisted securities-table column selection |

The default column array is `price`, `security`, `value`, `pnl`, `ideal`,
`plan`, and `trade`.

## Broker and Freedom24 settings

| Key | Default | Purpose |
|---|---|---|
| `tradernet_api_key` | empty | TraderNet API key |
| `tradernet_api_secret` | empty | TraderNet API secret |
| `freedom24_login` | empty | Freedom24 web login for PRAAMS structure scraping |
| `freedom24_password` | empty | Freedom24 web password |

The Freedom24 credentials are not required for normal broker sync. They are
only used by `/api/portfolio/structure`, an unstable web-scraping integration.

## Strategy settings

| Key | Default | Purpose |
|---|---:|---|
| `strategy_min_opp_score` | `0.55` | Score dividing core and opportunity timing classifications |
| `strategy_ideal_qualifying_threshold` | `0.65` | Minimum AI research rating for a positive model target |
| `strategy_entry_t1_dd` | `-0.10` | First drawdown tranche threshold |
| `strategy_entry_t2_dd` | `-0.16` | Second drawdown tranche threshold |
| `strategy_entry_t3_dd` | `-0.22` | Third drawdown tranche threshold |
| `strategy_entry_memory_days` | `45` | Recent-dip memory window |
| `strategy_memory_max_boost` | `0.12` | Maximum opportunity boost from recent-dip memory |
| `strategy_opportunity_addon_threshold` | `0.75` | Score required for additional opportunity accumulation |
| `strategy_max_opportunity_buys_per_cycle` | `1` | Total opportunity buys permitted in a planning cycle |
| `strategy_max_new_opportunity_buys_per_cycle` | `1` | New opportunity positions permitted in a cycle |
| `strategy_lot_standard_max_pct` | `0.08` | Maximum portfolio fraction for a standard ticket classification |
| `strategy_lot_coarse_max_pct` | `0.30` | Maximum portfolio fraction for a coarse ticket classification |
| `strategy_coarse_max_new_lots_per_cycle` | `1` | New coarse lots permitted per cycle |
| `cooldown_enabled` | `true` | Master switch for recent-trade cool-off rules |
| `strategy_opportunity_cooloff_days` | `7` | Opportunity-side repeat-trade cool-off |
| `strategy_core_cooloff_days` | `21` | Core-side repeat-trade cool-off |
| `strategy_same_side_cooloff_days` | `15` | Same-direction trade cool-off |
| `strategy_rotation_time_stop_days` | `90` | Opportunity rotation time-stop |
| `strategy_core_timing_min_score` | `0.30` | Minimum normally timed core-buy opportunity score |
| `strategy_core_timing_min_dip_score` | `0.20` | Minimum normally timed core-buy dip score |
| `strategy_fallback_wait_days` | `30` | Durable wait before one convergence fallback buy |
| `strategy_max_funding_sells_per_cycle` | `2` | Funding sells permitted per planning cycle |
| `strategy_max_funding_turnover_pct` | `0.12` | Maximum portfolio turnover from funding sells |
| `strategy_funding_conviction_bias` | `1.0` | Conviction influence when choosing funding sells |

## AI research rating settings

| Key | Default | Purpose |
|---|---:|---|
| `ai_research_multiplier_strength` | `5.0` | Strength of relative AI ratings in target weighting |
| `ai_research_multiplier_decay_factor` | `0.90` | Fraction of distance from neutral retained per decay step |
| `ai_research_multiplier_decay_interval_days` | `7` | Minimum age before another decay step |

Security ratings range from `0` (avoid) through `0.5` (neutral) to `1`
(prefer). The fixed `decay:ai_research_multipliers` job moves stale stored
ratings toward neutral.

## Forecasting settings

| Key | Default | Purpose |
|---|---:|---|
| `forecasting_enabled` | `true` | Enables scheduled forecast generation/use |
| `forecasting_service_url` | `http://127.0.0.1:8010` | Separate forecasting service base URL |
| `forecasting_provider` | `toto2` | Provider identifier recorded with runs |
| `forecasting_model_id` | `Datadog/Toto-2.0-1B` | Model identifier or local model path |
| `forecasting_horizon_weeks` | `4` | Forecast horizon |
| `forecasting_context_weeks` | `520` | Maximum historical context |
| `forecasting_min_history_weeks` | `104` | Minimum history required for a series |
| `forecasting_max_group_variates` | `32` | Maximum related series in a grouped request |
| `forecasting_stale_after_days` | `21` | Age after which a forecast is stale |
| `forecasting_max_missing_ratio` | `0.25` | Maximum missing-data ratio accepted |
| `forecasting_score_max_age_days` | `14` | Maximum forecast-score age used by planner |
| `forecasting_timing_weight` | `0.15` | Bounded forecast influence on opportunity timing |
| `forecasting_request_timeout_seconds` | `840` | Service request timeout |

See [Forecasting](forecasting.md) for process and failure behavior.

## AI task runtime settings

### LLM

| Key | Default | Purpose |
|---|---|---|
| `ai_llm_base_url` | `http://127.0.0.1:8080/v1` | OpenAI-compatible inference base URL |
| `ai_llm_api_key` | `local` | Bearer token sent to the inference service |
| `ai_llm_model` | `qwen3.8-27b-udq4kxl` | Default model identifier |
| `ai_llm_timeout_seconds` | `3600` | LLM request timeout |
| `ai_max_tool_calls` | `40` | Per-prompt tool-call limit |
| `ai_max_tool_loop_iterations` | `40` | Per-prompt tool-loop iteration limit |

### Search and summarization

| Key | Default | Purpose |
|---|---|---|
| `ai_searxng_base_url` | `http://127.0.0.1:8888` | SearXNG JSON search service |
| `ai_browser_search_base_url` | `http://127.0.0.1:8891` | Browser-search service |
| `ai_url_summarizer_base_url` | `http://127.0.0.1:8890` | URL fetch/summarization service |

These are service defaults, not Vite or Sentinel HTTP ports.

### Research memory

| Key | Default | Purpose |
|---|---|---|
| `ai_pg_host` | `127.0.0.1` | PostgreSQL host |
| `ai_pg_port` | `5432` | PostgreSQL port |
| `ai_pg_database` | `clara_memories` | Database containing mem0-compatible tables |
| `ai_pg_user` | `clara` | Database user |
| `ai_pg_password` | environment/empty | Database password |
| `ai_embed_base_url` | `http://127.0.0.1:18200/v1` | OpenAI-compatible embeddings endpoint |
| `ai_embed_model` | `ibm-granite/granite-embedding-311m-multilingual-r2` | Embedding model |
| `ai_embed_dims` | `768` | Stored vector dimension |
| `ai_memory_user_id` | `clara` | mem0-compatible user identity |
| `ai_memory_collection` | `clara_memories` | pgvector collection/table identity |
| `ai_stale_after_days` | `7` | Research-unit staleness window |
| `ai_dedup_similarity_threshold` | `0.96` | Similarity at which a memory is reinforced/skipped instead of inserted |

The password can be supplied by `SENTINEL_AI_PG_PASSWORD`; the environment value
becomes the default when the process imports `sentinel.settings`.

## LED and backup settings

| Key | Default | Purpose |
|---|---:|---|
| `led_display_enabled` | `false` | Starts the optional Sentinel LED controller |
| `led_brightness` | `200` | Global LED brightness, 0–255 |
| `r2_account_id` | empty | Cloudflare R2 account ID |
| `r2_access_key` | empty | R2 access key |
| `r2_secret_key` | empty | R2 secret key |
| `r2_bucket_name` | empty | R2 bucket |
| `r2_backup_retention_days` | `30` | Remote backup retention |

## Process environment variables

These variables are outside the database setting system:

| Variable | Default | Consumer |
|---|---|---|
| `SENTINEL_DATA_DIR` | repository `data/` | SQLite and local backups |
| `SENTINEL_HOME` | `~/.sentinel` | Editable tasks and artifacts |
| `SENTINEL_BASE_URL` | derived from `main.py --port` | Task scripts calling Sentinel |
| `SENTINEL_AI_PG_PASSWORD` | empty | Initial AI memory password default |
| `SENTINEL_TARGET` | `aristath@clara.local` | Manual deploy script SSH target |
| `SENTINEL_REPO_DIR` | `/var/home/aristath/sentinel` | Auto-deploy repository |
| `SENTINEL_BRANCH` | `main` | Auto-deploy branch |
| `FORECASTING_PROVIDER` | `toto2` | Forecast service default provider |
| `FORECASTING_MODEL_ID` | `Datadog/Toto-2.0-1B` | Forecast service default model |

The folder-task runtime also injects `SENTINEL_TASKS_HOME`,
`SENTINEL_APP_ROOT`, `SENTINEL_PYTHON`, `SENTINEL_URL_SUMMARIZER_BASE_URL`,
`TASK_CWD`, and task input variables into child processes. These are runtime
contracts, not operator configuration; see [Tasks](tasks.md).

The Arduino application supports `SENTINEL_API_URL`, `HOST_IP`, and the
`LED_*` variables documented in [Hardware LED](hardware-led.md).

## Secret handling

The settings API returns the merged settings object, including stored secrets.
Sentinel assumes a trusted local network and currently has no authentication
layer. Do not expose port `8000` publicly, place it behind an authenticated
gateway, or forward it to an untrusted network.

Do not commit real credentials to source, service templates, examples, or
generated frontend assets.
