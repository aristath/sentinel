# Lists of user securities

### Receiving the lists of user securities:

#### Request:

```json
{
    "cmd" (string) : "getUserStockLists",
    "SID" (string) : "<SID>",
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | string | Request execution command
| SID |   | string | Session ID received during authorization

#### Response:

Getting a response if successful.

```json
{
    "userStockLists" : [
        {
            "id"      : 1,
            "userId"  : 123456,
            "name"    : "default",
            "tickers": [
                "FRHC.US",
                "CRH.US",
                "URBN.US",
                "VRT.US",
                "LZ.US",
                "COST.US",
                "RYAN.US",
                "APA.US",
                "CSCO.US",
                "BLDR.US"
            ],
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
        },
        {
            "id": 4,
            "userId": 123456,
            "name": "Best",
            "picture": "✳️",
            "tickers": [
                "SPCE.US",
                "GTHX.US"
            ]
        },
        ...
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
 * @type {getUserStockLists}
 */
var exampleParams = {
    "cmd": "getUserStockLists",
    "SID": "<SID>"
};

function getUserStockLists(callback) {
    $.getJSON("https://tradernet.com/api/", {q: JSON.stringify(exampleParams)}, callback);
}

/**
 * Get the object **/
getUserStockLists(function(json){
    console.log(json);
});
```
