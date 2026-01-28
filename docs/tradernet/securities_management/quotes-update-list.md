# Changing the list of securities

### Changing the list of user securities:

#### Request:

```json
{
    "cmd" (string)   : "updateStockList",
    "SID" (string)   : "<SID>",
    "params" (array) : {
        "id" (integer)     : 2,
        "name" (string)    : "etf2",
        "picture" (string) : "",
        "index" (integer)  : 0
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
| params | name | string | List name
| params | picture | string | List image
| params | index | integer | List item number

#### Response:

Getting a response if successful.

```json
{
    "userStockLists" : [
        {
            "id"      : 2,
            "userId"  : 123456,
            "name"    : "etf2",
            "tickers" : [
                "AAAU.US",
                "ACES.US",
                "ACIO.US",
                "AFIF.US"
            ],
            "picture" : ""
        },
        {
            "id"      : 1,
            "userId"  : 123456,
            "name"    : "default",
            "tickers" : [],
            "picture" : null
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
 * @type {updateStockList}
 */
var exampleParams = {
    "cmd": "updateStockList",
    "SID": "<SID>",
    "params": {
        "id": 2,
        "name": "etf2",
        "picture": "",
        "index": 0
    }
};

function updateStockList(callback) {
    $.getJSON("https://tradernet.com/api/", {q: JSON.stringify(exampleParams)}, callback);
}

/**
 * Get the object **/
updateStockList(function(json){
    console.log(json);
});
```
