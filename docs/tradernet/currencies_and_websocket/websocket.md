# Connecting to a Websocket server.

All WebSocket server requests and responses meet the format:

```json
[event[, data]]
```

### Example with an ordinary client using integrated javascript WebSocket

```javascript
        JavaScript





const WebSocketsURL = "wss://wss.tradernet.com/";

const ws = new WebSocket(WebSocketsURL);

// Connection event
ws.onopen = function () {
    console.log('Connected to WS');
};

// Incoming message processing
ws.onmessage = function (m) {
    const [event, data] = JSON.parse(m.data);
    console.log(event, data)
};

// Connection closure processing
ws.onclose = function (e) {
    console.log('sockets closed', e);
};

// Error processing
ws.onerror = function (error) {
    console.log("Sockets.error: ", error);
    ws.close();
};
```

```javascript
(function websocketStart() {
    const ws = new WebSocket(WebSocketsURL);

    /* ... */

    ws.onclose = function (e) {
        console.log('sockets closed', e);
        setTimeout(function () {
            websocketStart();
        }, 5000); // Try to reconnect 5 seconds after the disconnection
    };
})()
```

```javascript
new WebSocket('wss://wss.tradernet.com/?SID=<your-sid>');
```

#### Response:

When connecting, the 'userdata' event with user data is received

```json
[
    "userData",
    {
        "isDemo":false,
        "mode":"prod",
        "authLogin":"[email protected]",
        "login":"user1",
        "clientLogin":"[email protected]"
    }
 ]
```

**Description of 'userdata' event parameters:**

| Parameter | Type | Description
|---|---|---|---|
| isDemo | bool | Demo mode. 'True' if the SID was not transferred, the SID authorization failed, or the user has no live account.
| model | prod|demo | It is technically a string representation of the previous parameter
| authLogin | string | Authentication login. | login | string | User login.
| clientLogin | string | Username, under which the user logged in.

## Examples

### Browser

#### Subscribing to events

```json
// Subscribing to quotes
ws.onopen = function() { // Waiting for the connection to open
    ws.send(JSON.stringify(['quotes', ['AAPL.SPB']]));
}

// Incoming data processing
functions quotesHandler(data) {
    console.log(data);
}

const handlers = {
    q: quotesHandler
};

ws.onmessage = function (m) {
    const [event, data] = JSON.parse(m.data);
    handlers[event](data);
};
```

### Python

```json
from tradernet import TraderNetWSAPI, TraderNetCore

config = TraderNetCore.from_config('tradernet.ini')

async def main() -> None:
    async with TraderNetWSAPI(config) as wsapi:  # type: TraderNetWSAPI
        async for quote in wsapi.quotes('FRHC.US'):
            print(quote)

if __name__ == '__main__':
    asyncio.run(main())
```
