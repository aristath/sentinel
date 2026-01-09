# API key

#### Examples of using

## Examples

```php
declare(strict_types=1);

use GuzzleHttp\Client;
use GuzzleHttp\Exception\GuzzleException;
use GuzzleHttp\RequestOptions;

$api = new TradernetApiClient(
    'public key',
    'private key',
);

$api->request('commandName', 'GET', ['a' => 10, 'b' => 'foo']));

class TradernetApiClient
{
    /** @var Client */
    protected Client $client;

    /**
     * @param string $publicKey Your public API key
     * @param string $privateKey Your private API key
     */
    public function __construct(
        private readonly string $publicKey,
        #[SensitiveParameter] private readonly string $privateKey,
        string $host = 'https://tradernet.com/api/',
    ) {
        $this->client = new Client(['base_uri' => $host]);
    }

    /**
     * @param string $command API command name
     * @param string $method HTTP method
     * @param array $data Array of parameters
     * @throws GuzzleException
     * @return array
     */
    public function request(
        string $command,
        string $method,
        array $data = [],
    ): array {
        $timestamp = time();

        if (
            $method === 'POST'
            || $method === 'PUT'
        ) {
            $data = $data
                ? json_encode($data)
                : '';
            $signature = hash_hmac(
                'sha256',
                $data . $timestamp,
                $this->privateKey,
            );
            $options = [RequestOptions::BODY => $data];
            $headers = ['Content-Type' => 'application/json'];
        } else {
            $signature = hash_hmac(
                'sha256',
                (string) $timestamp,
                $this->privateKey,
            );
            $options = [RequestOptions::QUERY => $data];
            $headers = [];
        }

        $options[RequestOptions::HEADERS] = array_merge(
            $this->buildHeaders($signature, $timestamp),
            $headers,
        );

        $response = $this->client->request($method, $command, $options);

        return json_decode($response->getBody()->getContents(), true);
    }

    /**
     * @param string $signature
     * @param int $timestamp
     * @return array
     */
    private function buildHeaders(string $signature, int $timestamp): array
    {
        return [
            'X-NtApi-PublicKey' => $this->publicKey,
            'X-NtApi-Sig' => $signature,
            'X-NtApi-Timestamp' => $timestamp,
        ];
    }
}
```

```php
const crypto = require('crypto');
const axios = require('axios');

const publicKey = '';
const privateKey = '';

const timeStamp = Math.floor(Date.now() / 1000).toString();
const payload = JSON.stringify({
    a: 10,
    b: 'foo',
});

const headers = {
    'Content-Type': 'application/json',
    'X-NtApi-PublicKey': publicKey,
    'X-NtApi-Timestamp': timeStamp,
    'X-NtApi-Sig': generateSignature(payload + timeStamp),
};

function generateSignature (data) {
    return crypto
        .createHmac('sha256', privateKey)
        .update(data)
        .digest('hex');
}

async function callApi (command, payload, headers) {
    return await axios.post(
        `https://tradernet.com/api/${command}`,
        payload,
        { headers },
    );
}

callApi(payload, headers).then((response) => console.log(response.data));
```

More information on the page Tradernet Python SDK.

```php
from tradernet import TraderNetAPI

api = TraderNetAPI('public_key', 'private_key', 'login', 'passwd')
api.user_info()
```
