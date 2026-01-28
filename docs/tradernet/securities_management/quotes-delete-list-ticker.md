# Deleting the ticker from the list of securities

### Deleting the ticker from the list of user securities:

#### Request:

```json
{
    "cmd" (string)   : "deleteStockListTicker",
    "SID" (string)   : "<SID>",
    "params" (array) : {
        "id" (integer)    : 2,
        "ticker" (string) : "AAPL.US"
    }
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | string | Request execution command
| SID |   | string | Session ID received during authorization
| params |   | array | Request execution parameters

| params | id | integer | List ID
| params | ticker | string | Ticker

#### Response:

Getting a response if successful.

```json
{
    "userStockLists" : [
        {
            "id"      : 1,
            "userId"  : 123456,
            "name"    : "default",
            "tickers" : [],
            "picture" : null
        },
        {
            "id"      : 2,
            "userId"  : 123456,
            "name"    : "etf",
            "tickers" : [
                "AAAU.US",
                "ACES.US",
                "ACIO.US",
                "AFIF.US"
            ],
            "picture" : "🙂"
        }
    ],
    "selectedId"   : 1,
    "defaultId"    : 1
}
```

We get an answer in case of failure

```json
// Common error
{
    "errMsg" : "Bad json",
    "code"   : 2
}
```

### Examples of using

## Examples

### JS (jQuery)

```json
/**
 * @type {deleteStockListTicker}
 */
var exampleParams = {
    "cmd": "deleteStockListTicker",
    "SID": "<SID>",
    "params": {
        "id": 2,
        "ticker": "AAPL.US"
    }
};

function deleteStockListTicker(callback) {
    $.getJSON("https://tradernet.com/api/", {q: JSON.stringify(exampleParams)}, callback);
}

/**
 * Get the object **/
deleteStockListTicker(function(json){
    console.log(json);
});
```
