# Receiving clients' requests history

### Description of server request parameters and a sample response:

Method of receiving clients' requests history.

#### Request:

The method command getClientCpsHistory

```json
{
    "cmd"    : "getClientCpsHistory",
    "SID"    : "[SID by authorization]",
    "params" : {
        "cpsDocId"   (?int)         : 181,
        "id"         (?int)         : 123123123,
        "date_from"  (?string|date) : '2020-04-10',
        "date_to"    (?string|date) : '2020-05-10',
        "limit"      (?int)         : 100,
        "offset"     (?int)         : 20,
        "cps_status" (?int)         : 1
    }
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | string | Request execution command
| SID |   | string | SID received during the user's authorization
| params |   | array | Request execution parameters
| params | cpsDocId | null|int | Request execution parameters. Request type ID. Can be viewed in section                List of request types. Optional parameter
| params | id | null|int | Request execution parameters. Order ID. Optional parameter
| params | date_from | null|string|date | Request execution parameters. Request list start date. Optional parameter
| params | date_to | null|string|date | Request execution parameters. Request list end date. Optional parameter
| params | limit | null|int | Request execution parameters. Number of orders displayed in the list. Optional parameter
| params | offset | null|int | Request execution parameters. Step of the list of displayed requests. Optional parameter
| params | cps_status | null|int | Request execution parameters. Requests statuses: 0 - draft request; 1 - in process of execution; 2 - request is rejected; 3 - request is executed. Optional parameter

#### Response:

Getting a response if successful.

```json
{
    "cps": [
        {
            "reception": 1,
            "brief_nm": "5555555",
            "iis": "regular",
            "auth_login": "johndow@example.com",
            "manager": "Smith Suzanna",
            "manager_user_id": 123123123123,
            "fio": "Dow John",
            "tel": "+79999999901",
            "id": 13123125345345,
            "ts_id": 1231233333,
            "type_doc_id": 10160,
            "user_id": 1347723723,
            "date_crt": "2019-11-06 15:31:55",
            "date_mod": "2019-11-06 15:31:56.068482",
            "owner_login": "johndow@example.com",
            "creator_login": "johndow@example.com",
            "status_c": 3,
            "params": {
                "ip": "",
                "sign": 1,
                "secType": 3,
                "sms-code": "033333333",
                "status_c": 3,
                "status_date": "2019-11-06 15:31:56",
                "type_doc_id": "10160",
                "telegram_bot": "on",
                "client_comment": "",
                "security_session_id": 72648726348,
                "authorized-by-sms-code": ""
            },
            "parent_id": null,
            "submit_error": null,
            "fl_export_billing": 0,
            "name": "Copy of SMS to Telegram",
            "date_crt_msk": "2019-11-06 15:31:55.663147",
            "is_blocked": false,
            "available_for_cancel": false
        },
        ...
    ],
    "total": 10000
}
```

We get an answer in case of failure

```json
// Common error
{
    "errMsg" : "Unsupported query method",
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
| total |   | int | Total requests
| cps |   | array | Request list

### Examples of using

## Examples

### JS (jQuery)

```javascript
/**
 * @type {getCpsData}
 */
var exampleParams = {
    "cmd"    : "getClientCpsHistory",
    "SID"    : "[SID by authorization]",
    "params" : {
        "cpsDocId"   : 181,
        "id"         : 123123123,
        "date_from"  : '2020-04-10',
        "date_to"    : '2020-05-10',
        "limit"      : 100,
        "offset"     : 20,
        "cps_status" : 1
    }
};

function getClientCpsHistory(callback) {
    $.getJSON("https://tradernet.com/api/", {q: JSON.stringify(exampleParams)}, callback);
}

/**
 * Get the object **/
getClientCpsHistory(function(json){
    console.log(json);
});
```

### PHP

```php
$publicApiClient = new PublicApiClient($apiKey, $apiSecretKey, Nt\PublicApiClient::V2);

$params = [
    'cpsDocId'   => 181,
    'id'         => 123123123,
    'date_from'  => '2020-04-10',
    'date_to'    => '2020-05-10',
    'limit'      => 100,
    'offset'     => 20,
    'cps_status' => 1
];

$responseExample = $publicApiClient->sendRequest('getClientCpsHistory', $params);
```

### Python

```python
cmd_   = 'getClientCpsHistory'
params_ = {
    "cpsDocId"   : 181,
    "id"         : 123123123,
    "date_from"  : '2020-04-10',
    "date_to"    : '2020-05-10',
    "limit"      : 100,
    "offset"     : 20,
    "cps_status" : 1
}

res = NtApi.PublicApiClient(pub_, sec_, NtApi.PublicApiClient().V2)
print(res.sendRequest(cmd_, params_).decode("utf-8"))
```
