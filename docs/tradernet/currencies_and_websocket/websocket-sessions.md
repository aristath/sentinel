# Retrieving the list and subscribing to security session openings.

### Description of server request parameters and a sample response:

The server sends the 'sessions' event with session updates

#### Response:

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

### Examples of using

## Examples

### Websockets

```javascript
var WebSocketsURL = "wss://wss.tradernet.com/";
var ws = new WebSocket(WebSocketsURL);

var resultsDiv = document.getElementById('results');


/**
* Security sessions information handler
*
* @param {?object} err - Security session error. If not error is null
* @param {?SocketSequrityResponseMessage} data - Opened security sessions list
*/
function (data) {
  var totalSessions = data;
  var maxExpireTime = 0;
  totalSessions.forEach(
    /**
     * @param {SequritySession} - Opened security session
     */
    function (sess) {
      maxExpireTime = Math.max(maxExpireTime, sess.expire);
    }
  );

  resultsDiv.innerText = '' +
    'Security sessions total: ' + totalSessions.length + ',' +
    'Security session maximum action: ' + maxExpireTime + ' мс';
}

ws.onmessage = function (m) {
    const [event, data] = JSON.parse(m.data);
    if (event === 'error') {
         resultsDiv.innerText = 'ERROR on get sessions: ' + JSON.stringify(data);
    }
    if (event === 'sessions') {
        updateWatcher(data);
    }
};

ws.onopen = function() { // Waiting for the connection to open
  ws.send(JSON.stringify(['session']));
};
```
