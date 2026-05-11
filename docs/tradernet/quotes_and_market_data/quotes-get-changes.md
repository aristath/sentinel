# Subscribe to quotes updates.

### Description of response data from the server

The server sends the 'q' event with quote updates

```javascript
["q", { "c": "AAPL.US", .... }]
```

| c | Ticker
|---|---|
| ltr | Exchange of the latest trade
| name | Name of security
| name2 | Security name in Latin
| bbp | Best bid
| bbc | Designations of the best bid changes (\'\' – no changes, \'D\' - down, \'U\' - up)
| bbs | Best bid size
| bbf | Best bid volume
| bap | Best offer
| bac | Best offer change mark (\'\'unchanged, \'D\'down, \'U\'up)
| bas | Value (size) of the best offer
| baf | Volume of the best offer
| pp | Previous closing
| op | Opening price of the current trading session
| ltp | Last trade price
| lts | Last trade size
| ltt | Time of last trade
| chg | Change in the price of the last trade in points, relative to the closing price of the previous trading session
| pcp | Percentage change relative to the closing price of the previous trading session
| ltc | Designations of price change (\'\' – no changes, \'D\' - down, \'U\' - up)
| mintp | Minimum trade price per day
| maxtp | Maximum trade price per day
| vol | Trade volume per day, in pcs
| vlt | Trading volume per day in currency
| yld | Yield to maturity (for bonds)
| acd | Accumulated coupon interest (ACI)
| fv | Face value
| mtd | Maturity date
| cpn | Coupon, in the currency
| cpp | Coupon period (in days)
| ncd | Next coupon date
| ncp | Latest coupon date
| dpd | Purchase margin
| dps | Short sale margin
| trades | Number of trades
| min_step | Minimum price increment
| step_price | Price increment

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
