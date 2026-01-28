# Get ticker data.

### Description of server request parameters and a sample response:

#### Request:

```json
{
    "cmd" (string)   : "getSecurityInfo",
    "params" (array) : {
        "ticker" (string) : 'AAPL.US',
        "sup"    (bool)   : true
    }
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | string | Request execution command
| params |   | array | Request execution parameters
| params | ticker | string | the name of the ticker, required to retrieve data from the server
| params | sup | bool | IMS and trading system format

#### Response:

Getting a response if successful.

```json
/**
 * A sample response returned by the server, when requesting information about a ticker
* @param {number} id - Unique ticker ID
* @param {string} short_name - Short ticker name
* @param {string} default_ticker - Ticker name on the Exchange
* @param {string} nt_ticker - Ticker name in Tradernet system
* @param {string} first_date - Company registration date in stock exchange
* @param {string} currency - Currency of a security
* @param {number} min_step - Minimum price increment of a security
* @param {number} code - Code error
*/
{
     'id'            : 2772,
    'short_name'     :  'Apple Inc.',
    'default_ticker' :  'AAPL',
    'nt_ticker'      :  'AAPL.US',
    'firstDate'      :  '02.01.1990',
    'currency'       :  'USD',
    'min_step'       :  0.01000,
    'code'           :  0,
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
    "error" : "User is not found",
    "code"  : 7
}
```

### Examples of using

## Examples

### JS (jQuery)

```json
/**
 * @type {getSecurityInfo}
 */
var exampleParams = {
    "cmd"    : "getSecurityInfo",
    "params" : {
        "ticker" : "FB.US",
        "sup"    : true,
    }
};

function getSecurityInfo(callback) {
    $.getJSON("https://tradernet.com/api/", {q: JSON.stringify(exampleParams)}, callback);
}

/**
 * Get the object
 **/
getSecurityInfo(function(json){
    console.log(json);
});
```

### PHP

```php
$publicApiClient = new PublicApiClient($apiKey, $apiSecretKey, Nt\PublicApiClient::V1);
$responseExample = $publicApiClient->sendRequest('getSecurityInfo', ['ticker'=> 'AAPL.US', 'sup' => true], 'array');
```

### Python

```python
cmd_ ='getSecurityInfo'
params_ = {
    'ticker': 'AAPL.US',
    'sup': True
}
res = NtApi.PublicApiClient(pub_, sec_, NtApi.PublicApiClient().V1)
print(res.sendRequest(cmd_, params_).content.decode("utf-8"))
```
