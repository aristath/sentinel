# Adding the list of securities

### Adding the list of securities to the lists of user securities:

#### Request:

```json
{
    "cmd" (string)   : "addStockList",
    "SID" (string)   : "<SID>",
    "params" (array) : {
        "name" (string)    : "etf",
        "picture" (string) : "🙂",
        "tickers" (array)  : [
            "AAAU.US",
            "ACES.US",
            "ACIO.US",
            "AFIF.US"
        ]
    }
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | string | Request execution command
| SID |   | string | Session ID received during authorization
| params |   | array | Request execution parameters

| params | name | string | List name
| params | picture | string | List image
| params | tickers | array | List of tickers

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
 * @type {addStockList}
 */
var exampleParams = {
    "cmd": "addStockList",
    "SID": "<SID>",
    "params": {
        "name": "etf",
        "picture": "🙂",
        "tickers": [
            "AAAU.US",
            "ACES.US",
            "ACIO.US",
            "AFIF.US"
        ]
    }
};

function addStockList(callback) {
    $.getJSON("https://tradernet.com/api/", {q: JSON.stringify(exampleParams)}, callback);
}

/**
 * Get the object **/
addStockList(function(json){
    console.log(json);
});
```
