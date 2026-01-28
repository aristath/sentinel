# Delete/Cancel order

### Description of server request parameters and a sample response:

#### Request:

The method command delTradeOrder

```json
{
    "order_id" (int) : 2929292929
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| order_id |   | int | Request execution command. ID of the order that we want to cancel

#### Response:

Getting a response if successful.

```json
{
    "order_id" : 2929292929
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
    "error" : "Type of security not identified. Please contact Support.",
    "code"  : 0
}

// You have insufficient rights to cancel the request
{
    "code"      : 12,
    "errorMsg"  : "This order may only be cancelled by a Cancellation Order or through traders",
    "error"     : "This order may only be cancelled by a Cancellation Order or through traders"
}
```

**Description of response parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| order_id |   | int | Order ID of the canceled order

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

        delTradeOrder();

        function delTradeOrder () {
            getAuthInfo(function (responseText) {
                if (responseText.sess_id) {
                    ajaxSender(
                        {
                            "cmd"    : "delTradeOrder",
                            "apiKey" : settings.apiKey,
                            "nonce"  : settings.nonce,
                            "params" : {
                                "order_id" : 2929292929
                            }
                        },
                        settings.url + '/cmd/delTradeOrder',
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

// 2. Cancellation of a trade order
$params = [
    "order_id" => 2929292929
];

$responseExample = $publicApiClient->sendRequest('delTradeOrder', $params);
```

### Python

```python
from tradernet import Trading, TraderNetCore

config = TraderNetCore.from_config('tradernet.ini')
trade = Trading.from_instance(config)

"""
Parameters:
    ----------
    order_id: int

Returns
    -------
    result : dict
        A dictionary of orders.

"""

result = order.cancel(order_id=28533222)
print(result)
```
