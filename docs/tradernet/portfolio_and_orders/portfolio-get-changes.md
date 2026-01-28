# Getting information on a portfolio and subscribing for changes

### Example and description of the receiving details

#### Request:

The method command getPositionJson

```json
{
    "cmd" (string)   : "getPositionJson",
    "params" (array) : {}
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | string | Request execution command
| params |   | array | Request execution parameters

#### Response:

Getting a response if successful.

```json
/**
 * @typedef {{}} AccountInfoRow (acc)
 * @property {string} curr - account currency
 * @property {number} currval - account currency exchange rate
 * @property {number} forecast_in
 * @property {number} forecast_out
 * @property {number} s - available funds
 */

/**
 * @typedef {{}} PositionInfoRow (pos)
 * @property {number} acc_pos_id - Unique identifier of an open position in the Tradernet system
 * @property {number} accruedint_a - (ACI) accrued coupon income
 * @property {string} curr - Open position currency
 * @property {number} currval - Account currency exchange rate
 * @property {number} fv - Coefficient to calculate initial margin
 * @property {number} go - Initial margin per position
 * @property {string} i - Open position ticker
 * @property {number} k
 * @property {number} q - Number of securities in the position
 * @property {number} s
 * @property {number} t
 * @property {string} t2_in
 * @property {string} t2_out
 * @property {number} vm - Variable margin of a position
 * @property {string} name - Issuer name
 * @property {string} name2 - Issuer alternative name
 * @property {number} mkt_price - Open position market value
 * @property {number} market_value - Asset value
 * @property {number} bal_price_a - Open position book value
 * @property {number} open_bal - Position book value
 * @property {number} price_a - Book value of the position when opened
 * @property {number} profit_close - Previous day positions profit
 * @property {number} profit_price - Current position profit
 * @property {number} close_price - Position closing price
 * @property {{trade_count: number}[]} trade
*/

/**
* @typedef {{}}SocketPortfolioResponseRow
* @property {{acc: AccountInfoRow[], pos: PositionInfoRow[]}} ps
*/

/**
* @typedef {SocketPortfolioResponseRow} SocketPortfolioResponse
*/

/**
* @type {SocketPortfolioResponse}
*/
{
    "key": "%test@test.com",
    "acc": [
        {
            "s": ".00000000",
            "forecast_in": ".00000000",
            "forecast_out": ".00000000",
            "curr": "USD",
            "currval": 78.95,
            "t2_in": ".00000000",
            "t2_out": ".00000000"
        },
        ...
    ],
    "pos": [
        {
            "i": "AAPL.US",
            "t": 1,
            "k": 1,
            "s": 22.4,
            "q": 100,
            "fv": 100,
            "curr": "USD",
            "currval": 1,
            "name": "Apple Inc.",
            "name2": "Apple Inc.",
            "open_bal": 299.4,
            "mkt_price": 23.81,
            "vm": ".00000000",
            "go": ".00000000",
            "profit_close": -2.4,
            "acc_pos_id": 85600002,
            "accruedint_a": ".00000000",
            "acd": ".00000000",
            "bal_price_a": 29.924,
            "price_a": 29.924,
            "base_currency": "USD",
            "face_val_a": 3,
            "scheme_calc": "T2",
            "instr_id": 10000007229,
            "Yield": ".00000000",
            "issue_nb": "US0000040",
            "profit_price": 2.83,
            "market_value": 2020,
            "close_price": 20.83
        },
        ...
    ]
}
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
| result |   | array | List of portfolio information

### Examples of using

## Examples

### Websockets

The server sends the 'portfolio' event with portfolio updates

```javascript
const WS_SOCKETURL = 'wss://wss.tradernet.com/';

const ws = new WebSocket(WS_SOCKETURL);

ws.onopen = function () {
    /**
     * Subscribe to portfolio updates
     */
    ws.send(JSON.stringify(["portfolio"]));
};

ws.onmessage = function (m) {
    /**
         * Server message handler         * @param {SocketPortfolioResponse} data - Portfolio details     */
    const [event, data] = JSON.parse(m)
    if (event === 'portfolio') {
        console.info(data);
    }
);
```

### PHP

```php
/**
 * Retrieving information on the portfolio
 */
$publicApiClient = new PublicApiClient($apiKey, $apiSecretKey, Nt\PublicApiClient::V2);

$responseExample = $publicApiClient->sendRequest('getPositionJson');
```

### Python

```python
'''
The PublicApiClient.py script can, as an option, be hosted:
[your_current_py_directory]/v2/PublicApiClient.py
'''

import json
import v2.PublicApiClient as NtApi

pub_ = '[public Api key]'
sec_ = '[secret Api key]'

cmd_ = 'getPositionJson'

res = NtApi.PublicApiClient(pub_, sec_, NtApi.PublicApiClient().V2)

print(res.sendRequest(cmd_).content.decode("utf-8"))
```
