# Get quote historical data (candlesticks).

### Description of server request parameters and a sample response:

#### Request:

```json
{
    "cmd" (string)   : "getHloc",
    "params" (array) : {
        "userId"       (int|null)        : <User Id>,
        "id"           (string)          : "FB.US",
        "count"        (signed int)      : -1,
        "timeframe"    (int)             : 1440,
        "date_from"    (string|datetime) : "15.08.2020 00:00",
        "date_to"      (string|datetime) : "16.08.2020 00:00",
        "intervalMode" (string)          : "ClosedRay"
    }
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | string | Request execution command
| params |   | array | Request execution parameters
| params | userId | string | User ID. Optional parameter. Used to retrieve the candlestick history data for a registered user. For a GET request only API v1
| params | id | string | ticker name. You can specify multiple tickers separated by commas
| params | count | signed int | the number of candlesticks that should be received in addition to the specified interval, if not required - the value should be -1. (for example, if you want to get all candlesticks for the year + 100 candlesticks before the interval, the parameter should be -100)
| params | timeframe | int #### Response:

Getting a response if successful.

```json
            params
            intervalMode
            string


            params
            date_from
            string | datetime
            the start date of the interval, for which it is required to obtain information on candlesticks in the format DD.MM.yyyy hh:mm


            params
            date_to
            string | datetime
            the end date of the interval, for which it is necessary to obtain information on the candlesticks in the format dd.M.yyyy hh:mm










/**
 * @type {FullHlocData}
 */
{
    "hloc": {
        "FB.US": [
            [107.25, 106.1603, 106.96, 106.26],
            [106.45, 104.62, 106.45, 104.75],
            [103.33, 100.25, 103.33, 102.32],
            [103.71, 101.41, 102.33, 102.82],
            [103.7301, 100.89, 101.05, 102.97]
        ]
    },
    "vl": {
        "FB.US": [
            7588957,
            8812260,
            5941541,
            6529607,
            5905857
        ]
    },
    "xSeries": {
        "FB.US": [
            1451422800,
            1451509200,
            1451854800,
            1451941200,
            1452027600
        ]
    },
    "maxSeries": 1452027600,
    "info": {
        "FB.US": [
            "id"             : "FB.US",
            "nt_ticker"      : "FB.US",
            "short_name"     : "Facebook, Inc.",
            "default_ticker" : "FB",
            "code_nm"        : "FB",
            "currency"       : "USD",
            "min_step"       : "0.01000000",
            "lot"            : "1.00000000"
        }
    },
    "took" : 26.685
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
| HLOC |   | Object.<string, number[][]> | Candlestick data: key – ticker name, value - array of arrays containing the following four elements [high, low, open, close]
| vl |   | Object.<string, number[][]> | Candlestick volume data: key – ticker name, value - array of arrays containing numbers which are equal to candlesticks volumes
| xSeries |   | Object.<Timestamps, number[][]> | Candlestick time data in seconds (!!!). The key is the name of the Ticker, the value is an array of numbers corresponding to the candlestick time
| maxSeries |   | Object.<Timestamp, number> | Timestamp of the most recent candlestick rendering
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
    "params" : {
        "id"           : "FB.US",
        "count"        : -1,
        "timeframe"    : 1440,
        "date_from"    : "15.08.2020 00:00",
        "date_to"      : "16.08.2020 00:00",
        "intervalMode" : "ClosedRay"
    }
};

function getHloc(callback) {
    $.getJSON("https://tradernet.com/api/", {q: JSON.stringify(exampleParams)}, callback);
}

/**
 * Get the object **/
getHloc(function(json){
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
    'id'           => 'FB.US',
    'count'        => -1,
    'timeframe'    => 1440,
    'date_from'    => '15.08.2020 00:00',
    'date_to'      => '16.08.2020 00:00',
    'intervalMode' => 'ClosedRay'
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

cmd_   = 'getHloc'
params_ = {
    'id'           : 'FB.US',
    'count'        : -1,
    'timeframe'    : 1440,
    'date_from'    : '15.08.2020 00:00',
    'date_to'      : '16.08.2020 00:00',
    'intervalMode' : 'ClosedRay'
}

print(res.sendRequest(cmd_, params_).decode("utf-8"))
```
