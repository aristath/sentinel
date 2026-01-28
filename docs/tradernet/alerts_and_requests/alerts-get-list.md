# Retrieving the current price alerts

### Description of server request parameters and a sample response:

#### Request:

```json
{
"cmd"           (string)        :"getAlertsList",
"params"        (array)         :{
    "ticker"    (string | null) :"AAPL.US"
    }
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | String | Name of the method invoked
| params |   | array | Parameter array
| params | ticker | string | null | ticker in Tradernet's system

#### Response:

```json
{
"alerts" (array):[
    {
    "id"                (number)            :76,
    "auth_login"        (string)            :"virtual@virtual.com",
    "ticker"            (string)            :"FCX.US",
    "init_price"        (number)            :"9.8",
    "trigger_price"     (string)            :"{"price":"105"}",
    "quote_type"        (string)            :"ltp",
    "notification_type" (string)            :"email",
    "trigger_type"      (string)            :"crossing",
    "periodic"          (number)            :"0",
    "expire"            (number | string)   :"",
    "triggered"         (number)            :"",
    "deleted"           (string)            :"0"
    }
   ]
}
```

**Description of response parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| alerts |   | array | Parameter array
| alerts | id | number | unique alert ID
| alerts | auth_login | string | login of user who set an alert
| alerts | ticker | string | ticker in Tradernet's system
| alerts | init_price | number | price of the alert activation
| alerts | trigger_price | string | price of alert activation (JSON string!!!)
| alerts | quote_type | string |
| alerts | notification_type | string |
| alerts | triggered | string | whether an alert was activated
| alerts | trigger_type | string |
| alerts | periodic | number |
| alerts | expire | number | string |
| alerts | deleted | string | alert interval indicator

**Price type description:**

| Price type | Description
|---|---|---|---|
| ltp | last trade price
| bap | the best bid price
| bbp | the best ask price
| op | opening price
| pp | closing price

**Notification type description:**

| type of notification | Description
|---|---|---|---|
| email | by mail only
| sms | only via SMS
| push | push notification
| all | via SMS and email

**Alert trigger event description:**

| Trigger method | Description
|---|---|---|---|
| crossing | Crossing price
| crossing_down | Crossing Down
| crossing_up | Crossing Up
| less_then | Less than
| greater_then | Greater than
| channel_in | Is included in the range
| channel_out | Goes out of the range
| channel_inside | Within the range
| channel_outside | Outside the range
| moving_down_from_current | Decreases from the current price by %
| moving_up_from_current | Moving up from the current price by %
| moving_down_from_maximum | Moving down from maximum of the day by %
| moving_up_from_minimum | Moving up from minimum of the day by %

**Alert activation frequency description:**

| Value | Description
|---|---|---|---|
| 0 | Once
| 60 | Activate again in 1 min after it has worked
| 300 | Activate again in 5 minutes after it has worked
| 900 | Activate again in 15 minutes after it has worked
| 3600 | To re-activate after an hour of operation
| 86400 | Activate again in 24 hours after it worked

**Alert duration description:**

| alert period | Description
|---|---|---|---|
| 0 | Good-Til-Cancelled
| end_of_day | Good-Til-Day
| till_time | Until a specified time

### Error examples

```json
//Method error
{
"alerts":[
    {
        "error" (string): "Instrument not found"
    }
  ]
}
```

```json
//Common error
{
    "code"      (number) 	: 1,
    "errMsg"    (string)	: "No \"params\" key in request object"
}
```

### Examples of using

## Examples

### Browser

```json
/**
 * Retrieving the list of price alerts
 * @param {string} [ticker]
 * @param {function} callback
 */
$results = $('#results');
function addLog(data) {
  $results.html( $results.html() + JSON.stringify(data));
}
var WS_SOCKETURL = 'https://ws2.tradernet.com/';

$(document).ready(function () {
  //var ws = io(WS_SOCKETURL);

  var exampleData = {
    "cmd": "getAlertsList",
        "params": {
            "ticker": AAPL.US,
            "triggered": false
        }
  }

  function getAlertsList(ticker, callback) {
    $.ajax({
      url: 'https://tradernet.com/api/',
      xhrFields: {
        withCredentials: true
      },
      data: {
            q: JSON.stringify({
                cmd: 'getAlertsList',
                params: ticker
            })
      },
      type: 'GET',
      success: callback,
      error: callback
    });

}

getAlertsList(exampleData, addLog);
});
```
