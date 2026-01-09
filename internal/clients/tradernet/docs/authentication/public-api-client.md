# Public API client.

### Connecting to the API through the client.

Tradernet Python SDK.

#### Examples of using API using pre-made libraries

## Examples

```php
use Nt\PublicApiClient;

/*
 * @param {string} $apiKey - Public API key
 * @param {string} $apiSecretKey - Private API key
 * @param {Nt\PublicApiClient::V1|Nt\PublicApiClient::V2} $version - API version
 */

$apiKey = "yours_public_api_key";
$apiSecretKey = "yours_secret_api_key";
$version = PublicApiClient::V2;

$publicApiClient = new PublicApiClient($apiKey, $apiSecretKey, $version);

/*
 * @param {string} $command - API team
 * @param {array} $params - order parameters
 * @param {'json'|'array'} $type - Response template json or array
 */
$result = $publicApiClient->sendRequest($command, $params, $type);

// Examples

// 1. Opening a security session
$result = $publicApiClient->sendRequest('getAuthInfo', []);

// 2. Sending a trade order
$result = $publicApiClient->sendRequest(
    'putTradeOrder',
    [
        'instr_name' => 'BAC.US', // security ticker
        'action_id' => 1, // 1 purchase, 2 - sale
        'order_type_id' => 1, // 1 - At the market, 2 - Limit, 3 - Stop, 4 - Stop Limit, 5 - Stop Loss, 5 - Take Profit
        'qty' => 1, // Quantity
        'limit_price' => 1, // Limit price - not indicated for market orders and stop orders
        'stop_price' => 1, // Stop price - indicated for Stop orders
    ]
);
```

More information on the page Tradernet Python SDK.

```php
from tradernet import TraderNetAPI

api = TraderNetAPI('public_key', 'private_key', 'login', 'passwd')
api.user_info()
```
