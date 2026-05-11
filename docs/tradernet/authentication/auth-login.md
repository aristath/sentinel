# User authentication in the system using a login-password combination.

#### Request:

```json
{
    "cmd" (string) : "authByLogin",
    "params" (array) : {
        "login" (string): "user@example.com",
        "password" (string): "password",
        "rememberMe" (integer|null): 1,
        "getAccounts" (boolean|null): false,
        "userId" (integer|null): 1234
    },
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | string | Request execution command
| params |   | array | Request execution parameters
| params | login | string | User login
| params | password | string | User password
| params | rememberMe | integer | Remember the session for 2 weeks. Optional parameter
| params | getAccounts | boolean | List all accounts associated with this login*. Optional parameter
| params | viewOnlyMode | boolean | Account access is limited to view-only mode. Optional parameter
| params | userId | integer | Specify a specific User ID for authorization. Optional parameter

* Important! When using getAccounts: true, we get a list of available accounts. After selecting the required User ID, pass it in the userId parameter, setting getAccounts to false. In this case, we get authorization for the selected user.

#### Response:

Getting a response if successful.

```json
{
    "success": true,
    "logged": true,
    "SID": "skjdhfahdf2847928743kjsfhd",
    "isSecuritySessionOpened": false,
    "userId": 1234,
    "real": true,
    "account_type": "brokerage",
    "account_title": "Trading account",
    "reception_country": "EU",
    "reception_code": "EU",
    "reception_name": "EU",
    "reception_title": "Freedom Finance",
    "reception_type": "broker",
    "hasAdminPanel": true
}
```

We get an answer in case of failure

```javascript
// Common error
{
    "errMsg" : "Bad json",
    "code"   : 2
}
```

### Examples of using

## Examples

```javascript
/**
 * @type {authByLogin}
 */
var exampleParams = {
    "cmd": "authByLogin",
    "params": {
        "login": "user@example.com",
        "password": "password",
        "rememberMe": 1,
        "getAccounts": false,
        "userId": 1234
    },
};

function authByLogin(callback) {
    $.post("https://tradernet.com/api/", {q: JSON.stringify(exampleParams)}, callback);
}

/**
 * Get the object **/
authByLogin(function(json){
    console.log(json);
});
```
