# Subscribe to quotes updates.

### Description of response data from the server

The server sends the 'q' event with quote updates


### Examples of using

## Examples

### Browser

```javascript
var WebSocketsURL = "wss://wss.tradernet.com/";

var ws = new WebSocket(WebSocketsURL);

var tickersToWatchChanges = ["AAPL.US"];

/**
 * @param QuoteInfoAnswer[] data
 */
function updateWatcher(data) {
    data.forEach(console.info.bind(console));
}

ws.onmessage = function (m) {
    const [event, data] = JSON.parse(m.data);
    if (event === 'q') {
        updateWatcher(data);
    }
};
ws.onopen = function() { // Waiting for the connection to open
    ws.send("quotes", JSON.stringify(['quotes', tickersToWatchChanges]));
}
```
