# Login & password authorization

### Examples of using

## Examples

### Browser

```javascript
var resultsDiv = $('#results');

$.ajax({
  url: 'https://tradernet.com/api/check-login-password',
  method: 'POST',
  data: {
    login: '[email protected]',
    password: 'test',
    rememberMe: 1
  },
  success: function (responseText) {
    resultsDiv.text(responseText);
  },
  error: function (err) {
    resultsDiv.text('Error: ' + err.statusText);
  }
});
```

### NodeJS

```javascript
let querystring     = require('querystring');
let https           = require('https');

let authData = {
    login: '[email protected]',
    password: 'test123',
    rememberMe: 1
};

let postData = querystring.stringify(authData);

let postOptions = {
      host: 'tradernet.com',
      path: '/api/check-login-password',
      method: 'POST',
      headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'Content-Length': Buffer.byteLength(postData)
      }
};

let postRequest = https.request(postOptions, function(res) {
    res.setEncoding('utf8');
    res.on('data', function (chunk) {
        let jsonResponse = JSON.parse(chunk);

        if(jsonResponse.error) {
            console.error('ERROR while auth...', jsonResponse.error);
        } else {
            console.info('ALL IS OK');

            let sessionID,
                userID;

            this.headers['set-cookie'].forEach(function (c) {
                let cookieStrVal = c.split(';')[0] || c;
                let cookieName = cookieStrVal.split('=')[0];

                switch (cookieName) {
                    case 'SID':
                        sessionID = cookieStrVal.split('=')[1];
                        break;
                    case 'uid':
                        userID = cookieStrVal.split('=')[1];
                        break;
                }
            });

            console.log({
                'user-id': userID,
                'session-id': sessionID
            });
        }
    });
});

// post the data
postRequest.write(postData);
postRequest.end();
```

# Getting a list of accounts and an authorization for one of them.

### Examples of using

## Examples

### Retrieving a list of accounts

```javascript
var resultsDiv = $('#results');

$.ajax({
  url: 'https://tradernet.com/api/check-login-password',
  method: 'POST',
  data: {
    login: '[email protected]',
    password: 'test',
    rememberMe: 1,
    mode: 'regular',
    getAccounts: true

  },
  success: function (responseText) {
    resultsDiv.text(responseText);
    console.log(responseText);
  },
  error: function (err) {
    var text = 'Error: ' + err.statusText;
    resultsDiv.text(text);
    console.log(text);
  }
});
```

```javascript
var resultsDiv = $('#results');

$.ajax({
  url: 'https://tradernet.com/api/check-login-password',
  method: 'POST',
  data: {
    login: '[email protected]',
    password: 'test',
    rememberMe: 1,
    mode: 'regular',
    userId: <User Id>
  },
  success: function (responseText) {
    resultsDiv.text(responseText);
  },
  error: function (err) {
    resultsDiv.text('Error: ' + err.statusText);
  }
});
```

# Authorization by SMS.

### Examples of using

## Examples

### Retrieving a list of accounts

```javascript
var params = JSON.stringify({
    "cmd"    : "getAuthSms",
    "params" : {
        "tel" : "+74951111111",
    }
});

params = {
    q: params
};

function authSmsCmd(params, callback) {

    $.ajax({
      url: 'https://tradernet.com/api/',
      method: 'GET',
      data: params,
      dataType: 'json',
      success: callback,
      error: function (err) {
        console.log('Error: ' + err.errMsg);
      }
    });

}

authSmsCmd(params, function (json) {

    var resultsDiv = $('#results');

    var result = confirm(" Enter SMS code ");

    if(result) {
        $.ajax({
          url    : 'https://tradernet.com/api/check-login-password',
          method : 'POST',
          data   : {
            rememberMe   : 1,
            auth_code_id : json.auth_code_id,
            sms          : result,
            mode         : 'sms'
          },
          success: function (responseText) {
            resultsDiv.text(responseText);
          },
          error: function (err) {
            resultsDiv.text('Error: ' + err.statusText);
          }
        });
    }

});
```
