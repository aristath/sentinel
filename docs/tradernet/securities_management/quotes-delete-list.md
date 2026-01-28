# Deleting the saved list of securities

### Deleting the saved list of securities from the lists of user securities:

#### Request:

```json
{
    "cmd" (string)   : "deleteStockList",
    "SID" (string)   : "<SID>",
    "params" (array) : {
        "id": (integer) 3
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
 * @type {deleteStockList}
 */
var exampleParams = {
    "cmd": "deleteStockList",
    "SID": "<SID>",
    "params": {
        "id": 3
    }
};

function deleteStockList(callback) {
    $.getJSON("https://tradernet.com/api/", {q: JSON.stringify(exampleParams)}, callback);
}

/**
 * Get the object **/
deleteStockList(function(json){
    console.log(json);
});
```
