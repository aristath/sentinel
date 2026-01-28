# Subscribe to market depth updates.

The server sends the 'b' event with market depth updates

### Description of response data from the server

```json
/**
 * @typedef {{}} DomInfoRow
 * @property {number} k -  position number in the market depth
 * @property {number} p -  string price of the market depth
 * @property {number} q -  a number in a string
 * @property {'S'|'B'} s -  buy or sell sign
 */

/**
 * @typedef {{}} DomInfoBlock
 * @property {string} i -  ticker, by which market depth information has been received
 * @property {number} cnt -  depth of market data
 * @property {DomInfoRow[]} ins -  new strings in market depth
 * @property {DomInfoRow[]} del -  Market Depth strings to delete
 * @property {DomInfoRow[]} upd -  market depth data strings to update
 */

/**
 *  Example of market depth received
 * @type DomInfoBlock
 */
var data = {
    "n": 102,
    "i": "AAPL.US",
    "del": [],
    "ins": [],
    "upd": [
        {"p": 33.925, "s": "S", "q": 196100, "k": 3},
        {"p": 33.89, "s": "S", "q": 373700, "k": 6},
        {"p": 33.885, "s": "S", "q": 1198800, "k": 7},
        {"p": 33.88, "s": "S", "q": 251600, "k": 8}
    ],
    "cnt": 21,
    "x": 11
};
```

### Examples of using

## Examples

### Browser

```javascript
const ticker = 'AAPL.US';

ws.onmessage = function (m) {
    const [event, data] = JSON.parse(m.data);
    if (event === 'b') {
        console.info(data);
    }
};
ws.onopen = function() { // Waiting for the connection to open
    ws.send(JSON.stringify(["orderBook", [ticker]]));
}
```
