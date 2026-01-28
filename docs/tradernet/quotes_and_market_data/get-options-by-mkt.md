# Options demonstration

### Description of server request parameters and a sample response:

This methods allows receiving data on options.

#### Request:

```json
{
    "cmd"    (string) : "getOptionsByMktNameAndBaseAsset",
    "params" (array)  : {
        "ltr"                (string) : "FIX",
        "base_contract_code" (string) : "T.US"
    }
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | string | Request execution command
| params |   | array | Request execution parameters

| params | ltr | string | Market name
| params | base_contract_code | string | Underlying contract code

#### Response:

Getting a response if successful.

```json
[
    {
        "ticker": "+T^D1K40.US",
        "base_contract_code": "T.US",
        "last_trade_date": "2023-01-20",
        "expire_date": "2023-01-20",
        "strike_price": "10",
        "option_type": "CALL"
    },
    {
        "ticker": "+T^C5K14.5.US",
        "base_contract_code": "T.US",
        "last_trade_date": "2022-05-20",
        "expire_date": "2022-05-20",
        "strike_price": "4.5",
        "option_type": "CALL"
    },
    ...
]
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
 * @type {getOptionsByMktNameAndBaseAsset}
 */
var exampleParams = {
    "cmd": "getOptionsByMktNameAndBaseAsset",
    "params": {
        "ltr": "FIX",
        "base_contract_code": "T.US"
    }
};

function getOptionsByMktNameAndBaseAsset(callback) {
    $.getJSON("https://tradernet.com/api/", {q: JSON.stringify(exampleParams)}, callback);
}

/**
 * Get the object
 **/
getOptionsByMktNameAndBaseAsset(function(json){
    console.log(json);
});
```
