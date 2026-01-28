# Send an order to execute.

### Description of server request parameters and a sample response:

#### Request:

The method command putTradeOrder

```json
{
    "instr_name"    (string) : "AAPL.US",
    "action_id"     (int)    : 1,
    "order_type_id" (int)    : 2,
    "qty"           (int)    : 100,
    "limit_price"   (?float) : 40,
    "stop_price"    (?float) : 0,
    "expiration_id" (int)    : 3,
    "user_order_id" (?int)   : 146615630
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| instr_name |   | string | Request execution command. The instrument used to issue an order
| action_id |   | int | Request execution command. Action: 1 - A Purchase (Buy); 2 - A Purchase when making trades with margin (Buy on Margin); 3 - A Sale (Sell); 4 - A Sale when making trades with margin (Sell Short)*
| order_type_id |   | int | Request execution command. Type of order: 1 - Market Order (Market); 2 - Order at a set price (Limit); 3 - Market Stop-order (Stop); 4 - Stop-order at a set price (Stop Limit)
| qty |   | int | Request execution command. Quantity in the order
| limit_price |   | null|float | Request execution command. Limit price. Optional parameter
| stop_price |   | null|float | Request execution command. Stop price. Optional parameter
| expiration_id |   | int | Request execution command. Order expiration: 1 - Order 'until the end of the current trading session' (Day); 2 - Order 'day/night or night/day' (Day + Ext); 3 - Order 'before cancellation' (GTC, before cancellation with participation in night sessions)
| user_order_id |   | null|int | Request execution command. Custom order ID. Optional parameter

* Tradernet allows using margin at all times. The check is only carried out in terms of adequacy of the portfolio and orders collateral. I.e., the scope of control covers the amount or number in the order placed on the side of the final terminal.. The action_id field values equal to 3 or 4 are now the same in the system.

#### Response:

Getting a response if successful.

```json
{
    "order_id" : 4982349829328
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
    "error" : "Invalid transaction identifier, allowed values 1 - purchase, 3 - sale",
    "code"  : 0
}
```

**Description of response parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| order_id |   | int | Order ID of the created order

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

        putTradeOrder();

        function putTradeOrder () {
            getAuthInfo(function (responseText) {
                if (responseText.sess_id) {
                    ajaxSender(
                        {
                            "cmd"    : "putTradeOrder",
                            "apiKey" : settings.apiKey,
                            "nonce"  : settings.nonce,
                            "params" : {
                                "instr_name"    : "AAPL.US",
                                "action_id"     : 1,
                                "order_type_id" : 2,
                                "limit_price"   : 1.03,
                                "qty"           : 10000,
                                "expiration_id" : 1
                            }
                        },
                        settings.url + '/cmd/putTradeOrder',
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

// 1. Opening a security session
$result = $publicApiClient->sendRequest('getAuthInfo', []);

// 2. Sending a trade order
$params = [
    "instr_name"    => "AAPL.US",
    "action_id"     => 1,
    "order_type_id" => 2,
    "qty"           => 100,
    "limit_price"   => 40,
    "stop_price"    => 0,
    "expiration_id" => 3,
    "user_order_id"   => 0
];

$responseExample = $publicApiClient->sendRequest('putTradeOrder', $params);
```

### Python

```python
from tradernet import Trading, TraderNetCore

config = TraderNetCore.from_config('tradernet.ini')
trade = Trading.from_instance(config)

"""
Order to buy

Parameters:
    ----------
    symbol ('instr_name'): str
    quantity ('qty'): int
    price ('limit_price'): float, optional
    duration ('expiration_id'): str, optional. 'day' by default
    use_margin ('action_id'): bool, optional. 'True' by default

Returns
    -------
    result : dict
        A dictionary of orders.

"""

result = order.buy('FRHC.US', quantity=1, price=0.4, use_margin=False)
print(result)

"""
Order to sell

Parameters:
    ----------
    symbol ('instr_name'): str
    quantity ('qty'): int
    price ('limit_price'): float, optional
    duration ('expiration_id'): str, optional. 'day' by default
    use_margin ('action_id'): bool, optional. 'True' by default

Returns
    -------
    result : dict
        A dictionary of orders.

"""

result = order.sell('FRHC.US', quantity=1, price=0.8, use_margin=False)
print(result)
```
