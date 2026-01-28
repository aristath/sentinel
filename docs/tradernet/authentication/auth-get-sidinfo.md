# User’s current session information

### Description of server request parameters and a sample response:

#### Request:

```json
{
    "cmd" (string)   : "getSidInfo",
    "SID" (string)   : "[SID by authorization]",
    "params" (array) : {}
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | string | Request execution command
| SID |   | string | SID received during the user's authorization
| params |   | array | Request execution parameters

#### Response:

Getting a response if successful.

```json
{
  "SID" (string)   : "[SID by authorization]",
  "user_id"  (int) : 2011111110
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

**Description of response parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| error |   | string | Error description
| SID |   | string | Session ID or null if no active session is available
| user_id |   | int | User ID

### Examples of using

## Examples

### JS (jQuery)

```json
/**
 * @type {getSidInfo}
 */
var exampleParams = {
    "cmd"    : "getSidInfo",
    "SID"    : "[SID by authorization]",
    "params" : {}
};

function getSidInfo(callback) {
    $.getJSON("https://tradernet.com/api/", {q: JSON.stringify(exampleParams)}, callback);
}

/**
 * Get the object **/
getSidInfo(function(json){
    console.log(json);
});
```

### PHP

```json
/**
 * User’s session information receipt*/

$publicApiClient = new PublicApiClient($apiKey, $apiSecretKey, Nt\PublicApiClient::V2);

$responseExample = $publicApiClient
                        ->sendRequest(
                            'getSidInfo'
                        );
```

### Python

```python
import PublicApiClient as NtApi

pub_ = 'Your Api key'
sec_ = 'Your Api secret'

cmd_ = 'getSidInfo'

res = NtApi.PublicApiClient(pub_, sec_, NtApi.PublicApiClient().V2)
print(res.sendRequest(cmd_).content.decode("utf-8"))
```
