# Subscribing to changes in market statuses

The server sends the 'markets' event with market status updates

#### Response:

Getting a response if successful.

```json
/**
 * @property {string} t  - Current request time
 *
 * @typedef {m: {}} MarketInfoRow
 * @property {string} n  - Full market name
 * @property {string} n2 - Market abbreviation
 * @property {string} s  - Current market status
 * @property {string} o  - Market opening time (MSK)
 * @property {string} dt - Time difference in regards to MSK time (in minutes)
**/

{
  "t"     : "2020-11-18 19:29:27",
  "m"     : [
    {
      "n"  : "KASE",
      "n2" : "KASE",
      "s"  : "CLOSE",
      "o"  : "08:20:00",
      "c"  : "14:00:00",
      "dt" : "-180"
    }
  ]
}
```

### Examples of using

## Examples

### Websockets

The server sends the 'markets' event with market depth updates

```json
ws.onmessage = function (m) {
    const [event, data] = JSON.parse(m.data);
    if (event === 'markets') {
        console.info(data);
    }
);
ws.onopen = function() { // Waiting for the connection to open
    ws.send(JSON.stringify(["markets"]));
}
```
