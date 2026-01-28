# Checking the instruments allowed for trading

### Description of server request parameters and a sample response:

This methods allows receiving data on options.

#### Request:

```json
{
    "cmd"    (string) : "checkAllowedTickerAndBanOnTrade",
    "params" (array)  : {
        "ticker" (string) : "AAPL.US",
        "checkBan" (bool|null) : true
    }
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | string | Request execution command
| params |   | array | Request execution parameters
| params | ticker | string | Instrument ticker
| params | checkBan | bool|null | Should the current account restrictions be additionally checked?. Optional parameter

#### Response:

Getting a response if successful.

```json
{
    "allowed": 1,
    "allowedExpires": [
        1,
        3,
        2
    ]
}
```

We get an answer in case of failure

```json
// Common error
{
    "code": 1,
    "errMsg": "Param `q` must be an array"
}

// Method error
{
    "code": 5,
    "error": "No value specified in the mandatory field 'ticker'",
    "errMsg": "No value specified in the mandatory field 'ticker'"
}

// Trading in the instrument is prohibited
{
    "allowed": 0,
    "allowedExpires": [
        1,
        3,
        2
    ],
    "restriction": " By broker’s decision, the instrument is not available for trading. ",
    "operation": null
}

// Ban due to account blocking
{
    "allowed": 0,
    "allowedExpires": [
        1,
        3,
        2
    ],
    "recommendations": [
        {
            "title": " Please update your personal data ",
            "text": " Your account has been blocked due to outdated personal data. To unblock your account, submit an order to change information. ",
            "doc_type_id": 217,
            "trading_blocked": true
        }
    ]
}
```

**Description of response parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| allowed |   | int | Access. 0 or 1 depending on access to the instrument
| allowedExpires |   | array |
| restriction |   | string|null | Ban description (if any)
| operation |   | string|null | Transaction type (if any): B, S
| recommendations |   | array|null | Blocking description
| recommendations | title | string | Blocking head
| recommendations | text | string | Blocking description
| recommendations | type | int|null | Blocking code (if any)
| recommendations | doc_type_id | int|null | Related document code (if any)
| recommendations | trading_blocked | bool | Trading ban availability

### Examples of using

## Examples

### JS (jQuery)

```json
/**
 * @type {checkAllowedTickerAndBanOnTrade}
 */
var exampleParams = {
    "cmd": "checkAllowedTickerAndBanOnTrade",
    "params": {
        "ticker": "AAPL.US",
        "checkBan": true
    }
};

function checkAllowedTickerAndBanOnTrade(callback) {
    $.getJSON("https://tradernet.com/api/", {q: JSON.stringify(exampleParams)}, callback);
}

/**
 * Get the object
 */
checkAllowedTickerAndBanOnTrade(function(json){
    console.log(json);
});
```
