# Opening the security session.

### Description of server request parameters and a sample response:

#### Request:

Method for the security code request via SMS

```json
{
    "cmd" (string)   : "getSecuritySessionCode",
    "SID" (string)   : "[SID by authorization]",
    "params" (object) : {}
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
    "channel": "sms",
    "delay": 60,
    "isRepeatAvailable": true,
    "isInputAvailable": true,
    "isSent": true,
    "texts": {
        "sent": "The code has been sent to your Telegram and pushed to the app",
        "error": null,
        "repeat": "Resending",
        "footer": "Message signature text",
        "link": null
    }
}
```

We get an answer in case of failure

```json
// Common error
{
    "errMsg" : "Bad json",
    "code"   : 2
}
```

**Description of response parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| channel |   | string|null |
| delay |   | int|null | A repeated request can be made in, s
| isRepeatAvailable |   | bool | Resend attempts available
| isInputAvailable |   | bool | Code entry attempts available
| isSent |   | bool | Code successfully sent to the client
| texts |   | object | Additional information on security session opening
| texts | sent | string|null | Code sent to the client to
| texts | error | string|null | Error description
| texts | repeat | string|null | Resend button text
| texts | footer | string|null | Text with link at the bottom
| texts | link | string|null | Link

### Examples of using

## Examples

### JS (jQuery)

```javascript
function getSecuritySessionCode(callback) {
    var exampleParams = {
        "cmd"    : "getSecuritySessionCode",
        "SID"    : "[SID by authorization]",
        "params" : {}
    };

    $.ajax({
        url      : "https://tradernet.com/api/",
        dataType : 'json',
        type     : 'POST',
        data     : {q: JSON.stringify(exampleParams)},
        success  : function (json) {
            if (typeof callback === 'function') {
                callback(json);
            }
        }
    });
}

getSecuritySessionCode(function(json){
    console.log(json);
});
```

# Opening the security session

### Description of server request parameters and a sample response:

#### Request:

Method of sending a message with a secret code from the SMS to open a security session

```json
{
    "cmd" (string)   : "checkSecuritySessionCode",
    "SID" (string)   : "[SID by authorization]",
    "params" (array) : {
        "validationKey" (string) : "023456",
    }
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | string | Request execution command
| SID |   | string | SID received during the user's authorization
| params |   | array | Request execution parameters
| params | validationKey | string |

#### Response:

Getting a response if successful.

```json
{
    "success": true,
    "isAttemptAvailable": true,
    "sessions": [
        {
            "id": 1234567,
            "owner_login": "owner@example.test",
            "user_login": "user@example.test",
            "safety_type_id": 14,
            "key_current": "1232hjhsdgf123",
            "start_datetime": "2025-01-01T12:12:11.023",
            "expire_datetime": "2025-01-07T12:12:11.023",
            "expire": 72389472983,
            "ip": "api:123kjhsdkfjhs",
            "ip_client": "127.0.0.1",
        }
    ]
    "texts": {
        "error": null,
        "footer": "Message signature text",
        "link": null
    }
}
```

We get an answer in case of failure

```json
// Common error
{
    "errMsg" : "Bad json",
    "code"   : 2
}
```

**Description of response parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| success |   | bool | Session successfully opened.
| isAttemptAvailable |   | bool | Attempted access
| sessions |   | object[]|null | Security session information
| sessions | id | int | Security Session ID
| sessions | safety_type_id | int |
| sessions | owner_login | string | Login of the account owner
| sessions | user_login | string | Login of the client that opened the session
| sessions | key_current | string | Unique security session key
| sessions | start_datetime | string | Security session start date in UTCZ format
| sessions | expire_datetime | string | Security session end date in UTCZ format
| sessions | expire | int |
| sessions | ip | string | IP address hash
| sessions | ip_client | string | Client IP address
| texts |   | object | Additional information on security session opening
| texts | error | string|null | Error description
| texts | footer | string|null | Text with link at the bottom
| texts | link | string|null | Link

### Examples of using

## Examples

### JS (jQuery)

```javascript
function checkSecuritySessionCode(callback) {
    var exampleParams = {
        "cmd"    : "checkSecuritySessionCode",
        "SID"    : "[SID by authorization]",
        "params" : {
            "validationKey" : "000111"
        }
    };

    $.ajax({
        url      : "https://tradernet.com/api/",
        dataType : 'json',
        type     : 'POST',
        data     : {q: JSON.stringify(exampleParams)},
        success  : function (json) {
            if (typeof callback === 'function') {
                callback(json);
            }
        }
    });
}

checkSecuritySessionCode(function(json){
    console.log(json);
});
```
