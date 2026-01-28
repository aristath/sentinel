# Most traded/growing securities.

### Description of server request parameters and a sample response:

#### Request:

```json
	{
    "cmd"           (string)    :"getTopSecurities",
    "params"        (array)     :{
        "type"      (string)    : "stocks",
        "exchange"  (string)    : "europe",
        "gainers"   (int)       : 1,
        "limit"     (int)       : 10
     }
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | string | Request execution command
| params |   | array | Request execution parameters
| params | type | string | Instrument type
| params | exchange | string | Stock Exchanges
| params | gainers | boolean | List type
| params | limit | int | Number of instruments displayed,default: 10

**Description of instrument types:**

| Instrument type | Description
|---|---|---|---|
| stocks | Stocks
| bonds | Bonds
| futures | Futures
| funds | Funds
| indexes | Indices

**Description of available exchanges:**

| Stock Exchanges | Description
|---|---|---|---|
| kazakhstan | Kazakhstan
| europe | Europe
| usa | USA
| ukraine | Ukraine
| currencies | Currency

**Description of list types:**

| Value | Description
|---|---|---|---|
| 1 | Top fastest-growing
| 0 | Top by trading volume

#### Response:

Exemplified reply in the event of success

```json
		{
ers": [
L.US",
S",
S"
			]
		}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| tickers |   | array | List of instruments

Exemplified reply in the event of failure

```json
		{
"  : 5,
    "error" : "Exchange is missing",
    "errMsg": "Exchange is missing"
		}
```

**Description of response parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| code |   | int | Code error
| error |   | string | Error description
| errMsg |   | string | Error description

### Examples of using

## Examples

### Browser

```json
/**
 * @type {getTopSecurities}
 */
var exampleParams = {
    "cmd":     "getTopSecurities",
    "params": {
       "type": "stocks",
       "exchange": "europe",
       "gainers": 0,
       "limit": 10
    }
};

/**
 *  Gets the list of the most traded securities or the fastest growing ones in the last year (available only for stocks)
 * @param {getTopSecurities} params
 * @param callback
 */
function getTopSecurities(params, callback) {
    $.getJSON('https://tradernet.com/api/', {q: JSON.stringify(params)}, callback);
}

getTopSecurities(exampleParams,
    function (json) {
        console.info(json);
    }
);
```
