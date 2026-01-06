# Tradernet SDK Analysis for Go Port

## Source Code Reference
Based on analysis of: https://github.com/kutsevol/tradernet-api

## Architecture Overview

The Python SDK uses a **dual-client architecture** (V1 and V2) with different authentication methods:

### Client V1
- **Authentication**: MD5 HMAC signature
- **Endpoint**: `https://tradernet.ru/api`
- **Request Format**: JSON in form data (`{"q": <json>}`)
- **Used for**: `get_ticker_info` (legacy endpoint)

### Client V2
- **Authentication**: SHA256 HMAC signature
- **Endpoint**: `https://tradernet.ru/api/v2/cmd/{command}`
- **Request Format**: URL-encoded form data with nested bracket notation
- **Used for**: All modern commands (orders, stop orders, etc.)

## Key Implementation Details

### 1. Authentication & Request Signing

#### V1 Authentication
```python
# MD5 HMAC of secret key (static)
sig = hmac.new(key=secret_key.encode(), digestmod="MD5").hexdigest()

# Request structure:
{
    "cmd": "command_name",
    "params": {...},
    "nonce": int(time.time() * 10000),  # milliseconds * 10
    "sig": "<md5_hex>"
}
```

#### V2 Authentication
```python
# SHA256 HMAC of query string
query_string = convert_to_query_string(data.dict())  # Sorted keys
signature = hmac.new(
    key=secret_key.encode(),
    msg=query_string.encode("utf-8"),
    digestmod=hashlib.sha256
).hexdigest()

# Header: X-NtApi-Sig: <sha256_hex>
# Request: URL-encoded form with nested brackets
```

**Critical**: V2 uses **sorted keys** for signature generation!

### 2. URL Encoding (V2)

V2 uses a **custom URL encoding** with nested bracket notation:

```python
# Input: {"params": {"ticker": "AAPL", "sup": False}}
# Output: "params[ticker]=AAPL&params[sup]=False"
```

**Implementation**:
- Sorts all keys before encoding
- Handles nested dictionaries recursively
- Uses bracket notation: `key[subkey]=value`

### 3. Nonce Generation

```python
nonce = int(time.time() * 10000)  # Current time in milliseconds * 10
```

**Important**: Uses milliseconds multiplied by 10, not standard Unix timestamp!

### 4. Command Structure

Commands are defined as enum values:
- `send_order` → `"putTradeOrder"`
- `delete_order` → `"delTradeOrder"`
- `get_orders` → `"getNotifyOrderJson"`
- `get_ticker_info` → `"getSecurityInfo"`
- `set_stop_order` → `"putStopLoss"`

## Edge Cases & Validations

### 1. SendOrder Validation

The SDK implements **complex validation logic** for order parameters:

#### Action ID Calculation
```python
# Combines side + margin into action_id
sides = {"buy": 1, "sell": 3}
action_id = sides[side.lower()] + (1 if margin else 0)

# Valid combinations:
# buy + no margin = 1
# buy + margin = 2
# sell + no margin = 3
# sell + margin = 4
```

**Validation**:
- ✅ Side must be `"buy"` or `"sell"` (case-insensitive)
- ✅ Margin must be boolean
- ❌ Raises `ValueError` if invalid

#### Order Type ID Calculation
```python
# Determines order type from parameters:
# - market_order=True → type_id=1
# - limit_price set → type_id=2
# - stop_price set → type_id=3
# - both limit_price AND stop_price → type_id=4 (stop-limit)
# - None of above → ValueError
```

**Critical**: At least ONE of `market_order`, `limit_price`, or `stop_price` must be set!

#### Expiration ID
```python
expirations = {
    "day": 1,  # Current trading session
    "ext": 2,  # Day + extended hours
    "gtc": 3   # Good-til-cancelled
}
```

**Validation**: Must be one of `"day"`, `"ext"`, or `"gtc"` (case-insensitive)

### 2. Ticker Formatting

**Automatic suffix addition**:
```python
# Input: "AAPL"
# Output: "AAPL.US"
ticker = f"{ticker}.US".upper()
```

**Applied to**:
- `send_order`
- `get_ticker_info`
- `set_stop_order`

### 3. Field Hiding

The SDK uses a **"hidden fields"** pattern to exclude internal fields from API requests:

```python
# Fields marked as "hidden" are excluded from dict() output
# But still used for validation (action_id, order_type_id, expiration_id)
```

**Hidden fields**:
- `side` (converted to `action_id`)
- `margin` (converted to `action_id`)
- `expiry` (converted to `expiration_id`)
- `market_order` (converted to `order_type_id`)

### 4. Request Model Structure

#### V1 Request
```python
{
    "cmd": str,
    "params": dict,
    "nonce": int,
    "sig": str  # MD5 hex
}
```

#### V2 Request
```python
{
    "cmd": str,
    "params": dict,
    "nonce": int,
    "apiKey": str  # API key in body
}
# Plus header: X-NtApi-Sig: <sha256_hex>
```

### 5. Error Handling

The SDK defines custom error messages:
```python
EXCEPTION_MESSAGES = {
    "side_validation": "Side must be one of: `buy` or `sell`",
    "margin_validation": "Margin must be `True` or `False`",
    "expiration_validation": "Expiration must be one of: `day`, `ext` or `gtc`",
    "order_type_validation": "One of the order types must be selected: market_order, limit_price or stop_price"
}
```

