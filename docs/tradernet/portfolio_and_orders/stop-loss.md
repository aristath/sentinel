# Sending Stop Loss and Take Profit commands for execution.

### Description of server request parameters and a sample response:

#### Request:

The method command putStopLoss

```json
{
    "instr_name"                (string) : "SIE.EU",
    "take_profit"               (?float) : 1,
    "stop_loss"                 (?float) : 1,
    "stop_loss_percent"         (?float) : 1,
    "stoploss_trailing_percent" (?float) : 1
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| instr_name |   | string | Request execution command. The instrument used to issue an order
| take_profit |   | null|float | Request execution command. The price of the take profit order, if null - the takeprofit order does not change. Optional parameter
| stop_loss |   | null|float | Request execution command. Stoploss order price, if null - stoploss order does not change. Optional parameter
| stop_loss_percent |   | null|float | Request execution command. Stoploss order percentage. Optional parameter
| stoploss_trailing_percent |   | null|float | Request execution command. Percentage of the accompanying stoploss order. Optional parameter

#### Response:

Getting a response if successful.

```json
 /**
 * @typedef {{}} OrderDataRow
 *
 * @property {string} date            - order date
 * @property {string} market_time     - date of securities purchase
 * @property {number} changetime      - order change time (timestamp)
 * @property {string} last_checked_datetime  - last verification date
 * @property {number} exp             - order type. 1 – «End-of-Day» (Day); 2 – Day/Night or Night/Day (Day+Ext); 3 – Good-Til-Cancel order (GTC including night sessions)
 * @property {number} id              - tradernet unique order ID
 * @property {number} order_id        - tradernet unique order ID
 * @property {number} instr_type      - *** tradernet stock ticker name
 * @property {string} instr           - tradernet stock ticker name
 * @property {number} leaves_qty      - number of remaining securities
 * @property {string} auth_login      - login of the client who sent the order
 * @property {string} creator_login   - login of the client who sent the order
 * @property {string} owner_login     - login the user, for which the order has been created
 * @property {string} user_id         - ID of the user who placed the order
 * @property {number} oper            - 1 - Buy; 2 - Buy on Margin; 3 - Sell; 4 - Sell Short
 * @property {number} p               - order price
 * @property {number} q               - number in order
 * @property {number} curr_q          - number before the transaction
 * @property {number} profit - trade profit
 * @property {string} cur             - order currency
 * @property {number} stat            - * order status
 * @property {string} stat_d          - * order status modification date
 * @property {number} stat_orig       - * initial order status. When working with API, the field value is always equal to the field value 'stat'.
 * @property {number} stat_prev       - previous order status
 * @property {number} stop            - order stop-price
 * @property {number} stop_activated     - 1|0 indicator of an activated stop order
 * @property {number} stop_init_price - price to activate a stop order
 * @property {number} trailing_price  - trailing order variance percentage
 * @property {number} type            - 1 - Market Order; 2 - Limit Order; 3 - Stop Order; 4 - Stop Limit Order; 5 - StopLoss; 6 - TakeProfit
 * @property {number} user_order_id   - order ID assigned by the user at order placing
 * @property {OrderTradeInfo} trades  - trade list for an order
 * @property {string} trades_json     - trade list for an order (JSON)
 * @property {string} error           - ordering error (JSON)
 * @property {string} safety_type_id  - security session opening type **
 * @property {string} order_nb        - Exchange ID **
 */

 /**
 * @typedef {{}} OrderTradesInfo
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

{
      "order_id" : 192054709,
      "order"    : {
            "id"                    : 192054709,
            "order_id"              : 192054709,
            "auth_login"            : "user@test.com",
            "user_id"               : 1088278273826,
            "date"                  : "2020-10-06 12:41:58",
            "stat"                  : 10,
            "stat_orig"             : 10,
            "stat_d"                : "2020-11-20 17:11:43",
            "instr"                 : "SIE.EU",
            "oper"                  : 3,
            "type"                  : 6,
            "cur"                   : "EUR",
            "p"                     : "0.033925",
            "stop"                  : "0.06",
            "stop_init_price"       : "0.036445",
            "stop_activated"        : 0,
            "q"                     : "20000",
            "leaves_qty"            : "20000",
            "exp"                   : 3,
            "stat_prev"             : 1,
            "user_order_id"         : "apiv2:160810000002",
            "trailing_price"        : null,
            "changetime"            : 160555333445000,
            "trades"                : "{}",
            "profit"                : "0.00",
            "curr_q"                : "20000",
            "trades_json"           : "[]",
            "error"                 : "",
            "market_time"           : "2020-10-06 12:41:58",
            "owner_login"           : "user@test.com",
            "creator_login"         : "user@test.com",
            "safety_type_id"        : 3,
            "repo_start_date"       : null,
            "repo_end_date"         : null,
            "repo_start_cash"       : null,
            "repo_end_cash"         : null,
            "instr_type"            : 1,
            "order_nb"              : null,
            "last_checked_datetime" : "2020-11-20 17:11:47"
      }
}
```

We get an answer in case of failure

```json
// Common error
{
    "errMsg" : "Unsupported query method",
    "code"   : 2
}

// Method error
{
    "error" : "You are trying to submit a request for client CLIENT, but you are working under client Real CLIENT",
    "code"  : 1
}
```

**Description of response parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| order_id |   | int | Order ID of the order
| order |   | array | Order data

* Order statuses are available at «Orders statuses »

** Please see the types of opening a security session at «Types of signatures »

** The instrument types and type name are available at «Instruments details »

### Examples of using

## Examples

### Browser

```javascript
<script src="jquery.min.js"></script>
<script>

    $(document).ready(function () {

        var settings = {
            url  : 'https://tradernet.com/api/v2',
            post : 'POST',
            get  : 'GET',

            apiKey       : '<YOUR_API_KEY>',
            apiSecretKey : '<YOUR_API_SECRET_KEY>',
            nonce        : (new Date().getTime() * 10000),
            sign         : '<hash>'
        };

        putStopLoss();

        function putStopLoss () {
            getAuthInfo(function (responseText) {
                if (responseText.sess_id) {
                    ajaxSender(
                        {
                            "cmd"    : "putStopLoss",
                            "apiKey" : settings.apiKey,
                            "nonce"  : settings.nonce,
                            "params" : {
                                "instr_name"               : "SIE.EU",
                                "take_profit"              : 1,
                                "stop_loss_percent"        : 1,
                                "stoploss_trailing_percent": 1
                            }
                        },
                        settings.url + '/cmd/putStopLoss',
                        function (responseText) {
                            console.log(responseText);
                        }
                    );
                }
            });


        }

        /**
         * open auth session
         */
        function getAuthInfo (callback) {
            ajaxSender(
                {
                    "cmd"    : "getAuthInfo",
                    "apiKey" : settings.apiKey,
                    "nonce"  : settings.nonce ,
                },
                settings.url + '/cmd/getAuthInfo',
                callback
            );
        }

        /**
         * Send Request
         *
         * @param data
         * @param url
         * @param callback
         */
        function ajaxSender(data, url, callback) {

            url = (typeof url === 'undefined') ? settings.url : url;

            $.ajaxSetup({
                // cors
                headers : {
                    'X_REQUESTED_WITH': 'XMLHttpRequest',
                    'X-NtApi-Sig'     : settings.sign,
                    'Nt-Jqp'          : true
                },
                xhrFields: {withCredentials:true}
            });

            $.ajax({
                url      : url,
                method   : settings.post,
                dataType : 'json',
                data     : data,
                success  : function (responseText) {
                    if (callback) {
                        callback(responseText);
                    }
                    else {
                        console.log(responseText);
                    }
                },
                error: function (err) {
                    console.log(err)
                }
            });
        }

    });

