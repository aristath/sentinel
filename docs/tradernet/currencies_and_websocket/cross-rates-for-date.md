# Exchange rate by date

### Description of server request parameters and a sample response:

#### Request:

```json
{
    "cmd" (string)   : "getCrossRatesForDate",
    "SID" (string)   : "[SID by authorization]",
    "params" (array) : {
        "base_currency" (string) : "USD",
        "currencies" (array) : ["EUR", "HKD"],
        "date" (null|string) : "2024-05-01"
    }
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | string | Request execution command
| params |   | array | Request execution parameters
| params | base_currency | string | Base currency
| params | currencies | array | List of currencies, for which the rate is retrieved
| params | date | string|null | Date, as at which the rate is requested. Optional parameter. If missing, the current date shall be used

#### Response:

Getting a response if successful.

```json
{
    "rates": {
        "EUR": 0.92261342533093,
        "HKD": 7.8070160113905
    }
}
```

We get an answer in case of failure

```json
// Common error
{
    "errMsg" : "Bad parameters",
    "code"   : 2
}
```

**Description of response parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| rates |   | array | List of exchange rates to the base currency

### Examples of using

## Examples

### JS (jQuery)

```json
/**
 * @type {getCrossRatesForDate}
 */
var exampleParams = {
    "cmd" : "getCrossRatesForDate",
    "params" : {
        "base_currency" : "USD",
        "currencies" : ["EUR", "HKD"],
        "date" : "2024-05-01"
    }
};

function getCrossRatesForDate(callback) {
    $.getJSON("https://tradernet.com/api/", {q: JSON.stringify(exampleParams)}, callback);
}

/**
 * Get the object **/
getCrossRatesForDate(function(json){
    console.log(json);
});
```
