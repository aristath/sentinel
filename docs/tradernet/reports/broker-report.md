# Getting the broker's report using software methods

### Description of server request parameters and a sample response:

#### Request:

The method command getBrokerReport

```json
{
    "cmd" (string)      : "getBrokerReport",
    "SID" (string|null) : "[SID by authorization]",
    "nonce" (floatnull) : 12345,
    "params" (array)    : {
        "date_start"  (string|date|null) : "2020-06-04",
        "date_end"    (string|date|null) : "2020-06-14",
        "time_period" (string|time|null) : "23:59:59",
        "format"      (string|null)      : "pdf",
        "type"        (string|null)      : "account_at_end"
    }
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | string | Request execution command
| SID |   | string | SID received during the user's authorization. (For API V1). Not used, if API Keys and headers are used X-NtApi-Sig, X-NtApi-PublicKey
| nonce |   | string | We recommend using the current timestamp as a nonce parameter. More information on the page « API key», paragraph 4. If the ID parameter is passed, the nonce parameter is not used
| params |   | array | Request execution parameters
| params | date_start | string|date|null | Starting date. Optional parameter, if flag is used recent
| params | date_end | string|date|null | Expiry date. Optional parameter, if flag is used recent
| params | time_period | string|time|null | Time cut maybe 23:59:59 or 08:40:00. Optional parameter, if flag is used recent
| params | recent | int|null | Accepts value of 1 or 0. Parameter that returns a date slice: report start date - yesterday 23:59:59; report end date - today 23:59:59. Optional parameter. If used, parameters are ignored date_start, date_end, time_period
| params | type | string|null | Data block from the report, optional parameter, possible values are shown in the table below  «Description of type parameter options»
| params | format | string|null | Report in the selected format. Acceptable formats: json, html, xml, xls, pdf. Default — json

**Description of type parameter options:**

| Value | Description
|---|---|---|---|
| account_at_start | Data array on the account status at the start time of the requested report period
| account_at_end | Data array on the account status at the date the end time of the requested report period
| trades | Dat array on trades for the requested report period
| commissions | Data array on commissions for the requested report period
| corporate_actions | Data array on corporate actions for the requested report period
| in_outs | Data array on deposits and withdrawals of funds for the requested report period
| in_outs_securities | Data array on deposits and withdrawals of securities for the requested report period
| cash_flows | Data array on all funds flows for the requested report period
| securities_flows | Data array on all securities movements for the requested report period

#### Response:

Getting a response if successful.

```json
    resource|json|xml

{
    "report" : {

        * @prop plainAccountInfoData  - Data array containing account information
        * @prop account_at_end        - Data array containing the balances at the end of the period
        * @prop account_at_start      - Data array containing opening balances
        * @prop cash_flows_json       - Data array, information about balances and all movements of money for the period
        * @prop cash_flows            - Data array containing data on deposits/withdrawals for the period
        * @prop securities_flows_json - Dataset, information on balances and all movements of securities for the period
        * @prop in_outs_securities    - Dataset containing information on the input/output of securities for the period
        * @prop trades                - Data array containing information about trades for the period
        * @prop commissions           - Data array containing information on the accrued commissions for the period
        * @prop corporate_actions     - Dataset containing information on corporate actions taken
        ...
    }
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
    "error" : "No param 'time_period' is set, or its incorrect. It should be '23:59:59' or '08:40:00'",
    "code"  : 109
}
```

**Description of response parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| resource|json |   | int | Returns a generated file or a response in json|xml format

### Examples of using

## Examples

### JS (jQuery) using the SID parameter:

```json
/**
 * @type {reports}
 */
var exampleParams = {
    "cmd"    : "getBrokerReport",
    "SID"    : "[SID by authorization]",
    "params" : {
        "date_start"  : "2020-06-04",
        "date_end"    : "2020-06-14",
        "time_period" : "23:59:59",
        "format"      : "pdf",
        "type"        : "account_at_end"
    }
};

function getBrokerReport(callback) {
    $.getJSON("https://tradernet.com/api/", {q: JSON.stringify(exampleParams)}, callback);
}

/**
 * Get the object **/
getBrokerReport(function(json){
    console.log(json);
});
```

### JS (jQuery) using the X-NtApi-Sig header:

```json
/**
 * @type {reports}
 */
var exampleParams = {
    "cmd"    : "getBrokerReport",
    "nonce"  : 12345,
    "params" : {
        "date_start"  : "2020-06-04",
        "date_end"    : "2020-06-14",
        "time_period" : "23:59:59",
        "format"      : "pdf",
        "type"        : "account_at_end"
    }
};

function getBrokerReport(callback) {
    $.ajaxSetup({
        headers : {
            "X-NtApi-Sig"       : "[Your hash]"
            "X-NtApi-PublicKey" : "[Your public Api Key]"
        },
        xhrFields: {withCredentials:true} // Parameter for the cross-domain request
    });
    $.getJSON("https://tradernet.com/api/", {q: JSON.stringify(exampleParams)}, callback);
}

/**
 * Get the object **/
getBrokerReport(function(json){
    console.log(json);
});
```

### PHP

```php
$publicApiClient = new PublicApiClient($apiKey, $apiSecretKey, Nt\PublicApiClient::V2);

// Create a report

$responseExample = $publicApiClient->sendRequest('getBrokerReport', [
    'date_start'  => date('Y-m-d', strtotime('-3 day')),
    'date_end'    => date('Y-m-d', strtotime('-2 day')),
    'time_period' => '23:59:59',
    'format'      => 'pdf',
    'type'        => 'account_at_end'
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

# Create a report

cmd_   ='getBrokerReport'
params_ = {
    'date_start'  : '2020-06-04',
    'date_end'    : '2020-06-14',
    'time_period' : '23:59:59',
    'format'      : 'pdf',
    'type'        : 'account_at_end'
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