## Go Port Recommendations

### 1. Structure

```go
// trader/internal/clients/tradernet/sdk/
//   ├── client.go          // Base client + V1/V2 clients
//   ├── auth.go             // Authentication & signing
//   ├── encoder.go           // URL encoding (V2)
//   ├── models.go           // Request/response models
//   ├── commands.go         // Command definitions
//   └── validation.go       // Parameter validation
```

### 2. Critical Implementation Points

#### Authentication
```go
// V1: MD5 HMAC (static)
sig := hmac.New(md5.New, []byte(secretKey))
sigHex := hex.EncodeToString(sig.Sum(nil))

// V2: SHA256 HMAC of sorted query string
queryString := buildSortedQueryString(data)
sig := hmac.New(sha256.New, []byte(secretKey))
sig.Write([]byte(queryString))
sigHex := hex.EncodeToString(sig.Sum(nil))
```

#### URL Encoding (V2)
```go
// Must match Python's url_form_encoded() behavior
// - Sort all keys
// - Handle nested dicts with brackets
// - Example: params[ticker]=AAPL&params[sup]=false
func urlFormEncode(data map[string]interface{}, rootName string) string {
    // Sort keys
    // Recursively handle nested maps
    // Use bracket notation
}
```

#### Nonce
```go
// Current time in milliseconds * 10
nonce := time.Now().UnixMilli() * 10
```

#### Validation
```go
// Implement all validators from SendOrderModel:
// - ValidateSide(side string) error
// - ValidateMargin(margin bool) error
// - ValidateExpiration(exp string) error
// - ValidateOrderType(market, limit, stop bool) error
// - CalculateActionID(side, margin) int
// - CalculateOrderTypeID(market, limit, stop) int
// - CalculateExpirationID(exp) int
```

### 3. Edge Cases to Handle

1. **Ticker Formatting**: Always append `.US` and uppercase
2. **Field Exclusion**: Don't send hidden/computed fields in request
3. **Sorted Keys**: V2 signature requires sorted keys
4. **Type Conversions**:
   - `bool` → `1`/`0` or `true`/`false` (check API docs)
   - `int` for quantities
   - `float` for prices
5. **Empty Values**: Handle `None`/`nil` appropriately (may need to omit from request)
6. **Error Messages**: Use descriptive errors matching Python SDK

### 4. Testing Strategy

Test all validation edge cases:
- ✅ Valid combinations of side + margin
- ✅ All order types (market, limit, stop, stop-limit)
- ✅ All expiration types
- ❌ Invalid side values
- ❌ Missing required order type
- ❌ Invalid expiration
- ✅ Ticker formatting
- ✅ URL encoding with nested structures
- ✅ Signature generation (compare with Python output)

### 5. API Compatibility

**Note**: The Python SDK you're using (`tradernet-sdk==2.0.0`) may be different from `tradernet-api`. Check which one your microservice actually uses:

- `tradernet-api` (kutsevol) - Analyzed above
- `tradernet-sdk` (PyPI) - May have different API

**Action**: Verify which SDK your microservice uses and analyze that one too.

## Methods to Implement

Based on your current usage in `tradernet_service.py`:

1. ✅ `user_info()` - Test connection (V1)
2. ✅ `buy(symbol, quantity)` - Place buy order (V2)
3. ✅ `sell(symbol, quantity)` - Place sell order (V2)
4. ✅ `get_placed(active=True)` - Get pending orders (V2)
5. ✅ `account_summary()` - Get portfolio (V2)
6. ✅ `get_trades_history()` - Get executed trades (V2)
7. ✅ `get_quotes(symbols)` - Get quotes (V1 or V2)
8. ✅ `get_candles(symbol, start, end)` - Historical data (V1 or V2)
9. ✅ `find_symbol(symbol, exchange)` - Security lookup (V1)
10. ✅ `security_info(symbol)` - Security metadata (V1)
11. ✅ `authorized_request(method, params, version)` - Custom API call

**Note**: Some methods may not be in `tradernet-api` but in `tradernet-sdk`. You'll need to check the actual SDK you're using.

## Important Note: SDK Version

**Your microservice uses**: `tradernet-sdk==2.0.0` (from PyPI)

**Analyzed SDK**: `tradernet-api` (from GitHub: kutsevol/tradernet-api)

These may be **different packages**! You should:

1. **Check PyPI**: Look up `tradernet-sdk` on PyPI to find its source
2. **Compare APIs**: The methods you're using (`user_info()`, `buy()`, `sell()`, `account_summary()`, etc.) may have different implementations
3. **Analyze Both**: If they're different, analyze the actual `tradernet-sdk` source code

However, the authentication patterns (V1/V2, HMAC signing) are likely similar across both SDKs since they target the same Tradernet API.

## Next Steps

1. **Verify SDK**:
   - Check PyPI for `tradernet-sdk` source code
   - Compare with `tradernet-api` to see differences
   - Analyze the actual SDK your microservice uses
2. **API Documentation**: Review official Tradernet API docs for endpoint details
3. **Start with V2**: Implement V2 client first (most commands use it)
4. **Test Authentication**: Verify signature generation matches Python
5. **Implement Validation**: Port all validation logic
6. **Add Tests**: Comprehensive test coverage for edge cases
