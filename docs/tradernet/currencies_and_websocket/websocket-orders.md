# Subscribing to order changes.

### Description of server request parameters and a sample response:

The server sends the 'orders' event with order updates

#### Response:

Getting a response if successful.

```json
/**
 * @typedef {{}} OrderDataRow
 *
 * @property {0|1}            aon             - All or Nothing setting is 0 – can be partially executed; 1 – cannot be partially executed
 * @property {string}         cur             - order currency
 * @property {string}         date            - order date
 * @property {1|2|3}          exp             - order type. 1 – «End-of-Day» (Day); 2 – Day/Night or Night/Day (Day+Ext); 3 – Good-Til-Cancel order (GTC including night sessions)
 * @property {number}         fv              - coefficient for securities traded in relative currencies, for example, future contracts
 * @property {number}         order_id        - tradernet unique order ID
 * @property {string}         instr           - tradernet stock ticker name
 * @property {number}         leaves_qty      - remaining securities number
 * @property {string}         auth_login      - login of the client who sent the order
 * @property {string}         creator_login   - login of the client who sent the order
 * @property {string}         owner_login     - login the user, for which the order has been created
 * @property {number}         mkt_id          - market unique trade ID
 * @property {string}         name            - name of a company issuing a security
 * @property {string}         name2           - alternative name of the issuer of security
 * @property {number}         oper            - 1 - Buy; 2 - Buy on Margin; 3 - Sell; 4 - Sell Short
 * @property {number}         p               - order price
 * @property {number}         q               - number in order
 * @property {number}         rep             -
 * @property {number}         stat            - order status
 * @property {string}         stat_d          - order status modification date
 * @property {number}         stat_orig       - initial order status. When working with API, the field value is always equal to the field value 'stat'.
 * @property {number}         stat_prev       - previous order status
 * @property {number}         stop            - order stop-price
 * @property {1|0}            stop_activated  - indicator of an activated stop order
 * @property {number}         stop_init_price - price to activate a stop order
 * @property {number}         trailing_price  - trailing order variance percentage
 * @property {1|2|3|4|5|6}    type            - 1 - Market Order; 2 - Limit Order; 3 - Stop Order; 4 - Stop Limit Order; 5 - StopLoss; 6 - TakeProfit
 * @property {number}         user_order_id   - order ID assigned by the user at order placing
 * @property {OrderTradeInfo} trade           - trade list for an order
 */

 /**
 * @typedef {{}} OrderTradeInfo
 *
 * @property {number} acd    - Accumulated coupon interest
 * @property {string} date   - trade date
 * @property {number} fv     - coefficient for securities traded in relative currencies, for example, future contracts
 * @property {number} go_sum - initial margin per trade
 * @property {number} id     - Tradernet unique trade ID
 * @property {number} p      - trade price
 * @property {number} profit - trade profit
 * @property {number} q      - Number of securities in a trade
 * @property {number} v      - trade amount
 */


/**
 * @type {SocketOrdersResponse}
 */
var responseData = [{
        "aon"             : 0,
        "cur"             : "USD",
        "curr_q"          : 0,
        "date"            : "2015-12-23T17:05:02.133",
        "exp"             : 1,
        "fv"              : 0,
        "order_id"        : 8757875,
        "instr"           : "FCX.US",
        "leaves_qty"      : 0,
        "auth_login"      : "virtual@virtual.com",
        "creator_login"   : "virtual@virtual.com",
        "owner_login"     : "virtual@virtual.com",
        "mkt_id"          : 30000000001,
        "name"            : "Freeport-McMoran Cp & Gld",
        "name2"           : "Freeport-McMoran Cp & Gld",
        "oper"            : 2,
        "p"               : 6.5611,
        "q"               : 2625,
        "rep"             : 0,
        "stat"            : 21,
        "stat_d"          : "2015-12-23T17:05:03.283",
        "stat_orig"       : 21,
        "stat_prev"       : 10,
        "stop"            : 0,
        "stop_activated"  : 1,
        "stop_init_price" : 6.36,
        "trailing_price"  : 0,
        "type"            : 1,
        "user_order_id"   : 1450879514204,
        "trade": [{
            "acd"    : 0,
            "date"   : "2015-12-23T17:05:03",
            "fv"     : 100,
            "go_sum" : 0,
            "id"     : 13446624,
            "p"      : 6.37,
            "profit" : 0,
            "q"      : 2625,
            "v"      : 16721.25
        }]
}];
```

### Examples of using

## Examples

### Websockets

The server sends the 'orders' event with order updates

```javascript
const WS_SOCKETURL = 'wss://wss.tradernet.com/';

const ws = new(WS_SOCKETURL);

ws.onopen = function() { // Waiting for the connection to open
    /**
     * Subscribe to orders updates
     */
    ws.send(JSON.stringify(['orders']));
});

ws.onmessage  = function ({ data }) {
    /**
         * Server message handler
         * @param {SocketOrdersResponse} data - order details
     */
    const [event, messageData] = JSON.parse(data)
    if (event === 'orders') {
        console.info(messageData);
    }
};
```

### PHP

```php
/**
 * Get a list of existing orders
 */

$publicApiClient = new PublicApiClient($apiKey, $apiSecretKey, Nt\PublicApiClient::V2);
$responseExample = $publicApiClient->sendRequest('getNotifyOrderJson');
```
