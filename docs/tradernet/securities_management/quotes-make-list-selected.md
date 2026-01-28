# Setting the selected list of securities

### Setting the selected list of user securities:

#### Request:

```json
{
    "cmd" (string)   : "makeStockListSelected",
    "SID" (string)   : "<SID>",
    "params" (array) : {
        "id": (integer) 2
    }
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | string | Request execution command
| SID |   | string | Session ID received during authorization
| params |   | array | Request execution parameters

| params | id | integer | Saved list ID

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
    "selectedId"   : 2,
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
 * @type {makeStockListSelected}
 */
var exampleParams = {
    "cmd": "makeStockListSelected",
    "SID": "<SID>",
    "params": {
        "id": 2
    }
};

function makeStockListSelected(callback) {
    $.getJSON("https://tradernet.com/api/", {q: JSON.stringify(exampleParams)}, callback);
}

/**
 * Get the object **/
makeStockListSelected(function(json){
    console.log(json);
});
```
