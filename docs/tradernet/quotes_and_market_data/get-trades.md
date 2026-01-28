# Get trades

### Description of server request parameters and a sample response:

#### Request:

```json
{
    "cmd" (string)   : "getHloc",
    "SID" (string)   : "[SID by authorization]",
    "params" (array) : {
        "id"        : "AAPL.US",
        "timeframe" : -1
    }
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | string | Request execution command
| SID |   | string | SID received during the user's authorization
| params |   | array | Request execution parameters
| params | id | string | ticker name. You can specify multiple tickers separated by commas
| params | timeframe | signed int | "-1" value of the parameter indicating that trade cycles are required

#### Response:

Getting a response if successful.

```json
{
  "AAPL.US": {
    "series": [],
    "info"  : {
      "id"            : "AAPL.US",
      "nt_ticker"     : "AAPL.US",
      "short_name"    : "Apple Inc.",
      "default_ticker": "AAPL.US",
      "code_nm"       : "AAPL.US",
      "currency"      : "USD",
      "min_step"      : "0.01000000",
      "lot"           : "10.00000000"
    }
  },
  "took": 2.759
}
```

We get an answer in case of failure

```json
// Common error
{
    "errMsg" : "Bad json",
    "code"   : 2
}

// Method error
{
    "error" : "User is not found",
    "code"  : 7
}
```

**Description of response parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| series |   | array | Trade series
| info |   | array | Information about the requested ticker
| took |   | float | Calculating the execution time of a request

### Examples of using

## Examples

### JS (jQuery)

```json
/**
 * @type {GetHlocParams}
 */
var exampleParams = {
    "cmd"    : "getHloc",
    "SID"    : "[SID by authorization]",
    "params" : {
        "id"        : "AAPL.US",
        "timeframe" : -1
    }
};

function getTradesByTicker(callback) {
    $.getJSON("https://tradernet.com/api/", {q: JSON.stringify(exampleParams)}, callback);
}

/**
 * Get the object **/
getTradesByTicker(function(json){
    console.log(json);
});
```

### PHP

```php
/**
 * @type {GetHlocParams}
 */

$apiKey       = '[public Api key]'
$apiSecretKey = '[secret Api key]'

$publicApiClient = new PublicApiClient($apiKey, $apiSecretKey, Nt\PublicApiClient::V2);

$responseExample = $publicApiClient->sendRequest('getHloc', [
    "id"        => "AAPL.US",
    "timeframe" => -1
]);
```

### Python

```python
'''
The PublicApiClient.py script can, as an option, be hosted:
[your_current_py_directory]/v2/PublicApiClient.py

@type {GetHlocParams}
'''

import json
import v2.PublicApiClient as NtApi

pub_ = '[public Api key]'
sec_ = '[secret Api key]'

res = NtApi.PublicApiClient(pub_, sec_, NtApi.PublicApiClient().V2)

#  2. Sending a trade order

cmd_    =  'getHloc'
params_ = {
    'id'        : 'AAPL.US',
    'timeframe' : -1
}

print(res.sendRequest(cmd_, params_).decode("utf-8"))
```
