# Instruments details

**Instrument types and type name:**

| Instrument type | Type name
|---|---|---|---|
| 2 | Bonds
| 11 | Bond Yield
| 6 | Currency
| 14 | Currency Swap
| 3 | Futures
| 5 | Indices
| 7 | Night trading
| 4 | Options
| 17 | Option exercise
| 16 | Option expiration
| 20 | Futures expiration
| 8 | REPO Securities
| 9 | Direct REPO
| 10 | Repo with netting
| 18 | Equity swap
| 1 | Stocks
| 19 | Structured products

#### Type combination examples

| instr_type_c | instr_kind_c | instr_type | instr_kind
| 1 | 1 | Share | ordinary stock
| 1 | 2 | Share | preferred share
| 1 | 7 | Share | fund/ ETF
| 1 | 10 | Share | depositary receipt
| 1 | 14 | Share | crypto shares
| 2 | 1 | Bonds | bond
| 2 | 3 | Bonds | bond
| 2 | 9 | Bonds | eurobonds
| 2 | 15 | Bonds | bond
| 3 | 1 | Futures | futures
| 3 | 5 | Futures | Deliverable Futures contract
| 3 | 6 | Futures | Futures settlement
| 4 | 1 | Options | option
| 4 | 5 | Options | settlement option
| 4 | 7 | Options | delivery option
| 5 | 1 | Indices | index
| 5 | 6 | Indices | index contract
| 6 | 1 | Cash | currency
| 6 | 8 | Cash | cryptocurrency
| 7 | 1 | Foreign exchange contract | currency contract
| 7 | 2 | Foreign exchange contract | currency swap
| 8 | 1 | REPO Securities | Autorepo
| 9 | 1 | Direct repo virtual position | Direct repo
| 10 | 1 | Repo with netting | Repo Netting
| 10 | 9 | Repo with netting | unknown
| 11 | 13 | Bond Yield | yield of eurobonds
