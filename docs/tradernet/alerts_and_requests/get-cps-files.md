# Receiving order files

### Description of server request parameters and a sample response:

#### Request:

```json
{
    "cmd" (string)   : "getCpsFiles",
    "SID" (string)   : "[SID by authorization]",
    "params" (array) : {
        "id"          (int|null) : 12345,
        "internal_id" (int|null) : 12345,
    }
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | string | Request execution command
| SID |   | string | SID received during the user's authorization
| params |   | array | Request execution parameters
| params | id | int|null | Order ID. May be not used if the draft order ID is known (internal_id).
| params | internal_id | int|null | Draft order number. Used when known, or if the order has the draft status and has not yet been assigned the main ID.

#### Response:

Getting a response if successful.

```json
{
  "files": [
    {
      "file"          : "base64=JVBERi0xLjUKJbXtrvM1MAolJUVPRgo=",
      "mime"          : "application\/pdf",
      "file_name"     : "att_file.pdf",
      "extension"     : "pdf",
      "encoding_type" : "base64"
    },
    ...
  ]
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
    "error" : "ACCESS DENIED: Cps with ID '12345' not available,
    "code"  : 12
}
```

**Description of response parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| files |   | array | File list
| files | file | string | File format base64
| files | mime | string | MIME type
| files | file_name | string | File name
| files | extension | string | File extension
| files | encoding_type | string | File encoding type (base64)

### Examples of using

## Examples

### JS (jQuery)

```json
/**
 * @type {getCps}
 */
var exampleParams = {
    "cmd"    : "getCpsFiles",
    "SID"    : "[SID by authorization]",
    "params" : {
        "id" : 12345
    }
};

function getCpsFiles(callback) {
    $.getJSON("https://tradernet.com/api/", {q: JSON.stringify(exampleParams)}, callback);
}

/**
 * Get the object **/
getCpsFiles(function(json){
    console.log(json);
});
```

### PHP

```php
$apiKey       = '[public Api key]'
$apiSecretKey = '[secret Api key]'

$publicApiClient = new PublicApiClient($apiKey, $apiSecretKey, Nt\PublicApiClient::V2);
$responseExample = $publicApiClient->sendRequest('getCpsFiles', [
    'id' => 12345
]);
```

### Python

```python
'''
The PublicApiClient.py script can, as an option, be hosted:
[your_current_py_directory]/v2/PublicApiClient.py
'''

import json
import v2.PublicApiClient as NtApi

pub_ = '[public Api key]'
sec_ = '[secret Api key]'

res = NtApi.PublicApiClient(pub_, sec_, NtApi.PublicApiClient().V2)

cmd_   ='getCpsFiles'
params_ = {
    'id' : 12345
}

result = res.sendRequest(cmd_, params).content.decode("utf-8")

print(
    type(result),
    result
)

jres = json.loads(result)

print(
    type(jres),
    jres
)
```
