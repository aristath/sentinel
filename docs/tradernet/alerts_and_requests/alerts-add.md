# Add price alert.

### Description of server request parameters and a sample response:

#### Request:

```json
        HTTPS
        GET



{
    "cmd"                   (string)        :"togglePriceAlert",
    "params"                (array)         :{
        "ticker"            (string)        :"AAPL.US",
        "price"             (array)         :{
            "price"         (string)        :"500"
        },
        "trigger_type"      (string)        :"crossing",
        "quote_type"        (string)        :"ltp",
        "notification_type" (string)        :"email",
        "alert_period"      (number | string) :"0",
        "expire"            (number | string) :"0"
 }
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | String | Name of the method invoked
| params |   | array | Parameter array
| params | ticker | string | ticker in Tradernet's system
| params | price | array |
| params | price | string | price of the alert activation
| params | trigger_type | string |
| params | quote_type | string |
| params | notification_type | string |
| params | alert_period | number |
| params | expire | number | string |

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

#### Response:

```json
{
	"added" (boolean)   :true
}
```

**Description of response parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| added |   | boolean | Deliverable

### Error examples

```json
//Common error
{
	"code" 		(number)	: 5,
	"errMsg"	(string)	: "No trigger_type param is set"
}
```

### Examples of using

## Examples

### Browser

```json
/**
 * @type {AlertDataRow}
 */
var exampleData = {
    "ticker":"FCX.US",
    "price":{
        "price":"15"
    },
    "trigger_type":"crossing",
    "quote_type":"ltp",
    "notification_type":"email",
    "alert_period":"0",
    "expire":"2016-06-18 12:05"
};

/**
 * Add price alert
 * @param {AlertDataRow} newAlert
 * @param {function} callback
 */
function togglePriceAlert(newAlert, callback) {
    $.ajax({
      url: "https://tradernet.com/api/",
      xhrFields: {
        withCredentials: true
      },
      data: {
            q: JSON.stringify({
                cmd: "togglePriceAlert",
                params: newAlert
            })
      },
      type: "GET",
      success: callback,
      error: callback
    });

}
```
