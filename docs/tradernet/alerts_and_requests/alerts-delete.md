# Remove price alert

### Description of server request parameters and a sample response:

#### Request:

```json
{
"cmd"                   (string)	:"togglePriceAlert",
"params"                (array)		:{
    "id"                (number)	:116071,
    "del"               (boolean)	:true,
    "quote_type"        (string)	:"ltp",
    "notification_type" (string)	:"email"
}
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | String | Name of the method invoked
| params |   | array | Parameter array
| params | id | number | unique alert ID
| params | del | boolean | Alert removal feature
| params | quote_type | string |
| params | notification_type | string |

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

#### Response:

```json
{
	"added" (boolean):true
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
    "code"   (number)	: 1,
    "errMsg" (string)   : "No \"params\" key in request object"
}
```

### Examples of using

## Examples

### Browser

```json
/**
 * Removing price alert
 * @param {string} id
 * @param {function} callback
 */
function removePriceAlert(id, callback) {
    var removeData = {
        "cmd": "togglePriceAlert",
        "params":{
            "id":"134216",
            "del":true,
            "quote_type":"ltp",
            "notification_type":"email"
   }
    };

    var params = {
        q: JSON.stringify(removeData)
    };

    $.ajax({
      url: 'https://tradernet.com/api/',
      xhrFields: {
        withCredentials: true
      },
      data: params,
      type: 'GET',
      success: callback,
      error: callback
    });

}

removePriceAlert("247", console.info.bind(console));
```
