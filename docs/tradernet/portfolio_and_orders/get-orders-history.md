# Retrieving orders history for the period

### Description of server request parameters and a sample response:

#### Request:

```json
{
    "cmd" (string)   : "getOrdersHistory",
    "SID" (string)   : "[SID by authorization]",
    "params" (array) : {
        "from" (datetime) : "2020-03-23T00:00:00",
        "till" (datetime) : "2020-04-03T23:59:59"
    }
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | string | Request execution command
| SID |   | string | SID received during the user's authorization
| params |   | array | Request execution parameters
| params | from | datetime | Request execution parameters. Period start date, format ISO 8601 YYYY-MM-DD\Thh:mm:ss
| params | till | datetime | Request execution parameters. Period end date, format ISO 8601 YYYY-MM-DD\Thh:mm:ss

#### Response:

Getting a response if successful.

```json
{
    "orders" (array) : {
        "key"   (string) : "USER",
        "order" (array)  : [
            {
                "id"                (int) : 1111222222112,
                "date"              (string|datetime) : "2020-03-23T10:00:28.853",
                "stat"              (int) : 31,
                "stat_orig"         (int) : 31,
                "stat_d"            (string|datetime) : "2020-03-23T10:00:33.620",
                "instr"             (string) : "AAPL.US",
                "oper"              (int) : 1,
                "type"              (int) : 2,
                "cur"               (string) : "USD",
                "p"                 (float)  : 100,
                "stop"              (string) : ".00000000",
                "stop_init_price"   (float)  : 112.82,
                "stop_activated"    (int) : 1,
                "q"                 (int) : 10,
                "leaves_qty"        (int) : 10,
                "aon"               (int) : "0",
                "exp"               (int) : 3,
                "rep"               (string) : "0",
                "fv"                (string) : "0",
                "name"              (string) : "Apple Inc.",
                "name2"              (string) : "Apple Inc.",
                "stat_prev"         (int)    : 2,
                "userOrderId"       (string) : "cps_21112",
                "trailing"          (string) : ".00000000",
                "login"             (string) : "USER",
                "instr_type"        (int)    : 1,
                "curr_q"            (int)    : 30,
                "mkt_id"            (int)    : 95006833,
                "owner_login"       (string) : "USER",
                "comp_login"        (string) : "example@domain.com",
                "safety_type_id"    (int)    : 15,
                "condition"         (string) : "",
                "text"              (string) : "The order may not be accepted",
                "@text"             (string) : "The order may not be accepted",
                "OrigClOrdID"       (string|null) : "The order may not be accepted",
                "trade"             (array)  : [
                    {
                        "id"       (int) : 40543041,
                        "p"        (float) : 78.5129,
                        "q"        (int) : 1,
                        "v"        (float) : 78.51,
                        "date"     (string|datetime) : "2020-04-02T21:19:47",
                        "profit"   (string) : ".00000000",
                        "acd"      (string) : ".00000000",
                        "pay_d"    (string|datetime) : "2020-04-06T00:00:00",
                        "before_q" (string) : ".00000000",
                        "after_q"  (int)    : 1,
                        "details"  (string) : ""
                    }
                ]
            },
            ...
        ]
    }
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
    "error" : "Exec wrong",
    "code"  : 18
}
```

**Description of response parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| orders |   | array | Request list.
| orders | key | string | Key (login) of the user.
| orders | order | array|null | Request from the list of requests.

### Examples of using

## Examples

### JS (jQuery)

```json
/**
 * @type {Orders}
 */
var exampleParams = {
    "cmd"    : "getOrdersHistory",
    "SID"    : "[SID by authorization]",
    "params" : {
        "from" : "2020-03-23T00:00:00",
        "till" : "2020-04-03T23:59:59"
    }
};

function getOrdersHistory(callback) {
    $.getJSON("https://tradernet.com/api/", {q: JSON.stringify(exampleParams)}, callback);
}

/**
 * Get the object **/
getOrdersHistory(function(json){
    console.log(json);
});
```

### PHP

```json
/**
 * Receiving orders history
* @param {string} from - Period start date, format ISO 8601 "YYYY-MM-DD\Thh:mm:ss"
* @param {string} till - Period end date, format ISO 8601 "YYYY-MM-DD\Thh:mm:ss"
*/

$publicApiClient = new PublicApiClient($apiKey, $apiSecretKey, Nt\PublicApiClient::V2);

$responseExample = $publicApiClient->sendRequest(
    'getOrdersHistory',
    [
        'from' => '22020-03-23T00:00:00',
        'till' => '2020-04-03T23:59:59'
    ],
);
```

### Python

```python
from tradernet import Trading, TraderNetCore

config = TraderNetCore.from_config('tradernet.ini')
trade = Trading.from_instance(config)

"""
Parameters:
    ----------
    start : datetime, optional
            Period start date.
    end : datetime, optional
        Period end date.

Returns
    -------
    result : dict
        A dictionary of orders.

"""

result = trade.get_historical(start=datetime(2023, 1, 1))
print(result)
```