</script>
```

### PHP

```php
$publicApiClient = new PublicApiClient($apiKey, $apiSecretKey, Nt\PublicApiClient::V2);

$params = [
    "instr_name"               => "SIE.EU",
    "take_profit"              => 1,
    "stop_loss_percent"        => 1,
    "stoploss_trailing_percent"=> 1
];

$responseExample = $publicApiClient->sendRequest('putStopLoss', $params);
```

### Python

```python
from tradernet import Trading, TraderNetCore

config = TraderNetCore.from_config('tradernet.ini')
trade = Trading.from_instance(config)

"""
    Stop Loss

    Parameters:
        ----------
        symbol ('instr_name'): str
        price ('limit_price'): float

    Returns
        -------
        result : dict
            A dictionary of orders.
"""

result = order.stop('FRHC.US', price=0.35)
print(result)

"""
    Trailing Stop Loss

    Parameters:
        ----------
        symbol ('instr_name'): str
        percent ('stop_loss_percent', 'stoploss_trailing_percent'): float

    Returns
        -------
        result : dict
            A dictionary of orders.
"""

result = order.trailing_stop('FRHC.US', percent=1)
print(result)

"""
    Take Profit

    Parameters:
        ----------
        symbol ('instr_name'): str
        price ('take_profit'): float

    Returns
        -------
        result : dict
            A dictionary of orders.
"""

result = order.take_profit('FRHC.US', price=0.9)
print(result)
```
