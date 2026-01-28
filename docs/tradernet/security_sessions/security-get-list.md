# Retrieving the list of open security sessions.

### Description of server request parameters and a sample response:

#### Request:

The method command getSecuritySessions

```json
{
    "cmd" (string)   : "getSecuritySessions",
    "SID" (string)   : "[SID by authorization]",
    "params" (array) : {}
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | string | Request execution command
| SID |   | string | SID received during the user's authorization. Used when there is a request API V1.
| params |   | array | Request execution parameters

#### Responce:

Getting a response if successful.

```json
/**

 * @typedef {{}} SequrityResponse

 * @property {number} id - unique security session ID
 * @property {string} owner_login - account authorization login
 * @property {string} user_login - broker account login (if your account is managed by a broker)
 * @property {number} safety_type_id - ID of security session type
 * @property {string} key_current - unique key of a security session
 * @property {string} start_datetime - Open Date of a security session (UTCZ format)
 * @property {string} expire_datetime - Closing date of a security session (UTCZ format)
 * @property {number} expire - number  of milliseconds between the message received and the expiration of a security session.
 * @property {string} ip - IP address hash
 * @property {string} ip_client - Client IP address
 */

/**
 * @typedef {{{SequrityResponse[]}}[]} SocketSequrityResponseMessage
 */

[
    {
        "id"              : 7165011,
        "owner_login"     : "virtual@virtual.com",
        "user_login"      : "virtual@virtual.com",
        "safety_type_id"  : 4,
        "key_current"     : "Login, password",
        "start_datetime"  : "2016-06-14T13:14:13.187",
        "expire_datetime" : "2016-06-15T13:14:13.187",
        "expire"          : 85299,
        "ip"              : "c5u7iip134fdfsxfqt4aq1osqchtg5b",
        "ip_client"       : "19.16.32.32"
    },
    ...
]

// Response if there are no sessions
[]
```

We get an answer in case of failure

```json
// Common error
{
    "errMsg" : "Unsupported query method",
    "code"   : 2
}
```

**Description of response parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| order_id |   | int | Order ID of the canceled order
| [ ] |   | array | Array of data if successful or if the list is missing

### Examples of using

## Examples

### Websockets

```javascript
var WebSocketsURL = "wss://wss.tradernet.com/";
var ws = new WebSocket(WebSocketsURL);

var resultsDiv = document.getElementById('results');


/**
* Security session information retrieval handler* @param {?object} err - security session retrieval error. If no error occurred === null
* @param {?SocketSequrityResponseMessage} data - list of security sessions opened*/
function sessionsWatcher (data) {
  //Handling retrieved security sessions  var totalSessions = data;
  var maxExpireTime = 0;
  totalSessions.forEach(
    /**
     * @param {SequritySession} - Opened security session     */
    function (sess) {
      maxExpireTime = Math.max(maxExpireTime, sess.expire);
    }
  );

  resultsDiv.innerText = '' +
    'Total security sessions opened: ' + totalSessions.length + ',' +
    ' maximum security session validity: ' + maxExpireTime + ' ms';
}

ws.onmessage = function (m) {
    const [event, data] = JSON.parse(m.data);
    if (event === 'error') {
         resultsDiv.innerText = 'ERROR on get sessions: ' + JSON.stringify(data);
    }
    if (event === 'sessions') {
        sessionsWatcher(data);
    }
};

ws.onopen = function() { // Waiting for the connection to open
  ws.send(JSON.stringify(['sessions']));
};
```

### Browser JS (JQUERY)

```json
/**
 * @type {getSecuritySessions}
 */
var paramsToGetSessions = {
    "cmd"    : "getSecuritySessions",
    "SID"    : "[SID by authorization]",
    "params" : {}
};

function getSecuritySessions (callback) {
    $.getJSON("https://tradernet.com/api/", {q: JSON.stringify(paramsToGetSessions)}, callback);
}

getSecuritySessions(function (json) {
    console.info(json);
});
```

### NodeJS

```javascript
let io = require('socket.io-client');
let cookie = require('cookie');

//For first rime we need to get sessionID to establish connection by WebSocket
//Let's use Promise to get them

let sidPromise = new Promise(function (resolve, reject) {
    let querystring     = require('querystring');
    let https           = require('https');

    let authData = {
        login: 'test@test123.ru',
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
                console.error('ERROR while auth...');
                reject(jsonResponse.error);
            } else {
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

                resolve({
                    'user-id': userID,
                    'session-id': sessionID
                });
            }
        });
    });

    // post the data
    postRequest.write(postData);
    postRequest.end();
});

sidPromise.then(function (sid) {

    let WebSocketsURL = `wss://ws.tradernet.com/?SID=${sid['session-id']}`;
    let ws = io(WebSocketsURL, {
        extraHeaders: {
            'cookie': cookie.serialize('SID', sid['session-id'])
        }
    });

    console.log('SID GETTED', sid, WebSocketsURL);

    ws.on("sup_iitr_notify_sessions_json",

      function (err, data) {
        console.info('got answer from WebSockets', JSON.stringify(err), JSON.stringify(data));
        if (err) {
          // Security session retrieval error handler          console.log('ERROR on get sessions: ' + JSON.stringify(err));
        } else {
          // Handling retrieved security sessions          let totalSessions = data[0].response.res;
          let maxExpireTime = 0;
          if (!totalSessions) {
              console.log('' +
                          'No security session opened'
                          );
          } else {
              totalSessions.forEach(
                /**
                 * @param {SequritySession} - Opened security session                 */
                function (sess) {
                  maxExpireTime = Math.max(maxExpireTime, sess.expire);
                }
              );

              console.log( '' +
                'Total security sessions opened: ' + totalSessions.length + '\n' +
                ' maximum security session validity: ' + maxExpireTime + ' ms'
              );
          }

        }
      }
    );

    ws.on('connect', function () {

      console.log('Sending request');
      ws.emit('sup_subscribe', 'iitr_notify_sessions_json', '%username');

    });

    ws.on('error', function (err) {
        console.error(err);
    });

    ws.on('reconnect_attempt', function (err) {
        console.error('reconnect_attempt', err);
    });

    ws.on('reconnect_error', function (err) {
        console.error('reconnect_error', err);
    });
});
```
